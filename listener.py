"""Microphone loop shared by the GUI and console modes.

The GUI runs Listener.run() on a background thread; console mode runs it on
the main thread. Both receive recognised commands through the same callback
interface, so the listening behaviour is identical in either mode.
"""

import threading
import time

import speech_recognition as sr

from output import detail, say

PREFIX = "computer"

# A short listen timeout keeps the loop cycling frequently, so a pause or
# stop request is noticed quickly instead of blocking on the microphone.
LISTEN_TIMEOUT = 1
PHRASE_LIMIT = 8


def strip_prefix(text, required):
    """Extract the command from an utterance.

    Spoken input must start with the wake word so that ordinary conversation
    ("I bought a computer yesterday") does not trigger commands. When
    ``required`` is False the prefix is optional, which suits typed input.
    Returns the command text, or None if the wake word was required and absent.
    """
    spoken = text.lower().strip()

    if spoken.startswith(PREFIX):
        return spoken[len(PREFIX):].strip(" ,.")

    return None if required else spoken


class Listener:
    """Listens on the microphone and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status):
        self.on_command = on_command    # called with the recognised command text
        self.on_status = on_status      # on_status(text, transient=False)

        self._stop = threading.Event()
        self._active = threading.Event()
        self._active.set()

        self._warned_offline = False

    # -- control, called from other threads -----------------------------------

    def pause(self):
        """Stop capturing audio until resume() is called."""
        self._active.clear()
        self.on_status("Paused")

    def resume(self):
        """Start capturing audio again after pause()."""
        self._active.set()
        self.on_status("Listening")

    def stop(self):
        """Shut the loop down; run() returns shortly after."""
        self._stop.set()

    @property
    def paused(self):
        return not self._active.is_set()

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

                self.on_status("Listening")
                self._loop(recognizer, source)
        except Exception as e:
            self.on_status("Microphone stopped")
            say(f"The microphone stopped working: {e}")

    def _loop(self, recognizer, source):
        while not self._stop.is_set():
            if not self._active.is_set():
                time.sleep(0.1)
                continue

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
                text = recognizer.recognize_google(audio)
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

            command = strip_prefix(text, required=True)
            if command:
                self.on_command(command)
