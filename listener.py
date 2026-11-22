"""Listening: Moonshine hears everything on this PC, and lines that open with the wake word become
commands.

Moonshine's streaming transcriber does the hard part: it tells speech from noise by itself, shows
a line's text while it is still being said, and finishes the line when the speaker pauses. The
listener decides which finished lines are commands, and runs them one at a time on its own
thread -- which is what lets `dictate` and the setup conversation wait for the next line.
"""

import array
import difflib
import os
import queue
import re
import threading
import time
import wave

import apps
import models
import registry
import settings
import speech
import win
from output import detail, log, say, warn

ANSWER_TIMEOUT = 7    # how long a question waits for its answer to start
LONGEST_LINE = 20     # how long one started past that may still run on
RETRY_SECONDS = 3     # between attempts to open a missing microphone
UPDATE_SECONDS = 0.25 # how often the text of a line still being said is refreshed

# Kept muted this long after the voice stops, so its echo off the walls is not heard as speech.
SETTLE_SECONDS = 0.3

SETUP = "Setting up"  # the status while the setup conversation runs

GREETINGS = ("hey", "hi", "hello", "ok", "okay")   # said before the wake word, not part of it
WAKE_CUTOFF = 0.75   # how close a heard word must be to the wake word to count as it

_current = None

# A folder to keep every finished line's sound in, with what was heard -- for measuring how well
# speech is recognised on a real voice and microphone. Set by `hard2assist.py --record`.
RECORD_TO = None


def current():
    """The Listener whose microphone is open, or None. For `dictate` and the setup conversation."""
    return _current


# -- the wake word --------------------------------------------------------------


def _after_prefix(text, prefix):
    """The text after the wake word, if it opens with the wake word as a whole word, else None.
    ("max" must not fire on "maximize notepad".)"""
    match = re.match(rf"{re.escape(prefix)}(?:$|[\s,.!?]+)(.*)", text, re.IGNORECASE | re.DOTALL)
    return None if match is None else match.group(1).strip()


def _sounds_like(heard, prefix):
    """Whether a heard word is the wake word misheard. One that merely starts with it is a
    different word: "computers are slow" is about computers."""
    heard, prefix = heard.lower(), prefix.lower()
    if heard != prefix and heard.startswith(prefix):
        return False
    return difflib.SequenceMatcher(None, heard, prefix).ratio() >= WAKE_CUTOFF


def _misheard_prefix(text, prefix):
    """Each (command, as heard) the text could be, opening with the wake word misheard as one
    word ("commuter") or split into two ("compute her"). Both are offered; the command check
    decides."""
    words = list(re.finditer(r"[\w']+", text))[:2]
    if not words or words[0].start() > 0:
        return
    for count in (1, 2):
        if len(words) >= count and _sounds_like("".join(word.group() for word in words[:count]), prefix):
            end = words[count - 1].end()
            yield text[end:].lstrip(" ,.!?"), text[:end].lower()


def find_command(text, prefix, opens_with_command=None):
    """(command, heard_as) from a line; command is None without a wake word.

    The wake word must come first, so conversation ("I bought a computer yesterday") does nothing.
    Spelled exactly at the start it always counts. Because recognition gets it wrong -- background
    speech before it, an accent, a clipped start -- it is also looked for at the start of every
    sentence, after a "hey", and misheard; those are guesses, so they only count when
    opens_with_command() says a command follows. heard_as is what was taken for a misheard wake
    word. The command keeps its case and punctuation, for `type`.
    """
    text = text.strip()
    command = _after_prefix(text, prefix)
    if command is not None:
        return command, None
    if opens_with_command is None:
        return None, None

    greeting = rf"^(?:{'|'.join(GREETINGS)})[\s,.!?]+"
    for start in [0] + [match.end() for match in re.finditer(r"[.!?]+\s+", text)]:
        sentence = re.sub(greeting, "", text[start:], flags=re.IGNORECASE)
        exact = _after_prefix(sentence, prefix)
        candidates = [(exact, None)] if exact is not None else _misheard_prefix(sentence, prefix)
        for command, heard_as in candidates:
            if command and opens_with_command(command):
                return command, heard_as
    return None, None


