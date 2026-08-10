"""Microphone loop shared by the GUI and console modes.

The GUI runs Listener.run() on a background thread; console mode runs it on
the main thread. Both receive recognised commands through the same callback
interface, so the listening behaviour is identical in either mode.
"""

import os
import re
import threading
import time

import speech_recognition as sr

import settings
import speech
from output import detail, say

# A short listen timeout keeps the loop cycling frequently, so a pause or
# stop request is noticed quickly instead of blocking on the microphone.
LISTEN_TIMEOUT = 1
PHRASE_LIMIT = 8

# How long the setup conversation waits for an answer. Longer than
# LISTEN_TIMEOUT because the user is being asked a question and has to think,
# rather than the loop just sampling for a wake word.
ANSWER_TIMEOUT = 7

# Shown while the setup conversation is speaking. The main loop has not started
# yet at that point, so without a status of its own the window would keep
# reading "Calibrating..." for the whole conversation -- which looks like a
# microphone that never finished starting up.
SETUP = "Setting up"

# Silence added to both ends of a clip before it is recognised.
#
# Google returns an empty result for a short word with no silence around it:
# a bare "no" or "yeah" comes back as nothing at all rather than as a
# mishearing. listen() keeps up to non_speaking_duration (0.5s) of lead-in,
# but only if the user waited that long before speaking -- and answering the
# instant a question ends leaves almost none, which is why the setup
# conversation's yes/no questions usually took two or three goes. Half a
# second each side is enough to make them recognise first time, and it leaves
# ordinary commands unchanged.
PAD_SECONDS = 0.5


_current = None


def current():
    """The Listener that owns the microphone, or None if it is not open.

    For commands that need to hear an answer of their own -- `dictate` keeps
    listening until it is told to stop. The setup conversation reaches its
    Listener through wizard.use(), which is registered for it at startup; a
    command has nothing registered for it, and this module is the one that
    knows which Listener currently holds the microphone.

    Only ever one at a time, so a module global is the honest shape.
    """
    return _current


def strip_prefix(text, prefix):
    """Extract the command from an utterance.

    Spoken input must start with the wake word so that ordinary conversation
    ("I bought a computer yesterday") does not trigger commands. Returns the
    command text, or None when the wake word is absent.
    """
    spoken = text.lower().strip()

    if spoken.startswith(prefix):
        return spoken[len(prefix):].strip(" ,.")

    return None


def _greeting():
    """The hello spoken at launch.

    Uses the Windows account name when it reads like a name. Accounts are
    also called things like "marko-kg102", and being greeted by a login is
    worse than not being greeted by name at all.
    """
    name = os.environ.get("USERNAME", "").strip()

    if not re.fullmatch(r"[A-Za-z]{2,20}", name):
        return "Hello, what can I help with?"

    return f"Hello {name}, what can I help with?"


