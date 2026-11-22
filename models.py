"""The speech model and the voice: downloaded on first launch, then used offline for good.

They live in %LOCALAPPDATA%\\Hard2Assist\\models. Run from source they go in the project's models\\
folder instead, because the Microsoft Store's Python redirects writes under %LOCALAPPDATA% in a way
that breaks the downloader.
"""

import logging
import os
import threading
import time
from pathlib import Path

import settings
import storage
import win

log = logging.getLogger("hard2assist")   # output's logger; output itself imports this module's importers

LANGUAGE = "en"
RETRY_SECONDS = 15
SPEECH_SHARE = 0.7   # of the progress bar: the speech model is most of the download

_ready = threading.Event()


def load_library():
    """Load Moonshine's native library, once, before any thread needs it.

    Its loader is not thread-safe: it registers itself before the DLL has finished loading, so a
    second thread arriving meanwhile finds no library -- which the voice and the listener, both
    starting at launch, would otherwise race into.
    """
    from moonshine_voice import list_tts_languages
    list_tts_languages()


def folder():
    return os.path.join(storage.LOCAL_DIR if storage.FROZEN else storage.BUNDLE_DIR, "models")


def voices_folder():
    return os.path.join(folder(), "voices")


def voice_language(voice):
    """The catalogue language a voice is published under: the British ones under en_gb."""
    return "en_gb" if voice.startswith(("kokoro_bf_", "kokoro_bm_", "piper_en_GB")) else "en_us"


def speech_model(on_progress=None):
    """(folder, arch) of the recognition model, downloading it the first time.

    Moonshine's medium streaming model: its recommended English one, and on a 2014 laptop CPU it
    finishes a line a fraction of a second after the speaker stops.
    """
    from moonshine_voice import ModelArch, get_model_for_language

    saved = os.path.join(folder(), "speech.txt")
    try:
        with open(saved, encoding="utf-8") as f:
            path = f.read().strip()
        if os.path.isdir(path):
            return path, ModelArch.MEDIUM_STREAMING   # no need to ask the server again
    except OSError:
        pass

    path, arch = get_model_for_language(LANGUAGE, ModelArch.MEDIUM_STREAMING,
                                        cache_root=os.path.join(folder(), "speech"), on_progress=on_progress)
    with open(saved, "w", encoding="utf-8") as f:
        f.write(str(path))
    return path, arch


def fetch_voice(voice, on_progress=None):
    """Make sure a voice and what it needs are on disk, downloading what is missing."""
    from moonshine_voice import ensure_tts_voice_downloaded
    os.makedirs(voices_folder(), exist_ok=True)
    ensure_tts_voice_downloaded(voice_language(voice), voice, Path(voices_folder()), download_missing=True,
                                show_progress=False, on_progress=on_progress)


def voices():
    """[(id, label)] of every Kokoro voice: "kokoro_am_fenrir" -> "Fenrir (American man)"."""
    from moonshine_voice import list_tts_voices

    found = []
    for language in ("en_us", "en_gb"):
        listed = list_tts_voices(language, root_path=Path(voices_folder()))
        for voice in sorted(set(listed["present"]) | set(listed["downloadable"])):
            parts = voice.split("_")
            if parts[0] == "kokoro" and len(parts) == 3 and len(parts[1]) == 2:
                accent = "American" if parts[1][0] == "a" else "British"
                person = "woman" if parts[1][1] == "f" else "man"
                found.append((voice, f"{parts[2].capitalize()} ({accent} {person})"))
    return found


def prepare(on_progress, on_problem):
    """Get the speech model and the chosen voice onto this PC, retrying until it works.

    Blocking; run on a thread of its own. on_progress(0..1) follows the download, and
    on_problem(error, first) is told of each failed attempt. ready() is set when done.
    """
    first = True
    while not _ready.is_set():
        try:
            win.prevent_sleep(True)   # a laptop going to sleep mid-download would start it over
            speech_model(lambda done, _file: on_progress(SPEECH_SHARE * done))
            fetch_voice(settings.get("voice"),
                        lambda done, _file: on_progress(SPEECH_SHARE + (1 - SPEECH_SHARE) * done))
            on_progress(1.0)
            _ready.set()
        except Exception as e:
            log.exception("Could not get the speech models")
            on_problem(e, first)
            first = False
            time.sleep(RETRY_SECONDS)
        finally:
            win.prevent_sleep(False)


def ready(timeout=None):
    return _ready.wait(timeout)
