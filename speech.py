"""Saying things out loud.

One thread owns the voice, and it is the only thread that ever touches the
engine. pyttsx3.init() hands back the same cached engine every time it is
called, so creating one anywhere else -- even briefly, to check speech works --
gives that thread a half-used engine that then stops responding.

While it is talking the microphone is paused, otherwise Hard2Assist hears
"Closing one window", picks the word "close" out of it, and sets off again.
"""

import queue
import threading

_queue = queue.Queue()
_thread = None
_ready = threading.Event()
_available = False
_enabled = True

_pause_mic = None
_resume_mic = None
_error = ""

START_TIMEOUT = 15


def on_speaking(pause, resume):
    """Hand over the two functions that stop and start the microphone."""
    global _pause_mic, _resume_mic
    _pause_mic, _resume_mic = pause, resume


def start():
    """Bring the voice up. Returns False if this PC has no working speech."""
    global _thread

    if _thread is None:
        _thread = threading.Thread(target=_run, daemon=True)
        _thread.start()

    # The thread reports back whether it managed to build an engine.
    _ready.wait(timeout=START_TIMEOUT)
    return _available


def available():
    return _available


def error():
    """Why speech is unavailable. Empty when it is fine."""
    return _error


def enabled():
    return _enabled and _available


def set_enabled(value):
    global _enabled
    _enabled = bool(value)


def speak(text):
    if enabled() and text:
        _queue.put(text)


def stop():
    _queue.put(None)


def idle():
    """True when there is nothing left to say. Used by the tests."""
    return _queue.empty()


def _run():
    global _available, _error

    try:
        # COM has to be switched on for each thread that uses it. comtypes does
        # that when it is first imported -- but if anything else imported it
        # first, on another thread, the import here is a no-op and the voice
        # fails with "CoInitialize has not been called". So ask explicitly.
        import comtypes
        comtypes.CoInitialize()

        # comtypes normally writes generated COM wrappers into its own package
        # folder. Inside the built .exe that is a temporary unpacked copy, so
        # building them in memory instead avoids writing there at all.
        import comtypes.client
        comtypes.client.gen_dir = None
    except Exception:
        pass

    try:
        import pyttsx3
        engine = pyttsx3.init()
    except Exception as e:
        _available = False
        _error = f"{type(e).__name__}: {e}"
        _ready.set()
        return

    _available = True
    _ready.set()

    speaking = False
    while True:
        text = _queue.get()

        if text is None:
            break

        if not speaking:
            speaking = True
            if _pause_mic:
                _pause_mic()

        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass  # a broken voice must never take the app down
        finally:
            # Only start listening again once there is nothing left to say, so
            # a run of messages does not flap the microphone on and off. This
            # has to happen even if speaking failed, or the app goes deaf.
            if _queue.empty():
                speaking = False
                if _resume_mic:
                    _resume_mic()

    if speaking and _resume_mic:
        _resume_mic()

    try:
        engine.stop()
    except Exception:
        pass

    try:
        import comtypes
        comtypes.CoUninitialize()
    except Exception:
        pass
