import sys

import listener
import registry
import speech
from output import detail, say


def run_console():
    commands = registry.load()
    if not commands:
        say("No commands were found, so there is nothing to do.")
        return

    # detail(), not say() -- a banner and a list of every command is not
    # something anyone wants read aloud at startup.
    detail("Hard2Assist")
    detail("Commands: " + ", ".join(sorted(commands)))

    def on_command(command):
        detail(f"> {command}")
        if registry.dispatch(commands, command) is registry.STOP:
            ears.stop()

    def on_status(text, transient=False):
        if not transient:          # transient ones would spam the terminal
            detail(text)

    ears = listener.Listener(on_command=on_command, on_status=on_status)

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
