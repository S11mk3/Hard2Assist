"""Text-to-speech through the Windows SAPI voice.

One worker thread owns the COM voice; other threads queue text with speak(). The microphone is
paused from the moment a line is queued until the queue is empty, so the app never hears itself.
"""

import contextlib
import queue
import threading
import time

import settings

# A Speak() that returns faster than this made no sound: the voice broke silently, and is
# recreated rather than leaving the app mute for the rest of the session.
REAL_SPEECH_SECONDS = 0.05

_queue = queue.Queue()
_thread = None
_started = threading.Event()   # creating the voice has succeeded or failed
_available = False
_failed = False
_enabled = True
_error = ""

# Queueing a line and pausing the microphone happen together, as do finding the queue empty and
# resuming it, so a line can never be queued between the check and the resume.
_lock = threading.Lock()
_muting = False
_pause_mic = _resume_mic = None


def on_speaking(pause, resume):
    """Register the callbacks that mute and unmute the microphone."""
    global _pause_mic, _resume_mic
    _pause_mic, _resume_mic = pause, resume


def start():
    """Create the voice in the background. Lines queued meanwhile are spoken once it exists."""
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_run, daemon=True, name="speech")
        _thread.start()


def ready(timeout=15):
    """Wait until the voice exists or has failed. True if there is one."""
    _started.wait(timeout)
    return _available


def started():
    return _started.is_set()


def available():
    return _available


def error():
    """The last speech failure, or ""."""
    return _error


def enabled():
    return _enabled and _available


def set_enabled(value):
    """Turn speaking on or off; `quiet` and `speak` call this."""
    global _enabled
    _enabled = bool(value)


def speak(text):
    """Queue text to be spoken. A no-op when speech is off or impossible."""
    global _muting
    if not text or not _enabled or _failed or _thread is None:
        return
    with _lock:
        _queue.put(text)
        if not _muting:
            _muting = True
            _safely(_pause_mic)


def wait(timeout=60):
    """Block until everything queued so far has been spoken."""
    if not _enabled or _failed or _thread is None:
        return
    reached = threading.Event()
    _queue.put(reached)
    reached.wait(timeout)


def stop():
    _queue.put(None)


def _safely(hook):
    if hook is not None:
        with contextlib.suppress(Exception):
            hook()


def _new_voice():
    """A SAPI voice, the one named by the `voice` setting if it is installed."""
    import comtypes.client
    voice = comtypes.client.CreateObject("SAPI.SpVoice")

    wanted = settings.get("voice").lower()
    if wanted:
        voices = voice.GetVoices()
        for i in range(voices.Count):
            if wanted in voices.Item(i).GetDescription().lower():
                voice.Voice = voices.Item(i)
                break
    return voice


def _run():
    """Worker thread: create the voice, then speak the queue until stop()."""
    global _available, _failed, _error, _muting

    voice = None
    try:
        import comtypes
        comtypes.CoInitialize()   # needed on every thread that uses COM
        voice = _new_voice()
        _available = True
    except Exception as e:
        _failed = True
        _error = f"{type(e).__name__}: {e}"
    _started.set()

    # A failed voice still drains the queue, so nothing waits on it forever.
    while (item := _queue.get()) is not None:
        if isinstance(item, threading.Event):
            item.set()   # a wait() marker: everything queued before it is done
        elif voice is not None:
            try:
                voice = _speak_once(voice, item)
            except Exception as e:
                _error = f"{type(e).__name__}: {e}"   # the window reports it

        with _lock:
            if _muting and _queue.empty():
                _muting = False
                _safely(_resume_mic)

    _safely(_resume_mic)
    del voice   # released before COM is shut down on this thread
    with contextlib.suppress(Exception):
        import comtypes
        comtypes.CoUninitialize()


def _speak_once(voice, text):
    """Speak one line. Returns the voice to use next: a fresh one if this one has gone mute."""
    for retry in (False, True):
        if retry:
            voice = _new_voice()
        voice.Rate = settings.get("voice_rate")
        began = time.monotonic()
        voice.Speak(text)
        if time.monotonic() - began >= REAL_SPEECH_SECONDS:
            break
    return voice
