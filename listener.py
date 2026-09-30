"""The microphone loop, shared by the GUI and console modes.

The GUI runs Listener.run() on a background thread; console mode runs it on
the main thread. Both receive recognised commands through the same callbacks,
so listening behaves identically either way.
"""

import audioop
import collections
import difflib
import re
import threading
import time

import speech_recognition as sr

import recognizer
import settings
import speech
import win
from output import detail, say

# A short listen timeout keeps the loop cycling, so a pause or stop request is
# noticed quickly instead of blocking on the microphone.
LISTEN_TIMEOUT = 1
PHRASE_LIMIT = 8

# How long the setup conversation waits for an answer. Longer than
# LISTEN_TIMEOUT, because the user is answering a question rather than the
# loop sampling for a wake word.
ANSWER_TIMEOUT = 7

# The status shown while the setup conversation is speaking. The main loop has
# not started at that point, so without it the window would read
# "Calibrating..." for the whole conversation.
SETUP = "Setting up"

# Telling speech from the room; see _threshold().
NOISE_WINDOW = 10        # seconds of recent audio the room's level is read from
NOISE_PERCENTILE = 0.3   # how far up those levels, quietest first, the room is
SPEECH_RATIO = 2.0       # how much louder than the room counts as speech
MIN_THRESHOLD = 300      # the floor, however quiet the room
CALIBRATE_SECONDS = 1.5  # the first measurement, before anything is said

# Read and thrown away after the voice speaks: what the microphone buffered
# while it talked, and the room's echo of it. Without this the last word of a
# setup question -- "...or say keep" -- can come back as the answer.
SETTLE_SECONDS = 0.3

# Said in front of the wake word without being part of the command.
GREETINGS = ("hey", "hi", "hello", "ok", "okay")

# How close a heard word must be to the wake word to be taken for it. The same
# cutoff registry.py uses for command names.
WAKE_CUTOFF = 0.75


_current = None


def current():
    """The Listener that owns the microphone, or None if it is not open.

    For code that needs to hear an answer of its own: `dictate` keeps
    listening until it is told to stop, and the setup conversation asks its
    questions through it. Set before on_ready runs, so first-run setup finds
    it too.

    Only ever one at a time, so a module global is the honest shape.
    """
    return _current


def _after_prefix(text, prefix):
    """The text after the wake word, if the text opens with it, else None.

    The wake word must be a whole word: with a short wake word like "max",
    "maximize notepad" would otherwise fire as "imize notepad".
    """
    match = re.match(rf"{re.escape(prefix)}(?:$|[\s,.!?]+)(.*)", text,
                     re.IGNORECASE | re.DOTALL)
    return None if match is None else match.group(1).strip()


def _sounds_like(heard, prefix):
    """Whether a heard word is the wake word, misheard.

    A word that merely starts with the wake word is a different word, not a
    mishearing of it: "computers are slow" is a sentence about computers.
    """
    heard, prefix = heard.lower(), prefix.lower()
    if heard != prefix and heard.startswith(prefix):
        return False
    return difflib.SequenceMatcher(None, heard, prefix).ratio() >= WAKE_CUTOFF


def _misheard_prefix(text, prefix):
    """Each (command, as heard) the text could be, opening with the wake word
    misheard: as one word ("commuter"), or as two the recogniser split it
    into ("compute her").

    Both are offered, because both can pass: "compute" is close enough on its
    own, and only the command check tells "her, open notepad" from "open
    notepad".
    """
    words = list(re.finditer(r"[\w']+", text))[:2]

    for count in (1, 2):
        if len(words) < count or words[0].start() > 0:
            return
        heard = "".join(word.group() for word in words[:count])
        if _sounds_like(heard, prefix):
            end = words[count - 1].end()
            yield text[end:].lstrip(" ,.!?"), text[:end].lower()


