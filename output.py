"""What commands tell the user.

    say(text)      written and spoken
    warn(text)     written highlighted, with the failure chime, and spoken: something did not work
    detail(text)   written only, for lists and long explanations

The dock points the sink at its conversation panel; --console prints. Once start_log() has run,
everything also goes to log.txt, crashes included, since the built app has no console.
"""

import logging
import logging.handlers
import os
import sys
import threading

import speech

log = logging.getLogger("hard2assist")
log.addHandler(logging.NullHandler())


def _print(text, _tag=None):
    try:
        print(text)
    except UnicodeEncodeError:
        # Window titles and Start Menu names hold characters a console codepage cannot show.
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


_sink = _print


def on_message(sink):
    """Send everything to sink(text, tag): tag is "say", "warn", or None for detail."""
    global _sink
    _sink = sink


def say(text):
    _sink(text, "say")
    log.info(text)
    speech.speak(text)


def warn(text):
    _sink(text, "warn")
    log.warning(text)
    speech.beep_failed()
    speech.speak(text)


def detail(text):
    _sink(text, None)
    log.info(text)


def plural(count, noun):
    """ "1 window", "2 windows", "3 processes"."""
    if count != 1:
        noun += "es" if noun.endswith("s") else "s"
    return f"{count} {noun}"


def start_log(folder):
    """Also write every line, and every unhandled error, to folder/log.txt."""
    try:
        os.makedirs(folder, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(folder, "log.txt"), maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    except OSError:
        return

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    previous_hook, previous_thread_hook = sys.excepthook, threading.excepthook

    def crashed(*exc_info):
        log.error("Unhandled error", exc_info=exc_info)
        previous_hook(*exc_info)

    def thread_crashed(args):
        log.error("Unhandled error in thread %s", args.thread.name if args.thread else "?",
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        previous_thread_hook(args)

    sys.excepthook, threading.excepthook = crashed, thread_crashed
