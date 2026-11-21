"""The microphone loop, shared by the window and console modes.

The window runs Listener.run() on a background thread, console mode on the main thread. Commands
run on this thread too, one at a time, which is what lets `dictate` and the setup conversation
listen through the open microphone.

The microphone is only open while listening is allowed: under "only when in focus" it is closed
whenever another window is in front, and a missing or failed microphone is retried until one
works. Typed commands and push-to-talk work throughout.
"""

import audioop
import collections
import contextlib
import difflib
import queue
import re
import threading
import time

import speech_recognition as sr

import recognizer
import settings
import speech
import win
from output import detail, log, say, warn

LISTEN_TIMEOUT = 1    # short, so stop, pause and focus changes are noticed quickly
PHRASE_LIMIT = 8
ANSWER_TIMEOUT = 7    # how long a question waits for its answer
RETRY_SECONDS = 3     # between attempts to open a missing microphone

SETUP = "Setting up"  # the status while the setup conversation runs

# Telling speech from the room; see _threshold().
NOISE_WINDOW = 10        # seconds of recent audio the room's level is read from
NOISE_PERCENTILE = 0.3   # how far up those levels, quietest first, the room is
SPEECH_RATIO = 2.0       # how much louder than the room counts as speech
MIN_THRESHOLD = 300
CALIBRATE_SECONDS = 1.5

# Read and discarded after the voice speaks: what the microphone buffered meanwhile, and the
# room's echo. Without it the end of a question ("...or say keep") can come back as the answer.
SETTLE_SECONDS = 0.3

GREETINGS = ("hey", "hi", "hello", "ok", "okay")   # said before the wake word, not part of it
WAKE_CUTOFF = 0.75   # how close a heard word must be to the wake word to count as it

