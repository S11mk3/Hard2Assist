"""The microphone loop.

Kept apart from both the window and the console entry point so they run exactly
the same listening code. Call run() on a background thread (the window does) or
on the main thread (console mode does).
"""

import threading
import time

import speech_recognition as sr

from output import detail, say

PREFIX = "computer"

# Short listen timeout so the loop comes back around often enough to notice a
# pause or a quit without making you wait for it.
LISTEN_TIMEOUT = 1
PHRASE_LIMIT = 8


def strip_prefix(text, required):
    """Pull the command out of what was said or typed.

    Speech has to start with the wake word, otherwise "I bought a computer
    yesterday" would set things off. Typing it is optional -- you already showed
    intent by typing in the box.
    """
    spoken = text.lower().strip()

    if spoken.startswith(PREFIX):
        return spoken[len(PREFIX):].strip(" ,.")

    return None if required else spoken


class Listener:
    """Listens, and hands recognised commands to a callback."""

    def __init__(self, on_command, on_status):
        self.on_command = on_command    # called with the command text
        self.on_status = on_status      # on_status(text, transient=False)

        self._stop = threading.Event()
        self._active = threading.Event()
        self._active.set()

        self._warned_offline = False

    # -- control, called from the window --------------------------------------

    def pause(self):
        self._active.clear()
        self.on_status("Paused")

    def resume(self):
        self._active.set()
        self.on_status("Listening")

    def stop(self):
        self._stop.set()

    @property
    def paused(self):
        return not self._active.is_set()

    # -- the loop -------------------------------------------------------------

    def run(self):
        recognizer = sr.Recognizer()

        try:
            microphone = sr.Microphone()
        except Exception as e:
            # No input device, or PyAudio missing. Hard2Assist is voice only, so
            # there is nothing it can do until that is sorted out.
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

                # Left on, the threshold drifts down until room tone counts as
                # speech, and you get an endless run of failed recognitions.
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
                continue  # silence, which is the normal case

            if self._stop.is_set():
                break

            try:
                text = recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                # A cough, a door, a bit of music. Worth a flicker in the status
                # line, not a line in the log.
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
