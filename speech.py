"""Text-to-speech through the Windows SAPI voice.

All speech happens on one worker thread that owns the COM voice object; other
threads queue text with speak(). While something is being said, the registered
pause hook mutes the microphone so the app does not hear its own voice.
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

# A Speak() call returning faster than this cannot have produced audio; it is
# treated as a silently broken voice. See _speak_once().
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
    """Whether a voice could be created on this PC."""
    return _available


def error():
    """Description of the last speech failure. Empty when everything works."""
    return _error


def enabled():
    """Whether replies are currently being spoken."""
    return _enabled and _available


def set_enabled(value):
    """Turn speaking on or off. The `quiet` and `speak` commands call this."""
    global _enabled
    _enabled = bool(value)


def speak(text):
    """Queue text to be spoken. A no-op when speech is off or unavailable."""
    if enabled() and text:
        _queue.put(text)


def wait(timeout=60):
    """Block until everything queued so far has been spoken.

    The setup conversation needs this: it must finish asking a question
    before it starts listening for the answer, or it hears itself.

    Works by queueing a marker behind the text and waiting for the speech
    thread to reach it; FIFO order means everything ahead of it is done.
    """
    if not enabled():
        return
    reached = threading.Event()
    _queue.put(reached)
    reached.wait(timeout)


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
    """Create a SAPI voice object."""
    import comtypes.client
    return comtypes.client.CreateObject("SAPI.SpVoice")


def _run():
    """Worker thread: create the COM voice and speak queued text until stopped."""
    global _available, _error

    try:
        # COM must be initialised on every thread that uses it. comtypes does
        # this on first import, but if another thread imported it first the
        # import here is a no-op and voice creation fails with "CoInitialize
        # has not been called".
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
        item = _queue.get()

        if item is None:
            break

        if isinstance(item, threading.Event):
            # A wait() marker rather than something to say. Reaching it means
            # every line queued ahead of it has been spoken.
            item.set()
        else:
            if not speaking:
                speaking = True
                _safely(_pause_mic)

            try:
                voice = _speak_once(voice, item)
            except Exception as e:
                # A broken voice must not crash the app, but it must not fail
                # invisibly either; the GUI polls error() and reports it.
                _error = f"{type(e).__name__}: {e}"

        # Resume the microphone only once the queue is empty, so a run of
        # messages does not toggle it between each line. Outside the try
        # above, so a failed line still un-deafens the app.
        if speaking and _queue.empty():
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
    without producing audio. A call that returns too fast to have made a
    sound gets the voice recreated and the line retried once, rather than the
    app staying mute for the rest of the session.
    """
    start = time.time()
    voice.Speak(text)

    if time.time() - start >= REAL_SPEECH_SECONDS:
        return voice

    fresh = _new_voice()
    fresh.Speak(text)
    return fresh
