"""How finished lines become commands, and how the models get onto the PC. The microphone, the
voice and the network are faked."""

import os
import threading
import time

import numpy
import pytest

import listener
import models
import registry
import speech


class _Mic:
    def __init__(self):
        self.muted = []

    def mute(self, on=True):
        self.muted.append(on)


@pytest.fixture
def ears(commands, monkeypatch):
    ran, partials = [], []
    monkeypatch.setattr(speech, "stop_talking", lambda: None)
    monkeypatch.setattr(speech, "beep_heard", lambda: None)
    monkeypatch.setattr(speech, "wait", lambda timeout=60: None)
    monkeypatch.setattr(listener, "SETTLE_SECONDS", 0)
    it = listener.Listener(on_command=ran.append, on_status=lambda text, transient=False: None,
                           opens_with_command=registry.opens_with_command, on_partial=partials.append)
    it.ran, it.partials = ran, partials
    return it


def test_a_line_opening_with_the_wake_word_runs_its_command(ears):
    ears._heard("Computer, open Notepad.")
    ears._heard("I bought a computer yesterday.")
    assert ears.ran == ["open Notepad."]


def test_the_wake_word_alone_takes_the_next_line_as_the_command(ears):
    ears._mic = _Mic()
    threading.Timer(0.1, lambda: ears._lines.put("What time is it?")).start()
    ears._heard("Computer.")
    assert ears.ran == ["What time is it?"]


def test_only_commands_are_shown_while_being_said(ears):
    ears._partial("Computer, open")
    ears._partial("and then she said")
    ears._expecting = True   # an answer is awaited: everything counts
    ears._partial("keep")
    assert ears.partials == ["Computer, open", "keep"]


def test_an_answer_is_the_next_line_not_one_already_said(ears):
    ears._mic = _Mic()
    ears._lines.put("said before the question")
    threading.Timer(0.1, lambda: ears._lines.put("jarvis")).start()
    assert ears.listen_once(timeout=2) == "jarvis"
    assert ears.listen_once(timeout=0.2) is None


def test_an_answer_still_being_said_at_the_timeout_gets_to_finish(ears):
    ears._mic = _Mic()

    def talk():   # starts inside the timeout, finishes well after it
        for _ in range(6):
            ears._partial("what's the")
            time.sleep(0.1)
        ears._lines.put("What's the date today?")

    threading.Timer(0.15, talk).start()
    assert ears.listen_once(timeout=0.3) == "What's the date today?"


def test_a_broken_microphone_surfaces_from_the_line_queue(ears):
    ears._lines.put(OSError("unplugged"))
    with pytest.raises(OSError):
        ears._next_line(0)


def test_typed_commands_run_with_or_without_the_wake_word(ears):
    ears.submit("computer what time is it")
    ears.submit("open notepad")
    ears._run_typed()
    assert ears.ran == ["what time is it", "open notepad"]


def test_it_does_not_hear_itself(ears):
    ears._mic = _Mic()
    ears.pause()
    ears.resume()
    assert ears._mic.muted == [True, False]


def test_microphone_levels_are_measured_on_the_way_through():
    levels = []
    tap = listener._LevelTap(levels.append)
    tap.put((numpy.array([0.5, -0.5, 0.5, -0.5], dtype=numpy.float32), 16000))
    tap.put(None)   # the reader's shutdown sentinel passes untouched
    assert levels == [pytest.approx(0.5)]
    assert tap.qsize() == 2


@pytest.mark.parametrize("voice, language", [
    ("kokoro_am_fenrir", "en_us"), ("kokoro_bm_george", "en_gb"), ("kokoro_bf_emma", "en_gb"),
])
def test_voice_languages(voice, language):
    assert models.voice_language(voice) == language


def test_the_speech_model_is_found_without_asking_the_server(tmp_path, monkeypatch):
    model = tmp_path / "speech" / "medium"
    model.mkdir(parents=True)
    (tmp_path / "speech.txt").write_text(str(model), encoding="utf-8")
    monkeypatch.setattr(models, "folder", lambda: str(tmp_path))
    assert models.speech_model()[0] == str(model)


def test_the_download_retries_until_it_works(monkeypatch):
    attempts, problems, progress = [], [], []

    def speech_model(on_progress=None):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("no internet")
        on_progress(1.0, "model")

    monkeypatch.setattr(models, "speech_model", speech_model)
    monkeypatch.setattr(models, "fetch_voice", lambda voice, on_progress=None: None)
    monkeypatch.setattr(models, "RETRY_SECONDS", 0)
    monkeypatch.setattr(models.win, "prevent_sleep", lambda on: None)
    monkeypatch.setattr(models, "_ready", threading.Event())

    models.prepare(progress.append, lambda error, first: problems.append(first))
    assert models.ready(0)
    assert problems == [True]                     # said once, on the first failure
    assert progress[-1] == 1.0 and len(attempts) == 2


def test_models_go_beside_the_source_when_run_from_it():
    assert models.folder() == os.path.join(models.storage.BUNDLE_DIR, "models")


def test_lines_are_timed_out_promptly(ears):
    ears._mic = _Mic()
    started = time.monotonic()
    assert ears.listen_once(timeout=0.3) is None
    assert time.monotonic() - started < 1


def test_a_chime_leaves_the_microphone_on_but_a_reply_mutes_it(monkeypatch):
    import queue as q
    paused = []
    monkeypatch.setattr(speech, "_queue", q.Queue())
    monkeypatch.setattr(speech, "_thread", object())   # as if started
    monkeypatch.setattr(speech, "_muting", False)
    monkeypatch.setattr(speech, "_pause_mic", lambda: paused.append(True))
    speech.beep_heard()
    assert paused == []          # chimes transcribe as nothing; muting would lose the next words
    speech.speak("Opening notepad")
    assert paused == [True]


def test_it_leans_towards_its_vocabulary_except_while_dictating(ears, monkeypatch):
    class Mic(_Mic):
        terms = None

        def set_keyterms(self, terms):
            self.terms = terms

    monkeypatch.setattr(listener, "vocabulary", lambda: ["open", "Notepad"])
    ears._mic = Mic()
    ears._update_keyterm()
    assert ears._mic.terms == ["computer", "open", "Notepad"]
    ears.use_vocabulary(False)
    assert ears._mic.terms == ["computer"]


def test_the_vocabulary_holds_commands_and_app_names(commands):
    words = listener.vocabulary()
    assert "close" in words and "volume" in words and "Notepad" in words
