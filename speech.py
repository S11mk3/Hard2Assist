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

START_TIMEOUT = 15

REAL_SPEECH_SECONDS = 0.15


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

    _ready.wait(timeout=START_TIMEOUT)
    return _available


def available():
    return _available


def error():
    """Why speech is not working. Empty when it is fine."""
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


def _safely(hook):
    """Run a pause/resume hook without letting it kill this thread."""
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
    global _available, _error

    try:
        # COM has to be switched on for each thread that uses it. comtypes does
        # that when it is first imported -- but if anything else imported it
        # first, on another thread, the import here is a no-op and everything
        # fails with "CoInitialize has not been called". So ask explicitly.
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
            # A broken voice must never take the app down, but it must not be
            # invisible either.
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

    _safely(_resume_mic)

    try:
        import comtypes
        comtypes.CoUninitialize()
    except Exception:
        pass


def _speak_once(voice, text):
    """Say one line. Returns the voice to use next time.

    If a call returns too fast to have made a sound, the voice object is
    replaced and the line tried once more, rather than the app going silently
    mute for the rest of the session.
    """
    start = time.time()
    voice.Speak(text)

    if time.time() - start >= REAL_SPEECH_SECONDS:
        return voice

    fresh = _new_voice()
    fresh.Speak(text)
    return fresh