def find_command(text, prefix, opens_with_command=None):
    """Extract the command from an utterance.

    Returns (command, heard_as). command is None when there is no wake word.
    heard_as is what was taken for the wake word when it was not heard as
    itself -- "commuter" -- and None when it was.

    The wake word has to come first, so that ordinary conversation ("I bought
    a computer yesterday") does not trigger commands. Opening the utterance,
    spelled exactly, it always counts, as it always has.

    The recogniser gets it wrong often enough for that to fail people, though:
    a noisy room puts the background in front of it ("The game's on.
    Computer, volume up."), an accent turns it into "commuter", and a quiet
    start loses its first syllable. So it is also looked for at the start of
    every sentence, after a "hey" or "okay", and misheard. Those only count
    when `opens_with_command` says the rest starts like a command, because
    they are guesses; without it only the exact wake word works.

    The command keeps its case and punctuation -- "Computer, type Hello
    there." gives "type Hello there." -- so `type` can type it as heard. The
    registry does its own matching on a cleaned-up copy.
    """
    text = text.strip()

    command = _after_prefix(text, prefix)
    if command is not None:
        return command, None

    if opens_with_command is None:
        return None, None

    starts = [0] + [match.end() for match in re.finditer(r"[.!?]+\s+", text)]
    greeting = rf"(?:{'|'.join(GREETINGS)})[\s,.!?]+"

    for start in starts:
        sentence = text[start:]
        sentence = re.sub(rf"^{greeting}", "", sentence, flags=re.IGNORECASE)

        exact = _after_prefix(sentence, prefix)
        if exact is not None:
            candidates = [(exact, None)]
        else:
            candidates = _misheard_prefix(sentence, prefix)

        for command, heard_as in candidates:
            if command and opens_with_command(command):
                return command, heard_as

    return None, None


def _greeting():
    """The hello spoken at launch.

    Uses the Windows account name when it reads like a name; see
    win.friendly_username(), which `stop`'s goodbye shares.
    """
    name = win.friendly_username()

    if not name:
        return "Hello, what can I help with?"

    return f"Hello {name}, what can I help with?"


class _Meter:
    """The microphone's stream, remembering how loud everything read was.

    Stands in for sr.Microphone's own stream, which listen() reads a chunk at
    a time, so every chunk is measured -- speech, silence and noise alike.
    That is what makes the room's level trustworthy. speech_recognition's own
    dynamic threshold learns only from chunks it has already judged quieter
    than the threshold, so it can only ever learn that the room is quieter
    than it thought, and it sinks until the noise counts as speech.
    """

    def __init__(self, stream, sample_width, chunk, rate):
        self._stream = stream
        self._width = sample_width
        self._chunk = chunk
        self._per_second = rate / chunk
        self.levels = collections.deque(
            maxlen=max(1, int(NOISE_WINDOW * self._per_second)))

    def read(self, size):
        buffer = self._stream.read(size)
        if buffer:
            self.levels.append(audioop.rms(buffer, self._width))
        return buffer

    def measure(self, seconds):
        """Listen to the room for a while, keeping only its levels."""
        for _ in range(max(1, round(seconds * self._per_second))):
            self.read(self._chunk)

    def skip(self, seconds):
        """Read and discard, without measuring."""
        for _ in range(max(1, round(seconds * self._per_second))):
            self._stream.read(self._chunk)

    def close(self):
        self._stream.close()


