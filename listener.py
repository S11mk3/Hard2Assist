"""The microphone loop, shared by the GUI and console modes.

The GUI runs Listener.run() on a background thread; console mode runs it on
the main thread. Both receive recognised commands through the same callbacks,
so listening behaves identically either way.
"""

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


def strip_prefix(text, prefix):
    """Extract the command from an utterance.

    Spoken input must start with the wake word, so that ordinary conversation
    ("I bought a computer yesterday") does not trigger commands. Returns the
    command text, or None when the wake word is absent.

    The wake word must be a whole word: "computers open notepad" is not a
    command, and with a short wake word like "max", "maximize notepad" would
    otherwise fire as "imize notepad".

    The command keeps its case and punctuation -- "Computer, type Hello
    there." gives "type Hello there." -- so `type` can type it as heard. The
    registry does its own matching on a cleaned-up copy.
    """
    match = re.match(rf"{re.escape(prefix)}(?:$|[\s,.!?]+)(.*)",
                     text.strip(), re.IGNORECASE)

    if match is None:
        return None

    return match.group(1).strip()


def _greeting():
    """The hello spoken at launch.

    Uses the Windows account name when it reads like a name; see
    win.friendly_username(), which `stop`'s goodbye shares.
    """
    name = win.friendly_username()

    if not name:
        return "Hello, what can I help with?"

    return f"Hello {name}, what can I help with?"


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status, on_ready=None, may_listen=None):
        self.on_command = on_command    # called with the recognised command text
        self.on_status = on_status      # on_status(text, transient=False)

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
        self._gated = False

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
                self.on_status("Calibrating for background noise...")

                # Greeting first, and waiting for it to finish, keeps the
                # voice out of the measurement below.
                #
                # Skipped on first run: the setup conversation opens with a
                # hello of its own.
                if not settings.is_first_run():
                    say(_greeting())
                    speech.wait()

                # Takes the room's energy as the floor for what counts as
                # speech. Measuring while the voice plays would lock the
                # threshold above anything said afterwards.
                sr_recognizer.adjust_for_ambient_noise(source, duration=1)

                # Dynamic adjustment drifts the threshold down until
                # background noise registers as speech, producing an endless
                # stream of failed recognitions. Calibrate once and lock it.
                sr_recognizer.dynamic_energy_threshold = False
                sr_recognizer.energy_threshold = max(
                    sr_recognizer.energy_threshold * 1.2, 300
                )

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
            audio = self._recognizer.listen(
                self._source, timeout=timeout, phrase_time_limit=PHRASE_LIMIT
            )
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
                audio = self._recognizer.listen(
                    self._source,
                    timeout=LISTEN_TIMEOUT,
                    phrase_time_limit=PHRASE_LIMIT,
                )
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
            self.on_status(f"Heard: {text}", transient=True)

            # Read every time rather than cached, so a new wake word chosen
            # through `customize` takes effect on the next utterance.
            command = strip_prefix(text, settings.get("prefix"))
            if command:
                self.on_command(command)
