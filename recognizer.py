"""Turning captured audio into text.

Moonshine, a speech model that runs on this PC, by default: offline, and nothing said leaves the
machine. Google's free speech service is the fallback where the model is missing or will not
load. The `recognizer` setting chooses:

    auto     Moonshine, or Google if Moonshine is unavailable   (the default)
    local    Moonshine only
    google   Google only

The model loads on a background thread while the microphone calibrates, which takes about as long.
"""

import array
import os
import threading

import speech_recognition as sr

import settings
import storage
from output import detail

SAMPLE_RATE = 16000   # Moonshine takes 16 kHz mono floats

# How long a transcription waits for the model to load before giving up on it; only reached on
# a PC too slow or short of memory to load it at all.
LOAD_TIMEOUT = 30

# Silence added to both ends of a clip for Google, which returns nothing for a short word with
# no silence around it -- a bare "no" answered the instant a question ends.
PAD_SECONDS = 0.5

_transcriber = None
_problem = ""
_loaded = threading.Event()
_thread = None


def start():
    """Begin loading the model, unless the setting is `google`. Safe to call more than once."""
    global _thread
    if _thread is None and settings.get("recognizer") != "google":
        _thread = threading.Thread(target=_load, daemon=True, name="speech model")
        _thread.start()


def is_local():
    """Whether speech is being recognised on this PC rather than by Google."""
    return _transcriber is not None and settings.get("recognizer") != "google"


def transcribe(recognizer, audio):
    """The text in an sr.AudioData clip.

    Raises sr.UnknownValueError when there is no speech in it, and sr.RequestError when nothing
    can recognise speech right now; the listener tells the two apart.
    """
    mode = settings.get("recognizer")

    if mode != "google":
        transcriber = _local()
        if transcriber is not None:
            return _moonshine(transcriber, audio)
        if mode == "local":
            raise sr.RequestError(f"the offline speech model isn't available: {_problem}")

    try:
        return recognizer.recognize_google(_padded(audio))
    except sr.RequestError as e:
        if mode == "google":
            raise
        raise sr.RequestError("the offline speech model isn't available, and Google's speech "
                              f"service can't be reached either: {e}") from e


def _local():
    if _thread is None:
        return None
    _loaded.wait(LOAD_TIMEOUT)
    return _transcriber


def _load():
    global _transcriber, _problem
    try:
        path = storage.model_dir()
        if not os.path.isdir(path):
            hint = "" if storage.FROZEN else " -- run: python build.py --fetch-model"
            raise FileNotFoundError(f"there is no model at {path}{hint}")

        # Imported here, so a PC that cannot load the library still gets Google.
        from moonshine_voice.moonshine_api import ModelArch
        from moonshine_voice.transcriber import Transcriber

        _transcriber = Transcriber(model_path=path, model_arch=ModelArch.SMALL_STREAMING)
    except Exception as e:
        _problem = f"{type(e).__name__}: {e}"
        if settings.get("recognizer") == "auto":
            detail("I couldn't load the offline speech model, so I'm using Google's speech "
                   "service, which needs the internet.")
        detail(f"({_problem})")
    finally:
        _loaded.set()


def _moonshine(transcriber, audio):
    """Recognise a clip with Moonshine, which returns no text for coughs, knocks and typing."""
    pcm = array.array("h")
    pcm.frombytes(audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2))
    # 16-bit samples to floats in -1..1, without numpy, which would add far more to the build.
    samples = [sample / 32768.0 for sample in pcm]

    result = transcriber.transcribe_without_streaming(samples, sample_rate=SAMPLE_RATE)
    text = " ".join(line.text.strip() for line in result.lines).strip()
    if not text:
        raise sr.UnknownValueError()
    return text


def _padded(audio):
    silence = b"\x00" * int(audio.sample_rate * audio.sample_width * PAD_SECONDS)
    return sr.AudioData(silence + audio.frame_data + silence, audio.sample_rate, audio.sample_width)