def _record(line):
    """Save a finished line's sound (16 kHz mono, as Moonshine hears it) and its text."""
    os.makedirs(RECORD_TO, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S-") + f"{int(time.time() * 1000) % 1000:03d}"
    pcm = array.array("h", (max(-32767, min(32767, int(sample * 32767))) for sample in line.audio_data))
    with wave.open(os.path.join(RECORD_TO, name + ".wav"), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(pcm.tobytes())
    with open(os.path.join(RECORD_TO, "heard.tsv"), "a", encoding="utf-8") as f:
        f.write(f"{name}.wav\t{line.text}\n")


def vocabulary():
    """The words this app listens for: command names, aliases and synonyms (lowercase, as they
    should come out), and the names of the apps it can open (as they are written)."""
    words = {word for word in registry.command_words() if len(word) > 2}
    names = {app.title for app in apps.all_apps() if app.title and len(app.title) < 30}
    return sorted(words) + sorted(names)


def _greeting():
    name = win.friendly_username()
    return f"Hello {name}, what can I help with?" if name else "Hello, what can I help with?"


class _LevelTap(queue.Queue):
    """Stands in for MicTranscriber's audio queue, measuring each block's loudness on its way to
    the transcriber -- for the dock's live waveform. Blocks arrive as (samples, rate)."""

    def __init__(self, on_level):
        super().__init__()
        self._on_level = on_level

    def put(self, item, block=True, timeout=None):
        if isinstance(item, tuple):
            samples = item[0]
            self._on_level(float((samples * samples).mean()) ** 0.5 if len(samples) else 0.0)
        super().put(item, block, timeout)


# -- the listener ----------------------------------------------------------------------


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status, on_ready=None, opens_with_command=None,
                 on_partial=None, on_level=None, on_download=None):
        self.on_command = on_command          # on_command(text)
        self.on_status = on_status            # on_status(text, transient=False)
        self.on_ready = on_ready              # on_ready(listener), once, when the microphone first opens
        self.opens_with_command = opens_with_command   # lets a guessed wake word count; see find_command
        self.on_partial = on_partial          # on_partial(text): a command still being said
        self.on_level = on_level              # on_level(0..1): how loud the microphone is
        self.on_download = on_download        # on_download(0..1): first-launch download progress

        self._mic = None
        self._keyterm = None
        self._lines = queue.Queue()   # finished lines, or the exception that broke the microphone
        self._typed = queue.Queue()
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._expecting = False       # listen_once() is waiting: show everything heard
        self._vocabulary = True       # see use_vocabulary()
        self._last_partial = 0.0      # when text of a line still being said last arrived
        self._in_setup = False
        self._running = False         # the loop is listening, so pause/resume may set the status
        self._logged_status = None

    def _status(self, text, transient=False):
        """Report a status, and log each change -- not the pause around every reply."""
        if not transient and text not in ("Speaking", self._logged_status):
            self._logged_status = text
            log.info("[%s]", text)
        self.on_status(text, transient)

    # -- called from other threads --

    def pause(self):
        """The voice is about to talk: stop hearing until it is done."""
        if self._mic is not None:
            self._mic.mute(True)
        if self._running:
            self._status("Speaking")

    def resume(self):
        time.sleep(SETTLE_SECONDS)
        if self._mic is not None:
            self._mic.mute(False)
        if self._running:
            self._status("Listening")

    def stop(self):
        self._stop.set()

    def submit(self, text):
        """Run a typed command as if it had been said; the wake word is optional."""
        self._typed.put(text)

    def reopen(self):
        """Close the microphone and open it again: a different one was chosen."""
        self._reopen.set()

    # -- the loop --

    def run(self):
        """Get the models, open the microphone, and listen until stop()."""
        threading.Thread(target=models.prepare, args=(self._downloading, self._download_failed),
                         daemon=True, name="download").start()
        while not models.ready(0.2):   # typed commands still work meanwhile
            if self._stop.is_set():
                return
            self._run_typed()

        path, arch = models.speech_model()
        if not settings.is_first_run():   # the setup conversation says its own hello
            say(_greeting())

        failures = 0
        while not self._stop.is_set():
            try:
                self._session(path, arch, retrying=failures > 0)
                failures = 0
            except Exception as e:
                failures += 1
                self._lost(e, failures)

    def _downloading(self, fraction):
        if self.on_download is not None:
            self.on_download(fraction)
        self._status("Downloading" if fraction < 1 else "Getting ready")

    def _download_failed(self, error, first):
        self._status("Can't download")
        if first:
            warn("I need the internet once, to download my hearing and my voice. I'll keep trying.")
            detail(f"({error})")

    def _session(self, path, arch, retrying=False):
        """Everything done while the microphone is open. Raises when it fails."""
        global _current
        from moonshine_voice.mic_transcriber import MicTranscriber

        if not retrying:   # while waiting for a microphone, "No microphone" stays up
            self._status("Getting ready")
        mic = (MicTranscriber().language(models.LANGUAGE).model_arch(arch).models_from(path)
               .update_interval(UPDATE_SECONDS).device(settings.get("microphone") or None))
        mic.on_text(self._partial)
        mic.on_line(self._finished)
        mic.on_error(self._lines.put)
        mic.load()
        if self.on_level is not None:
            mic._audio_queue = _LevelTap(self.on_level)   # before start(), which starts its reader
        self._mic = mic
        self._update_keyterm()
        mic.mute(speech.talking())   # the greeting may already be playing
        try:
            mic.start()
            _current = self
            if self.on_ready is not None:
                ready, self.on_ready = self.on_ready, None
                self._in_setup = True
                if settings.is_first_run():   # otherwise there is nothing to set up
                    self._status(SETUP)
                try:
                    ready(self)
                finally:
                    self._in_setup = False

            self._running = True
            self._status("Listening")
            self._loop()
        finally:
            self._running = False
            _current = self._mic = None
            mic.close()

    def _finished(self, line):
        if RECORD_TO and line.audio_data:
            _record(line)
        self._lines.put(line.text)

    def use_vocabulary(self, on):
        """Lean towards the app's vocabulary (on), or towards ordinary speech: dictation, where the
        names of commands and apps would come out capitalised mid-sentence."""
        self._vocabulary = on
        if self._mic is not None:
            self._update_keyterm()

    def _update_keyterm(self):
        """Lean the recogniser towards what is said to this app: the wake word, which may be an
        unusual word ("jarvis"), the commands, and the apps' names. On recordings of a real,
        accented voice this took the right command from 83% to 91% of the time."""
        terms = [settings.get("prefix")] + (vocabulary() if self._vocabulary else [])
        if terms != self._keyterm:
            self._keyterm = terms
            self._mic.set_keyterms(terms)

    def _loop(self):
        while not self._stop.is_set():
            if self._reopen.is_set():
                self._reopen.clear()
                return
            self._run_typed()
            text = self._next_line(0.1)
            if text:
                self._heard(text)
                self._update_keyterm()   # `customize` may have changed it

    def _next_line(self, timeout):
        """The next finished line, or None after timeout. Raises what broke the microphone."""
        try:
            item = self._lines.get(timeout=timeout)
        except queue.Empty:
            return None
        if isinstance(item, BaseException):
            raise item
        return item.strip()

    def _partial(self, text):
        """A line still being said. Shown only once it is a command, or while an answer is
        expected: everything else heard is nobody's business."""
        self._last_partial = time.monotonic()
        if self.on_partial is not None and (self._expecting or _after_prefix(text.strip(), settings.get("prefix"))
                                            is not None):
            self.on_partial(text)

    def _heard(self, text):
        prefix = settings.get("prefix")
        command, heard_as = find_command(text, prefix, self.opens_with_command)
        if command is None:
            # Shown so that a misheard wake word looks different from a microphone hearing nothing.
            self._status(f'Heard "{text}" (no wake word)', transient=True)
            return

        self._status(f"Heard: {text}", transient=True)
        if heard_as:
            detail(f"(heard '{heard_as}', taking it as '{prefix}')")
        if command:
            speech.beep_heard()   # plays while the reply is still being put into words
            self.on_command(command)
        else:
            self._command_without_wake_word()

    def _command_without_wake_word(self):
        """The wake word on its own: chime, and take the next thing said as the command -- which
        may already be on its way, so nothing waits for the chime and nothing heard is dropped."""
        speech.beep_heard()
        text = self.listen_once(timeout=5, fresh=False)
        if text:
            self._run_text(text)

    def _run_typed(self):
        while True:
            try:
                text = self._typed.get_nowait()
            except queue.Empty:
                return
            speech.stop_talking()   # a new command interrupts whatever is being said
            self._run_text(text)

    def _run_text(self, text):
        """Run text as a command, taking off the wake word if it was said or typed anyway."""
        command = _after_prefix(text.strip(), settings.get("prefix"))
        command = text.strip() if command is None else command
        if command:
            self.on_command(command)

    def _lost(self, error, failures):
        """The microphone is missing or stopped: say so once, then wait before trying again."""
        log.error("Microphone: %s", error)
        if failures == 1:
            self._status("No microphone")
            warn("I can't hear anything: no microphone is working. Plug one in and I'll pick it up.")
            detail("If one is plugged in, check Windows Settings > Privacy & security > Microphone "
                   f"lets apps use it. ({error})")

        until = time.monotonic() + RETRY_SECONDS
        while time.monotonic() < until and not self._stop.is_set():
            self._run_typed()
            time.sleep(0.2)

    def listen_once(self, timeout=ANSWER_TIMEOUT, fresh=True):
        """The next line said, with no wake word needed, or None. For a command or the setup
        conversation, which run on this thread while the microphone is open.

        fresh: lines finished before now were said before the question, so are not its answer.
        """
        if self._mic is None:
            return None

        while fresh and not self._lines.empty():
            self._next_line(0)

        self._status("Listening")   # the only cue that it is the user's turn
        self._expecting = True
        try:
            # Past the timeout, an answer already being said still gets to finish.
            until, latest = time.monotonic() + timeout, time.monotonic() + timeout + LONGEST_LINE
            while time.monotonic() < latest:
                text = self._next_line(0.2)
                if text:
                    return text
                if time.monotonic() > until and time.monotonic() - self._last_partial > 1:
                    return None
            return None
        finally:
            self._expecting = False
            if self._in_setup:
                self._status(SETUP)
