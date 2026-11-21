"""Hard2Assist: the window by default, or the same listening loop in a terminal with --console."""

import sys

import listener
import registry
import speech
import storage
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
        if not transient and text not in ("Paused", shown):
            shown = text
            print(text)

    # No may_listen: with no window there is nothing to be in focus, so it always listens.
    ears = listener.Listener(on_command, on_status, on_ready=wizard.on_ready,
                             opens_with_command=registry.opens_with_command)
    speech.on_speaking(ears.pause, ears.resume)
    speech.start()
    ears.run()


def main():
    start_log(storage.USER_DIR)
    if "--console" in sys.argv:
        run_console()
    else:
        import gui
        gui.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        detail("\nExiting.")
