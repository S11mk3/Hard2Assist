"""Microphone loop shared by the GUI and console modes.

The GUI runs Listener.run() on a background thread; console mode runs it on
the main thread. Both receive recognised commands through the same callback
interface, so the listening behaviour is identical in either mode.
"""

import threading
import time

import speech_recognition as sr

import settings
from output import detail, say

# A short listen timeout keeps the loop cycling frequently, so a pause or
# stop request is noticed quickly instead of blocking on the microphone.
LISTEN_TIMEOUT = 1
PHRASE_LIMIT = 8

# How long the setup conversation waits for an answer. Longer than
# LISTEN_TIMEOUT because the user is being asked a question and has to think,
# rather than the loop just sampling for a wake word.
ANSWER_TIMEOUT = 7


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

                try:
                    # Setup runs while _running is still False, so the speech
                    # pause hooks stay quiet and the conversation owns the
                    # status line instead of flickering Paused/Listening.
                    if self.on_ready is not None:
                        self.on_ready(self)

                    self._running = True
                    self.on_status("Listening")
                    self._loop(recognizer, source)
                finally:
                    # Cleared before the handler below reports, so that the
                    # speech pause hooks cannot overwrite a failure message.
                    self._running = False
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
        return self._recognizer.recognize_google(audio)

    def listen_once(self, timeout=ANSWER_TIMEOUT):
        """Capture one utterance with no wake word required, or None.

        For the setup conversation, which cannot require the wake word while
        it is still asking what the wake word should be. Safe to call from
        on_ready or from a command: both run on this thread, so the microphone
        source is already open and owned by the caller.
        """
        if self._recognizer is None or self._source is None:
            return None

        try:
            audio = self._recognizer.listen(
                self._source, timeout=timeout, phrase_time_limit=PHRASE_LIMIT
            )
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            detail(f"Something went wrong listening: {e}")
            return None

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