_current = None


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
    """(command, heard_as) from an utterance; command is None without a wake word.

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


@contextlib.contextmanager
def _microphone():
    """The default microphone, open. sr.Microphone swallows a stream that will not open -- no
    device, or Windows' privacy settings refusing this program -- and hands back None, which
    only fails later as a confusing AttributeError; here it is an error at once."""
    microphone = sr.Microphone()
    source = microphone.__enter__()
    if source.stream is None:   # __enter__ has already cleaned up
        raise OSError("Windows would not open the microphone")
    try:
        yield source
    finally:
        microphone.__exit__(None, None, None)


def _greeting():
    name = win.friendly_username()
    return f"Hello {name}, what can I help with?" if name else "Hello, what can I help with?"


# -- how loud counts as speech -----------------------------------------------------


class _Meter:
    """Stands in for the microphone's stream, measuring every chunk listen() reads.

    speech_recognition's own dynamic threshold only learns from chunks it has already judged
    quiet, so it can only sink, until noise counts as speech. Measuring everything -- speech,
    silence and noise -- keeps the room's level honest.
    """

    def __init__(self, source, levels):
        self._stream = source.stream
        self._width = source.SAMPLE_WIDTH
        self._chunk = source.CHUNK
        self._per_second = source.SAMPLE_RATE / source.CHUNK
        self.levels = collections.deque(levels, maxlen=max(1, int(NOISE_WINDOW * self._per_second)))

    def read(self, size):
        buffer = self._stream.read(size)
        if buffer:
            self.levels.append(audioop.rms(buffer, self._width))
        return buffer

    def measure(self, seconds):
        for _ in range(max(1, round(seconds * self._per_second))):
            self.read(self._chunk)

    def skip(self, seconds):
        for _ in range(max(1, round(seconds * self._per_second))):
            self._stream.read(self._chunk)

    def close(self):
        self._stream.close()


def _threshold(levels):
    """The loudness that counts as speech: twice the room's level, read from low down.

    A door, the television, or the commands themselves only fill the top of the range, so they
    cannot lift the threshold above a quieter voice, and they leave the window within
    NOISE_WINDOW seconds.
    """
    if not levels:
        return MIN_THRESHOLD
    ordered = sorted(levels)
    return max(MIN_THRESHOLD, ordered[int(len(ordered) * NOISE_PERCENTILE)] * SPEECH_RATIO)


# -- the listener ----------------------------------------------------------------------


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status, on_ready=None, may_listen=None, opens_with_command=None):
        self.on_command = on_command          # on_command(text)
        self.on_status = on_status            # on_status(text, transient=False)
        self.on_ready = on_ready              # on_ready(listener), once, when the microphone first opens
        self.may_listen = may_listen          # whether to listen right now: "only when in focus"
        self.opens_with_command = opens_with_command   # lets a guessed wake word count; see find_command

        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = False   # it sinks; see _Meter
        self._source = None
        self._meter = None
        self._levels = ()
        self._voice_spoke = False
        self._running = False       # the loop is listening, so pause/resume may set the status
        self._in_setup = False
        self._warned_unavailable = False
        self._logged_status = None

        self._typed = queue.Queue()
        self._wanted = threading.Event()   # push-to-talk was pressed
        self._stop = threading.Event()
        self._active = threading.Event()   # cleared while the voice speaks
        self._active.set()

    def _status(self, text, transient=False):
        """Report a status, and log each change -- not the pause around every reply."""
        if not transient and text not in ("Paused", self._logged_status):
            self._logged_status = text
            log.info("[%s]", text)
        self.on_status(text, transient)

    # -- called from other threads --

    def pause(self):
        self._active.clear()
        self._voice_spoke = True
        if self._running:
            self._status("Paused")

    def resume(self):
        self._active.set()
        if self._running:
            self._status("Listening")

    def stop(self):
        self._stop.set()

    def submit(self, text):
        """Run a typed command as if it had been said; the wake word is optional."""
        self._typed.put(text)

    def request_listen(self):
        """Push-to-talk: listen for one command without the wake word, even when unfocused."""
        self._wanted.set()

    # -- the loop --

    def run(self):
        """Listen until stop(), reopening the microphone after focus returns or it fails."""
        recognizer.start()

        spec = settings.get("hotkey")
        if spec and not win.hotkey(spec, self.request_listen):
            detail(f"(I couldn't use {spec} as the push-to-talk key: another program has it, "
                   "or it isn't a key combination.)")

        if not settings.is_first_run():   # the setup conversation says its own hello
            say(_greeting())
            speech.wait()

        failures = 0
        while self._wait_until_allowed():
            try:
                with _microphone() as source:
                    self._session(source, calibrate=self._meter is None or failures > 0)
                failures = 0
            except Exception as e:
                failures += 1
                self._lost(e, failures)

    def _session(self, source, calibrate):
        """Everything done while the microphone is open."""
        global _current
        self._meter = _Meter(source, self._levels)
        source.stream = self._meter   # closed by the Microphone on the way out, through the meter
        self._source, _current = source, self
        try:
            if calibrate:
                self._status("Calibrating for background noise...")
                self._settle()
                self._meter.measure(CALIBRATE_SECONDS)
            self._recognizer.energy_threshold = _threshold(self._meter.levels)

            if self.on_ready is not None:
                ready, self.on_ready = self.on_ready, None
                self._in_setup = True
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
            self._levels = self._meter.levels
            self._source = _current = None

    def _loop(self):
        """Listen and hand each command on, until stopped or listening stops being allowed."""
        while not self._stop.is_set():
            self._run_typed()
            if self._wanted.is_set():
                self._wanted.clear()
                self._command_without_wake_word()
                continue
            if not self._active.is_set():
                time.sleep(0.1)
                continue
            if not self._allowed():
                return

            try:
                audio = self._listen(LISTEN_TIMEOUT)
            except sr.WaitTimeoutError:
                continue
            text = None if self._stop.is_set() else self._recognise(audio)
            if text:
                self._heard(text)

    def _heard(self, text):
        prefix = settings.get("prefix")   # read every time: `customize` can change it
        command, heard_as = find_command(text, prefix, self.opens_with_command)
        if command is None:
            # Shown so that a misheard wake word looks different from a microphone hearing nothing.
            self._status(f'Heard "{text}" (no wake word)', transient=True)
            return

        self._status(f"Heard: {text}", transient=True)
        if heard_as:
            detail(f"(heard '{heard_as}', taking it as '{prefix}')")
        if command:
            self.on_command(command)
        else:
            self._command_without_wake_word()   # the wake word on its own

    def _command_without_wake_word(self):
        """Answer "Yes?" and take the next thing said as the command."""
        say("Yes?")
        speech.wait()
        text = self.listen_once(timeout=5)
        if text:
            self._run_text(text)

    def _run_typed(self):
        while True:
            try:
                text = self._typed.get_nowait()
            except queue.Empty:
                return
            self._run_text(text)

    def _run_text(self, text):
        """Run text as a command, taking off the wake word if it was said or typed anyway."""
        command = _after_prefix(text.strip(), settings.get("prefix"))
        command = text.strip() if command is None else command
        if command:
            self.on_command(command)

    def _wait_until_allowed(self):
        """Wait, microphone closed, until listening is allowed. False once stopped."""
        said = False
        while not self._stop.is_set():
            self._run_typed()
            if self._wanted.is_set() or self._allowed():
                return True
            if not said:
                said = True
                self._status("Not in focus")
            time.sleep(0.2)
        return False

    def _lost(self, error, failures):
        """The microphone is missing or stopped: say so once, then wait before trying again."""
        log.error("Microphone: %s", error)
        if failures == 1:
            if self._meter is None:
                self._status("No microphone found")
                warn("I could not open a microphone. Plug one in and I'll pick it up.")
                detail("If one is plugged in, check Windows Settings > Privacy & security > Microphone "
                       "lets apps use it.")
            else:
                self._status("Microphone stopped")
                warn("The microphone stopped working. I'll keep trying to reconnect.")
            detail(f"({error})")

        until = time.monotonic() + RETRY_SECONDS
        while time.monotonic() < until and not self._stop.is_set():
            self._run_typed()
            time.sleep(0.2)

    def _allowed(self):
        if self.may_listen is None:
            return True
        try:
            return bool(self.may_listen())
        except Exception:
            return True   # a broken gate must never leave the app deaf

    def _settle(self):
        """Let the voice's last words clear the microphone -- only if it just spoke, or dictation,
        which listens again the moment a line is typed, would lose the start of each sentence."""
        if self._voice_spoke:
            self._voice_spoke = False
            self._meter.skip(SETTLE_SECONDS)

    def _listen(self, timeout, phrase_limit=PHRASE_LIMIT):
        """Capture one phrase, then re-read the room's level. Raises what listen() raises."""
        self._settle()
        try:
            return self._recognizer.listen(self._source, timeout=timeout, phrase_time_limit=phrase_limit)
        finally:
            self._recognizer.energy_threshold = _threshold(self._meter.levels)

    def _recognise(self, audio):
        """The text in a clip, or None: unintelligible, or nothing can recognise speech (said once)."""
        try:
            text = recognizer.transcribe(self._recognizer, audio)
        except sr.UnknownValueError:
            self._status("Didn't catch that", transient=True)   # a cough, music, a door
            return None
        except sr.RequestError as e:
            self._status("Can't recognise speech", transient=True)
            if not self._warned_unavailable:
                self._warned_unavailable = True
                warn("I can't recognise speech right now.")
                detail(f"({e})")
            return None
        except Exception as e:
            log.exception("Recognition failed")
            detail(f"Something went wrong recognising that: {e}")
            return None

        self._warned_unavailable = False
        return text

    def listen_once(self, timeout=ANSWER_TIMEOUT, phrase_limit=PHRASE_LIMIT):
        """One utterance with no wake word needed, or None. For a command or the setup
        conversation, which run on this thread while the microphone is open."""
        if self._source is None:
            return None

        self._status("Listening")   # the only cue that it is the user's turn
        try:
            audio = self._listen(timeout, phrase_limit)
        except sr.WaitTimeoutError:
            return None
        finally:
            if self._in_setup:
                self._status(SETUP)
        return self._recognise(audio)