def _padded(audio):
    """The clip with PAD_SECONDS of silence on each end.

    See PAD_SECONDS: short answers are otherwise recognised as nothing at all.
    """
    silence = b"\x00" * int(audio.sample_rate * audio.sample_width * PAD_SECONDS)

    return sr.AudioData(
        silence + audio.frame_data + silence,
        audio.sample_rate,
        audio.sample_width,
    )


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status, on_ready=None, may_listen=None):
        self.on_command = on_command    # called with the recognised command text
        self.on_status = on_status      # on_status(text, transient=False)

        # Called once with this Listener after the microphone is calibrated and
        # before the loop starts, so the setup conversation can use the open
        # microphone before any command is accepted.
        self.on_ready = on_ready

        # Optional predicate gating whether to listen at all, separate from the
        # speech mute. Backs "only listen while I'm in focus"; consulted every
        # cycle so a change through `customize` takes effect immediately.
        self.may_listen = may_listen

        # Set once the microphone is open, so listen_once() can reuse them.
        self._recognizer = None
        self._source = None
        self._gated = False

        self._stop = threading.Event()
        self._active = threading.Event()
        self._active.set()

        # True only while the microphone loop is actually running. pause() and
        # resume() fire around every spoken reply, so without this a PC with no
        # microphone would still end up reporting "Listening".
        self._running = False

        self._warned_offline = False

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

        recognizer = sr.Recognizer()

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

                # Greet first and wait for the voice to finish, rather than
                # greeting while the measurement runs.
                # adjust_for_ambient_noise() takes the room's energy as the
                # floor for what counts as speech, so measuring with the
                # voice playing locks the threshold above anything the user
                # says afterwards -- the app would greet you and then be deaf
                # for the rest of the session.
                #
                # Skipped on first run: the setup conversation opens with a
                # hello of its own, and two in a row is one too many.
                if not settings.is_first_run():
                    say(_greeting())
                    speech.wait()

                recognizer.adjust_for_ambient_noise(source, duration=1)

                # Dynamic adjustment tends to drift the threshold down until
                # background noise registers as speech, producing an endless
                # stream of failed recognitions. Calibrate once and lock it.
                recognizer.dynamic_energy_threshold = False
                recognizer.energy_threshold = max(
                    recognizer.energy_threshold * 1.2, 300
                )

                self._recognizer = recognizer
                self._source = source

                # Published for current(), alongside the two attributes
                # listen_once() needs: from here on there is a microphone to
                # listen through.
                _current = self

                try:
                    # Setup runs while _running is still False, so the speech
                    # pause hooks stay quiet and the conversation owns the
                    # status line instead of flickering Paused/Listening.
                    if self.on_ready is not None:
                        # Calibration is over. Said explicitly because the
                        # conversation below can run for a minute, and leaving
                        # "Calibrating..." up for all of it reads as a stuck
                        # microphone.
                        self.on_status(SETUP)
                        self.on_ready(self)

                    self._running = True
                    self.on_status("Listening")
                    self._loop(recognizer, source)
                finally:
                    # Cleared before the handler below reports, so that the
                    # speech pause hooks cannot overwrite a failure message.
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
        setup conversation. Raises the speech_recognition errors, which callers
        tell apart to distinguish "unintelligible" from "no connection".
        """
        return self._recognizer.recognize_google(_padded(audio))

    def listen_once(self, timeout=ANSWER_TIMEOUT):
        """Capture one utterance with no wake word required, or None.

        For the setup conversation, which cannot require the wake word while
        it is still asking what the wake word should be. Safe to call from
        on_ready or from a command: both run on this thread, so the microphone
        source is already open and owned by the caller.
        """
        if self._recognizer is None or self._source is None:
            return None

        # The only cue the user gets that it is their turn to speak. During
        # setup the main loop is not running, so nothing else moves the status
        # line -- and a question answered before this point is not heard,
        # because the microphone is only open inside the listen() below.
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
            # Worth naming: otherwise being offline is indistinguishable from
            # mumbling, and the user retries a question that cannot succeed.
            detail(f"(could not reach the speech service: {e})")
            return None
        except Exception as e:
            detail(f"Something went wrong recognising that: {e}")
            return None

    def _loop(self, recognizer, source):
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
                audio = recognizer.listen(
                    source,
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
                # Unintelligible audio (a cough, music, a door closing).
                # Worth a brief status flicker, not a log entry.
                self.on_status("Didn't catch that", transient=True)
                continue
            except sr.RequestError as e:
                self.on_status("No connection", transient=True)
                if not self._warned_offline:
                    say("I can't reach the speech service. "
                        "Recognition needs an internet connection.")
                    detail(f"({e})")
                    self._warned_offline = True
                continue
            except Exception as e:
                detail(f"Something went wrong listening: {e}")
                continue

            self._warned_offline = False
            self.on_status(f"Heard: {text}", transient=True)

            # Read every time rather than cached, so a new wake word chosen
            # through `customize` takes effect on the very next utterance.
            command = strip_prefix(text, settings.get("prefix"))
            if command:
                self.on_command(command)
