"""Hard2Assist entry point.

Starts the GUI by default. Pass --console to run the same listening loop in
the terminal instead, without a window.
"""

import sys

import listener
import registry
import speech
import wizard
from output import detail, say


def run_console():
    """Run Hard2Assist in the terminal."""
    commands = registry.load()
    if not commands:
        say("No commands were found, so there is nothing to do.")
        return

    # The banner and command list are informational, so they are written
    # rather than read aloud.
    detail("Hard2Assist")
    detail("Commands: " + ", ".join(sorted(commands)))

    def on_command(command):
        detail(f"> {command}")
        # Guarded the same way the GUI guards it: one raising command must
        # not take the whole microphone loop down with it.
        try:
            result = registry.dispatch(commands, command)
        except Exception as e:
            detail(f"Could not run that: {e}")
            return
        if result is registry.STOP:
            ears.stop()

    def on_status(text, transient=False):
        # Transient statuses change constantly and would flood the terminal.
        if not transient:
            detail(text)

    # No may_listen gate: console mode has no window, so "only listen while in
    # focus" has nothing to mean and it always listens.
    ears = listener.Listener(
        on_command=on_command,
        on_status=on_status,
        on_ready=wizard.on_ready,
    )

    # Mute the microphone while speaking, so the app does not hear its own
    # replies and act on the words in them.
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
