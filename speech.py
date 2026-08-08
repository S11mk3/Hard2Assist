"""Text-to-speech via the Windows SAPI voice.

All speech happens on one dedicated worker thread that owns the COM voice
object; other threads just queue text with speak(). While something is being
said, the registered pause hook mutes the microphone so the assistant does
not hear and react to its own voice.
"""

import queue
import threading
import time

_queue = queue.Queue()
_thread = None
_ready = threading.Event()
_available = False
_enabled = True
_error = ""

_pause_mic = None
_resume_mic = None

# How long start() waits for the worker thread to report readiness.
START_TIMEOUT = 15

# A Speak() call that returns faster than this cannot have produced audio;
# it is treated as a silently broken voice (see _speak_once).
REAL_SPEECH_SECONDS = 0.15


def on_speaking(pause, resume):
    """Register the callbacks that mute and unmute the microphone."""
    global _pause_mic, _resume_mic
    _pause_mic, _resume_mic = pause, resume


def start():
    """Start the speech thread. Returns False if this PC has no working voice."""
    global _thread

    if _thread is None:
        _thread = threading.Thread(target=_run, daemon=True)
        _thread.start()

    _ready.wait(timeout=START_TIMEOUT)
    return _available


def available():
    return _available


def error():
    """Description of the last speech failure. Empty when everything works."""
    return _error


def enabled():
    return _enabled and _available


def set_enabled(value):
    """Turn speaking on or off (the `quiet` and `speak` commands)."""
    global _enabled
    _enabled = bool(value)


def speak(text):
    """Queue text to be spoken. A no-op when speech is off or unavailable."""
    if enabled() and text:
        _queue.put(text)


def stop():
    """Ask the speech thread to finish and exit."""
    _queue.put(None)


def _safely(hook):
    """Run a pause/resume hook without letting an exception kill this thread."""
    if hook is None:
        return
    try:
        hook()
    except Exception:
        pass


def _new_voice():
    import comtypes.client
    return comtypes.client.CreateObject("SAPI.SpVoice")


def _run():
    """Worker thread: create the COM voice and speak queued text until stopped."""
    global _available, _error

    try:
        # COM must be initialised on every thread that uses it. comtypes does
        # this on first import, but if another thread imported it first the
        # import here is a no-op and voice creation fails with "CoInitialize
        # has not been called" -- so initialise explicitly.
        import comtypes
        comtypes.CoInitialize()
        voice = _new_voice()
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
            voice = _speak_once(voice, text)
        except Exception as e:
            # A broken voice must never crash the app, but it must not fail
            # invisibly either; the GUI polls error() and reports it.
            _error = f"{type(e).__name__}: {e}"
        finally:
            # Resume the microphone only once the queue is empty, so a run of
            # messages does not toggle it on and off between each line. This
            # runs even when speaking failed -- otherwise the app stays deaf.
            if _queue.empty():
                speaking = False
                _safely(_resume_mic)

    _safely(_resume_mic)

    try:
        import comtypes
        comtypes.CoUninitialize()
    except Exception:
        pass


def _speak_once(voice, text):
    """Speak one line. Returns the voice object to use for the next line.

    SAPI voices occasionally break silently: Speak() returns immediately
    without producing audio. When a call returns too fast to have made a
    sound, the voice is recreated and the line retried once, instead of the
    app staying mute for the rest of the session.
    """
    start = time.time()
    voice.Speak(text)

    if time.time() - start >= REAL_SPEECH_SECONDS:
        return voice

    fresh = _new_voice()
    fresh.Speak(text)
    return fresh
