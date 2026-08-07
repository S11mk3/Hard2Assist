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
_spoken = []

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


def spoken_count():
    """How many lines have actually made it out of the speaker."""
    return len(_spoken)


def _safely(hook):
    """Run a pause/resume hook without letting it kill this thread."""
    if hook is None:
        return
    try:
        hook()
    except Exception:
        pass


def _say_with(engine, text):
    """Say one line, rebuilding the engine if it has stopped working.

    pyttsx3 engines go bad -- an interrupted runAndWait() leaves the driver
    thinking its loop is still running, and every later call fails. Left alone
    that means the app speaks once and is mute for the rest of the session, so
    a failure gets one fresh engine and one retry rather than being terminal.
    """
    try:
        engine.say(text)
        engine.runAndWait()
        return engine
    except Exception:
        pass

    try:
        engine.stop()
    except Exception:
        pass

    fresh = _new_engine()
    fresh.say(text)
    fresh.runAndWait()
    return fresh


def _new_engine():
    """A genuinely new engine.

    pyttsx3.init() hands back a cached one, which would just be the broken
    engine again, so build it directly and fall back to init() only if that
    class ever moves.
    """
    try:
        from pyttsx3.engine import Engine
        return Engine(None, False)
    except Exception:
        import pyttsx3
        return pyttsx3.init()


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
        engine = _new_engine()
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
            _safely(_pause_mic)

        try:
            engine = _say_with(engine, text)
            _spoken.append(text)
        except Exception as e:
            # A broken voice must never take the app down, but it must not be
            # invisible either -- a bundle that creates the engine and then
            # fails to speak would otherwise look like it is working.
            _error = f"{type(e).__name__}: {e}"
        finally:
            # Only start listening again once there is nothing left to say, so
            # a run of messages does not flap the microphone on and off. This
            # has to happen even if speaking failed, or the app goes deaf --
            # and the hooks are guarded because an exception raised in here
            # would kill this thread and end speech for the whole session.
            if _queue.empty():
                speaking = False
                _safely(_resume_mic)

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
