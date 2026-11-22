"""Hard2Assist: the dock at the top of the screen by default, or the same listening loop in a
terminal with --console."""

import os
import sys

import listener
import models
import registry
import speech
import storage
import win
import wizard
from output import detail, start_log


def run_console():
    commands = registry.load()
    if not commands:
        detail("No commands were found, so there is nothing to do.")
        return
    detail("Hard2Assist")
    detail("Commands: " + ", ".join(sorted(commands)))

    def on_command(text):
        if registry.run(text) is registry.STOP:
            ears.stop()

    shown = None

    def on_status(text, transient=False):
        # Transient lines, and the pause around every reply, would flood the terminal. Printed
        # rather than detail(): the listener already logs each change.
        nonlocal shown
        if not transient and text not in ("Speaking", shown):
            shown = text
            print(text)

    tenth = -1

    def on_download(fraction):
        nonlocal tenth
        if int(fraction * 10) != tenth:
            tenth = int(fraction * 10)
            print(f"Downloading my hearing and voice: {tenth * 10}%")

    ears = listener.Listener(on_command, on_status, on_ready=wizard.on_ready,
                             opens_with_command=registry.opens_with_command, on_download=on_download)
    speech.on_speaking(ears.pause, ears.resume)
    speech.start()
    ears.run()


def main():
    if not win.first_instance():
        win.show_first_instance()   # one copy only: two would both answer every command
        return 0

    start_log(storage.USER_DIR)
    models.load_library()
    if "--record" in sys.argv:   # keep what is heard, for measuring recognition on a real voice
        listener.RECORD_TO = os.path.join(storage.LOCAL_DIR, "recordings")
        detail(f"(Recording everything I hear into {listener.RECORD_TO})")
    if "--console" in sys.argv:
        run_console()
    else:
        import dock
        dock.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        detail("\nExiting.")
