"""Hard2Assist entry point.

Starts the GUI by default. Pass --console to run the same listening loop
in the terminal instead, without a window.
"""

import sys

import listener
import registry
import speech
from output import detail, say


def run_console():
    """Run Hard2Assist in the terminal."""
    commands = registry.load()
    if not commands:
        say("No commands were found, so there is nothing to do.")
        return

    # The startup banner and command list are informational, so they are
    # written with detail() rather than read aloud.
    detail("Hard2Assist")
    detail("Commands: " + ", ".join(sorted(commands)))

    def on_command(command):
        detail(f"> {command}")
        if registry.dispatch(commands, command) is registry.STOP:
            ears.stop()

    def on_status(text, transient=False):
        # Transient statuses update constantly and would flood the terminal,
        # so only persistent ones are printed.
        if not transient:
            detail(text)

    ears = listener.Listener(on_command=on_command, on_status=on_status)

    # Pause the microphone while speaking so the assistant does not pick up
    # and react to its own voice.
    if speech.start():
        speech.on_speaking(ears.pause, ears.resume)

    ears.run()


def main():
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
