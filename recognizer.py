"""Turning captured audio into text.

Local by default: Moonshine, a speech model that runs on this PC, so nothing
said leaves it and no internet is needed. Google's free speech service is the
fallback for a PC where the model is missing or will not load. The
`recognizer` setting picks:

    auto     Moonshine, or Google if Moonshine is unavailable   (the default)
    local    Moonshine only
    google   Google only

The model loads on a background thread when the microphone opens. It takes a
second or two, which calibrating the microphone covers.
"""

import array
import os
import sys
import threading

import speech_recognition as sr

import settings
from output import detail

# The model folder under models/, in the source tree and in the build alike.
# Moonshine small: fast enough on a 2014 laptop CPU to answer as quickly as
# Google does, at 139 MB. build.py --fetch-model puts it there.
MODEL = "moonshine-small-en"

# What Moonshine takes: 16 kHz mono floats.
SAMPLE_RATE = 16000

# How long a transcription waits for the model to finish loading before giving
# up on it. Loading takes a second or two; this only matters on a PC so slow
# or so short of memory that it never finishes.
LOAD_TIMEOUT = 30

# Silence added to both ends of a clip before Google recognises it.
#
# Google returns an empty result for a short word with no silence around it: a
# bare "no" or "yeah" comes back as nothing rather than as a mishearing.
# listen() keeps up to 0.5s of lead-in, but only if the user waited that long
# before speaking, and answering the instant a question ends leaves almost
# none. Half a second each side leaves ordinary commands unchanged. Moonshine
# does not need it.
PAD_SECONDS = 0.5

_transcriber = None
_problem = ""
_loaded = threading.Event()
_thread = None


def model_dir():
    """Where the model is: inside the bundle when built, else the source tree."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "models", MODEL)


def start():
    """Begin loading the model in the background. Safe to call more than once.

    Skipped when the setting is `google`: the model would only take up memory.
    """
    global _thread

    if _thread is None and settings.get("recognizer") != "google":
        _thread = threading.Thread(target=_load, daemon=True)
        _thread.start()


def is_local():
    """Whether speech is being recognised on this PC rather than by Google."""
    return _transcriber is not None and settings.get("recognizer") != "google"


def transcribe(recognizer, audio):
    """The text in an sr.AudioData clip.

    Raises sr.UnknownValueError when there is no speech in it, and
    sr.RequestError when no recogniser can be reached -- the errors the
    listener already tells apart.
    """
    mode = settings.get("recognizer")

    if mode != "google":
        transcriber = _local()
        if transcriber is not None:
            return _moonshine(transcriber, audio)

        if mode == "local":
            raise sr.RequestError(
                f"the offline speech model isn't available: {_problem}")

    try:
        return recognizer.recognize_google(_padded(audio))
    except sr.RequestError as e:
        if mode == "google":
            raise
        raise sr.RequestError(
            "the offline speech model isn't available, and Google's speech "
            f"service can't be reached either: {e}") from e


def _local():
    """The loaded Moonshine transcriber, or None if there isn't one."""
    if _thread is None:
        return None

    _loaded.wait(LOAD_TIMEOUT)
    return _transcriber


def _load():
    """Load the model. Runs on its own thread; see start()."""
    global _transcriber, _problem

    try:
        path = model_dir()
        if not os.path.isdir(path):
            hint = ("" if getattr(sys, "frozen", False)
                    else " -- run: python build.py --fetch-model")
            raise FileNotFoundError(f"there is no model at {path}{hint}")

        # Imported here, not at the top: a PC that cannot load the library
        # still gets Google instead of failing to start.
        from moonshine_voice.moonshine_api import ModelArch
        from moonshine_voice.transcriber import Transcriber

        _transcriber = Transcriber(model_path=path,
                                   model_arch=ModelArch.SMALL_STREAMING)
    except Exception as e:
        _problem = f"{type(e).__name__}: {e}"

        if settings.get("recognizer") == "auto":
            detail("I couldn't load the offline speech model, so I'm using "
                   "Google's speech service, which needs the internet.")
        detail(f"({_problem})")
    finally:
        _loaded.set()


def _moonshine(transcriber, audio):
    """Recognise a clip with Moonshine.

    Moonshine skips anything that is not speech -- a cough, a knock, typing --
    and returns no text for it, so there is no need to screen the clip first.
    """
    raw = audio.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)

    # 16-bit samples to floats in -1..1. Done without numpy, which would add
    # far more to the build than this saves.
    pcm = array.array("h")
    pcm.frombytes(raw)
    samples = [sample / 32768.0 for sample in pcm]

    result = transcriber.transcribe_without_streaming(samples,
                                                      sample_rate=SAMPLE_RATE)

    text = " ".join(line.text.strip() for line in result.lines).strip()
    if not text:
        raise sr.UnknownValueError()

    return text


def _padded(audio):
    """The clip with PAD_SECONDS of silence on each end. See PAD_SECONDS."""
    silence = b"\x00" * int(audio.sample_rate * audio.sample_width * PAD_SECONDS)

    return sr.AudioData(
        silence + audio.frame_data + silence,
        audio.sample_rate,
        audio.sample_width,
    )
