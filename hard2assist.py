"""Hard2Assist -- say "computer <something>" and it does it.

Opens a window by default. Pass --console for a plain terminal version, which
is handy when something is going wrong and you want to see it happen.
"""

import os
import sys
import tempfile

import apps
import listener
import registry
import speech
from output import say

EXPECTED_COMMANDS = {"open", "close", "kill", "help", "stop", "time", "date",
                     "battery", "status", "disk", "volume", "play", "search"}


def run_selftest():
    """Check that a build is complete. Run this after building the .exe.

    A .exe that is missing pieces still starts and still opens its window -- it
    just quietly has no commands, because the command modules are loaded by
    scanning at runtime and PyInstaller cannot see what they import. This says
    so plainly instead.
    """
    report = []

    def note(text):
        report.append(str(text))

    note(f"frozen        : {getattr(sys, 'frozen', False)}")
    note(f"roots         : {registry._roots()}")

    commands = registry.load()
    note(f"commands found: {sorted(commands) or 'NONE'}")

    for module_name in ("apps", "win", "psutil", "speech_recognition",
                        "pyttsx3", "pyttsx3.drivers.sapi5", "comtypes"):
        try:
            __import__(module_name)
            note(f"import {module_name:<24}: ok")
        except Exception as e:
            note(f"import {module_name:<24}: MISSING ({e})")

    # A build with no voice starts perfectly happily and is simply mute, so it
    # has to be checked rather than noticed.
    if speech.start():
        note("speech                          : ok")
    else:
        note(f"speech                          : NOT AVAILABLE -- {speech.error()}")

    tally = apps.counts()
    note(f"apps                            : {sum(tally.values())} "
         f"({', '.join(f'{k} {v}' for k, v in sorted(tally.items()))})")

    missing = EXPECTED_COMMANDS - set(commands)
    ok = not missing and speech.available()
    note("")
    if missing:
        note(f"RESULT: FAILED, missing commands {sorted(missing)}")
    elif not speech.available():
        note("RESULT: FAILED, no speech")
    else:
        note("RESULT: ok")

    text = "\n".join(report)

    # A windowed build has no stdout, so always leave the report on disk too.
    path = os.path.join(tempfile.gettempdir(), "hard2assist-selftest.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    if sys.stdout is not None:
        print(text)
        print(f"\n(also written to {path})")

    return 0 if ok else 1


def run_console():
    commands = registry.load()
    if not commands:
        say("No commands were found, so there is nothing to do.")
        return

    say("Hard2Assist")
    say("Commands: " + ", ".join(sorted(commands)))

    def on_command(command):
        say(f"> {command}")
        if registry.dispatch(commands, command) is registry.STOP:
            ears.stop()

    def on_status(text, transient=False):
        if not transient:          # transient ones would spam the terminal
            say(text)

    ears = listener.Listener(on_command=on_command, on_status=on_status)

    if speech.start():
        speech.on_speaking(ears.pause, ears.resume)

    ears.run()


def main():
    if "--selftest" in sys.argv:
        return run_selftest()

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
        say("\nExiting.")
