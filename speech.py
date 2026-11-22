"""The voice: a Kokoro voice through Moonshine, on this PC.

One worker thread owns the synthesizer and works through a queue of lines, chimes and wait
markers. The microphone is muted from the moment a line is queued until the queue is empty, so
the app never hears itself. Chimes leave it on: they transcribe as nothing, and muting for one
would lose what the user says straight after the wake word.
"""

import contextlib
import queue
import re
import threading

import models
import settings

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}

# "1:53 am", "12:05 PM", "13:45": the voice reads digits with a colon as nonsense.
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})(?:\s*([ap])\.?\s?m\b\.?)?", re.IGNORECASE)


def _number(n):
    """0 to 59 in words."""
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def _time(match):
    hour, minute, half = int(match[1]), int(match[2]), match[3]
    words = _number(hour) + (" o'clock" if minute == 0 else f" oh {_ONES[minute]}" if minute < 10
                             else f" {_number(minute)}")
    return words + (f" {half.upper()} M" if half else "")


def speakable(text):
    """Text as the voice should say it: "It's 1:53 am" -> "It's one fifty-three A M"."""
    return _TIME.sub(_time, text)

_queue = queue.Queue()
_thread = None
_tts = None
_started = threading.Event()   # loading the voice has succeeded or failed
_available = False
_failed = False
_enabled = True
_error = ""

# Queueing and pausing the microphone happen together, as do finding the queue empty and resuming
# it, so a line can never slip in between the check and the resume.
_lock = threading.Lock()
_muting = False
_pause_mic = _resume_mic = None


def on_speaking(pause, resume):
    """Register the callbacks that mute and unmute the microphone."""
    global _pause_mic, _resume_mic
    _pause_mic, _resume_mic = pause, resume


def start():
    """Load the voice in the background, once the models are on disk. Lines queued meanwhile wait."""
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_run, daemon=True, name="speech")
        _thread.start()


def ready(timeout=None):
    """Wait until the voice is loaded or has failed. True if there is one."""
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


def talking():
    """Whether anything is being said or waits to be."""
    return _muting


def speak(text):
    """Queue text to be said. A no-op when speech is off or impossible."""
    if text and _enabled:
        _put(text)


def beep_heard():
    """The chime for "I heard you": instant, where the voice takes a moment to start."""
    if settings.get("sounds"):
        _put(("beep", "success"), mute=False)


def beep_failed():
    if settings.get("sounds"):
        _put(("beep", "error"), mute=False)


def change_voice(voice):
    """Switch voices, downloading the new one if needed; lines already queued keep the old one."""
    _put(("voice", voice))


def wait(timeout=60):
    """Block until everything queued so far has been said."""
    if not _failed and _thread is not None:
        reached = threading.Event()
        _queue.put(reached)
        reached.wait(timeout)


def stop_talking():
    """Cut off what is being said, and drop everything queued after it."""
    with contextlib.suppress(queue.Empty):
        while True:
            item = _queue.get_nowait()
            if isinstance(item, threading.Event):
                item.set()
            elif item is None:
                _queue.put(None)   # a shutdown stays queued
                break
    if _tts is not None:
        with contextlib.suppress(Exception):
            _tts.stop()


def stop():
    """Finish the worker thread."""
    _queue.put(None)


def _put(item, mute=True):
    global _muting
    if _failed or _thread is None:
        return
    with _lock:
        _queue.put(item)
        if mute and not _muting:
            _muting = True
            _safely(_pause_mic)


def _safely(hook):
    if hook is not None:
        with contextlib.suppress(Exception):
            hook()


def _load(voice):
    from moonshine_voice.tts import TextToSpeech
    tts = TextToSpeech().language(models.voice_language(voice)).voice(voice).models_from(models.voices_folder())
    tts.load()
    return tts


def _run():
    global _tts, _available, _failed, _error, _muting

    models.ready()
    try:
        _tts = _load(settings.get("voice"))
        _available = True
    except Exception as e:
        _failed = True
        _error = f"{type(e).__name__}: {e}"
    _started.set()

    # A failed voice still drains the queue, so nothing waits on it forever.
    while (item := _queue.get()) is not None:
        try:
            if isinstance(item, threading.Event):
                item.set()   # a wait() marker: everything queued before it is done
            elif isinstance(item, tuple):
                _special(*item)
            elif _tts is not None:
                _tts.say(speakable(item), speed=settings.get("speed"))
                _tts.wait()
        except Exception as e:
            _error = f"{type(e).__name__}: {e}"   # the window reports it

        with _lock:
            if _muting and _queue.empty():
                _muting = False
                _safely(_resume_mic)

    _safely(_resume_mic)
    if _tts is not None:
        with contextlib.suppress(Exception):
            _tts.close()


def _special(kind, value):
    global _tts, _available
    if kind == "beep" and _tts is not None:
        # Not waited for: the synthesizer plays it while it puts the next line into words, so the
        # chime costs the reply no time.
        (_tts.play_success if value == "success" else _tts.play_error)()
    elif kind == "voice":
        models.fetch_voice(value)
        fresh = _load(value)
        old, _tts = _tts, fresh
        _available = True
        if old is not None:
            old.close()