def _threshold(levels):
    """The loudness that counts as speech, from the room's recent levels.

    The room is read from low down the levels rather than their average.
    A door, a burst of television, a friend talking while the app starts, or
    the commands themselves only ever fill the top of the range, so none of
    them can lift the threshold above a quieter voice -- and when one happens
    anyway, it has left the window within NOISE_WINDOW seconds. Even steady
    dictation leaves the gaps between words at the room's level.
    """
    if not levels:
        return MIN_THRESHOLD

    ordered = sorted(levels)
    room = ordered[int(len(ordered) * NOISE_PERCENTILE)]
    return max(MIN_THRESHOLD, room * SPEECH_RATIO)


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status, on_ready=None, may_listen=None,
                 opens_with_command=None):
        self.on_command = on_command    # called with the recognised command text
        self.on_status = on_status      # on_status(text, transient=False)

        # Optional predicate: whether some text starts the way a command does.
        # Lets a misheard or late wake word count; see find_command().
        self.opens_with_command = opens_with_command

        # Called once with this Listener after the microphone is calibrated
        # and before the loop starts, so the setup conversation can use the
        # open microphone before any command is accepted.
        self.on_ready = on_ready

        # Optional predicate gating whether to listen at all, separate from
        # the speech mute. Backs "only listen while I'm in focus"; consulted
        # every cycle, so a change through `customize` takes effect at once.
        self.may_listen = may_listen

        # Set once the microphone is open, so listen_once() can reuse them.
        self._recognizer = None
        self._source = None
        self._meter = None
        self._gated = False

        # Set whenever the voice starts speaking, so the next listen first
        # lets the room fall quiet; see SETTLE_SECONDS.
        self._voice_spoke = False

        self._stop = threading.Event()
        self._active = threading.Event()
        self._active.set()

        # True only while the microphone loop is actually running. pause() and
        # resume() fire around every spoken reply, so without this a PC with
        # no microphone would still report "Listening".
        self._running = False

        self._warned_unavailable = False

    # -- control, called from other threads -----------------------------------

    def pause(self):
        """Stop capturing audio until resume() is called."""
        self._active.clear()
        self._voice_spoke = True
        if self._running:
            self.on_status("Paused")

    def resume(self):
        """Start capturing audio again after pause()."""
        self._active.set()
        if self._running:
            self.on_status("Listening")

    def stop(self):
        """Shut the loop down; run() returns shortly after."""
        self._stop.set()

    # -- the loop --------------------------------------------------------------

    def run(self):
        """Open the microphone and listen until stop() is called."""
        global _current

        # Loads while the microphone calibrates, which takes about as long.
        recognizer.start()

        sr_recognizer = sr.Recognizer()

        try:
            microphone = sr.Microphone()
        except Exception as e:
            # No input device, or PyAudio is missing. Hard2Assist is voice
            # only, so there is nothing to do until a microphone is available.
            self.on_status("No microphone found")
            say("I could not find a microphone, and I only take voice commands.")
            detail("Plug one in, check it is enabled in Windows sound settings, "
                   "then start Hard2Assist again.")
            detail(f"({e})")
            return

        try:
            with microphone as source:
                # Everything listen() reads from here on passes through the
                # meter, so the threshold can follow the room. The Microphone
                # closes it on the way out, and the meter passes that on.
                self._meter = _Meter(source.stream, source.SAMPLE_WIDTH,
                                     source.CHUNK, source.SAMPLE_RATE)
                source.stream = self._meter

                self.on_status("Calibrating for background noise...")

                # Greeting first, and waiting for it to finish, keeps the
                # voice out of the measurement below.
                #
                # Skipped on first run: the setup conversation opens with a
                # hello of its own.
                if not settings.is_first_run():
                    say(_greeting())
                    speech.wait()

                # A first measure of the room, so the threshold is sensible
                # before anything is said. It used to be the only one: taken
                # in a single second and locked, so a loud moment while the
                # app started left it deaf to quieter voices for the whole
                # session. Now it is only a start; _listen() keeps
                # re-reading the room.
                self._settle()
                self._meter.measure(CALIBRATE_SECONDS)

                # speech_recognition's own adjustment is left off: it sinks
                # until noise counts as speech. See _Meter.
                sr_recognizer.dynamic_energy_threshold = False
                sr_recognizer.energy_threshold = _threshold(self._meter.levels)

                self._recognizer = sr_recognizer
                self._source = source

                # Published for current(): from here on there is a microphone
                # to listen through.
                _current = self

                try:
                    # Setup runs while _running is still False, so the speech
                    # pause hooks stay quiet and the conversation owns the
                    # status line.
                    if self.on_ready is not None:
                        # Calibration is over. Said explicitly because the
                        # conversation can run for a minute, and leaving
                        # "Calibrating..." up reads as a stuck microphone.
                        self.on_status(SETUP)
                        self.on_ready(self)

                    self._running = True
                    self.on_status("Listening")
                    self._loop()
                finally:
                    # Cleared before the handler below reports, so the speech
                    # pause hooks cannot overwrite a failure message.
                    self._running = False
                    _current = None
        except Exception as e:
            self.on_status("Microphone stopped")
            say(f"The microphone stopped working: {e}")

    def _allowed(self):
        """Whether the may_listen gate currently permits listening."""
        if self.may_listen is None:
            return True
        try:
            return bool(self.may_listen())
        except Exception:
            # A broken gate must never leave the app permanently deaf.
            return True

    def _transcribe(self, audio):
        """Turn captured audio into text.

        The single point where recognition happens, for both the loop and the
        setup conversation; see recognizer.py for which engine does it. Raises
        the speech_recognition errors, which callers tell apart to distinguish
        "unintelligible" from "nothing can recognise speech right now".
        """
        return recognizer.transcribe(self._recognizer, audio)

    def _settle(self):
        """Let the voice's last words clear the microphone, if it just spoke.

        Only then: dictation listens again the moment a line is typed, and a
        pause on every listen would cut the start off the next sentence.
        """
        if self._voice_spoke:
            self._voice_spoke = False
            self._meter.skip(SETTLE_SECONDS)

    def _listen(self, timeout):
        """Capture one phrase, then re-read the room's level.

        The single point audio is captured, for the loop and listen_once()
        alike, so the threshold keeps following the room however the app is
        listening. Raises what listen() raises.
        """
        self._settle()
        try:
            return self._recognizer.listen(
                self._source, timeout=timeout, phrase_time_limit=PHRASE_LIMIT
            )
        finally:
            self._recognizer.energy_threshold = _threshold(self._meter.levels)

    def listen_once(self, timeout=ANSWER_TIMEOUT):
        """Capture one utterance with no wake word required, or None.

        For the setup conversation, which cannot require the wake word while
        it is still asking what the wake word should be. Safe to call from
        on_ready or from a command: both run on this thread, so the source is
        already open and owned by the caller.
        """
        if self._recognizer is None or self._source is None:
            return None

        # The only cue the user gets that it is their turn to speak. During
        # setup the main loop is not running, so nothing else moves the status
        # line -- and the microphone is only open inside the listen() below.
        self.on_status("Listening")

        try:
            audio = self._listen(timeout)
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            detail(f"Something went wrong listening: {e}")
            return None
        finally:
            # Back to the setup status while the answer is recognised. Only
            # during setup: once the loop owns the status line it puts
            # "Listening" back itself.
            if not self._running:
                self.on_status(SETUP)

        try:
            return self._transcribe(audio)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            # Named, because otherwise a recogniser that cannot run is
            # indistinguishable from mumbling, and the user retries a
            # question that cannot succeed.
            detail(f"(speech recognition isn't working: {e})")
            return None
        except Exception as e:
            detail(f"Something went wrong recognising that: {e}")
            return None

    def _loop(self):
        """Listen, recognise, and hand each command to the callback."""
        while not self._stop.is_set():
            if not self._active.is_set():
                time.sleep(0.1)
                continue

            if not self._allowed():
                # "Only listen while I'm in focus", and we are not in front.
                if not self._gated:
                    self._gated = True
                    self.on_status("Not in focus")
                time.sleep(0.2)
                continue

            if self._gated:
                self._gated = False
                self.on_status("Listening")

            try:
                audio = self._listen(LISTEN_TIMEOUT)
            except sr.WaitTimeoutError:
                # Silence; the normal case.
                continue

            if self._stop.is_set():
                break

            try:
                text = self._transcribe(audio)
            except sr.UnknownValueError:
                # Unintelligible audio: a cough, music, a door closing. Worth
                # a brief status flicker, not a log entry.
                self.on_status("Didn't catch that", transient=True)
                continue
            except sr.RequestError as e:
                # No recogniser can run: the offline model is unavailable and
                # Google cannot be reached, or is not allowed. recognizer.py
                # words the reason.
                self.on_status("Can't recognise speech", transient=True)
                if not self._warned_unavailable:
                    say("I can't recognise speech right now.")
                    detail(f"({e})")
                    self._warned_unavailable = True
                continue
            except Exception as e:
                detail(f"Something went wrong listening: {e}")
                continue

            self._warned_unavailable = False

            # Read every time rather than cached, so a new wake word chosen
            # through `customize` takes effect on the next utterance.
            prefix = settings.get("prefix")
            command, heard_as = find_command(text, prefix,
                                             self.opens_with_command)

            if command is None:
                # Said, so that someone whose wake word keeps being misheard
                # can see that they were heard -- otherwise it looks exactly
                # like a microphone that picks up nothing.
                self.on_status(f'Heard "{text}" (no wake word)',
                               transient=True)
                continue

            self.on_status(f"Heard: {text}", transient=True)

            if command:
                if heard_as:
                    detail(f"(heard '{heard_as}', taking it as '{prefix}')")
                self.on_command(command)
