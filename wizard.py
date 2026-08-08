"""The spoken setup conversation.

Runs once on first launch, and again whenever the user says `customize`.

Two rules shape everything here. Every choice is explained aloud and read back
for confirmation, because a voice interface has no other way to show what it
understood. And no question can trap the user: after three failed attempts it
keeps the current value, says so, and moves on, so a poor microphone costs the
user a setting rather than the whole app.

Questions are asked without the wake word -- one of the things being chosen is
the wake word, so requiring it would be circular.
"""

import settings
import speech
from output import detail, say

# How many times a question is asked before its current value is kept.
ATTEMPTS = 3

YES = {"yes", "yeah", "yep", "yup", "correct", "right", "sure", "ok", "okay",
       "confirm", "affirmative", "that's right", "thats right", "do it"}

NO = {"no", "nope", "nah", "wrong", "incorrect", "negative", "cancel",
       "not right", "no thanks"}

# Said in answer to a question to leave that setting alone.
KEEP = {"keep", "keep it", "skip", "same", "unchanged", "next", "leave it",
        "no change"}


def _speak(text):
    """Say something, then wait for the voice to finish.

    Every prompt goes through here: speak() only queues, so without the wait
    the question and the listening for its answer would overlap and the
    assistant would hear itself.
    """
    say(text)
    speech.wait()


def _hear(ears):
    """One spoken answer, lowercased, or None."""
    heard = ears.listen_once()
    if not heard:
        return None
    answer = heard.strip().lower().strip(" ,.!?")
    detail(f"  > {answer}")
    return answer


def _confirm(ears, question):
    """Ask a yes/no question. True, False, or None if not understood."""
    for attempt in range(ATTEMPTS):
        _speak(question if attempt == 0 else "Was that a yes or a no?")
        answer = _hear(ears)
        if answer is None:
            continue
        if answer in YES:
            return True
        if answer in NO:
            return False
        # A one-word answer buried in a longer one still counts.
        if any(word in YES for word in answer.split()):
            return True
        if any(word in NO for word in answer.split()):
            return False
    return None


def _ask(ears, opening, retry, interpret):
    """Ask a question until it is understood, or give up after ATTEMPTS.

    `interpret` turns a heard phrase into a value, or returns None if it does
    not recognise it. Returns the confirmed value, or None to keep the current
    setting.
    """
    for attempt in range(ATTEMPTS):
        _speak(opening if attempt == 0 else retry)

        answer = _hear(ears)
        if answer is None:
            continue

        if answer in KEEP:
            return None

        value, spoken_back = interpret(answer)
        if value is None:
            continue

        confirmed = _confirm(ears, spoken_back)
        if confirmed:
            return value
        if confirmed is False:
            # Understood, but wrong. Spend the next attempt re-asking.
            continue
        return None

    return None


# -- the questions -----------------------------------------------------------


def _ask_prefix(ears):
    current = settings.get("prefix")

    def interpret(answer):
        word = answer.split()[0] if answer.split() else ""
        if not settings.valid_prefix(word):
            return None, ""
        return word, f"I heard {word}. Should I answer to {word} from now on?"

    opening = (f"First, the wake word. Right now I answer to {current}. "
               f"Say a single word you would like to use instead, "
               f"or say keep to leave it as {current}.")
    retry = "Sorry, I need a single word, at least three letters. Once more?"

    chosen = _ask(ears, opening, retry, interpret)

    if chosen is None:
        _speak(f"Keeping {current}.")
        return

    settings.set("prefix", chosen)
    _speak(f"Done. Say {chosen} before every command from now on.")


def _ask_listening(ears):
    if ears.may_listen is None:
        # Console mode has no window, so there is nothing to be in focus and
        # the setting would have no effect whichever way it were answered.
        return

    current = settings.get("listen_when")
    now = ("all the time" if current == "always"
           else "only while my window is in focus")

    def interpret(answer):
        words = answer.split()
        if any(w in ("always", "all", "everything", "background", "anytime",
                     "constantly") for w in words):
            return "always", ("I heard always. Should I keep listening even "
                              "when my window is minimised?")
        if any(w in ("focus", "focused", "focussed", "window", "only",
                     "selected", "open") for w in words):
            return "focused", ("I heard only when in focus. Should I listen "
                               "only while my window is in front?")
        return None, ""

    opening = (
        "Next, when should I listen. I can listen all the time, even when my "
        "window is minimised, which is hands free but means the microphone is "
        "always on. Or I can listen only while my window is in focus, which is "
        "more private but means you have to click me first. "
        f"Right now I listen {now}. Say always, or say only when in focus, "
        "or say keep."
    )
    retry = "Sorry. Say always, or say only when in focus."

    chosen = _ask(ears, opening, retry, interpret)

    if chosen is None:
        _speak(f"Keeping it as it is. I listen {now}.")
        return

    settings.set("listen_when", chosen)
    if chosen == "always":
        _speak("Done. I'll listen all the time.")
    else:
        _speak("Done. I'll only listen while my window is in focus.")


# -- entry points ------------------------------------------------------------

QUESTIONS = (_ask_prefix, _ask_listening)

# The Listener to ask through. Registered at startup, the same way output.py
# and ask.py take their handler, so the `customize` command can start a
# conversation without the command contract having to carry a Listener.
_ears = None


def use(ears):
    """Register the Listener the conversation listens through."""
    global _ears
    _ears = ears


def on_ready(ears):
    """The Listener's on_ready hook: remember it, and set up on first run."""
    use(ears)
    if settings.is_first_run():
        run(first_time=True)


def run(first_time=False):
    """Walk the user through the settings."""
    ears = _ears
    if ears is None:
        detail("Setup needs the microphone, which is not running.")
        return

    if not speech.available():
        # The whole conversation is spoken. Without a voice the user would be
        # answering questions they cannot hear, so keep the defaults instead.
        detail("No voice on this PC, so setup was skipped and the defaults "
               "were kept. Settings live in " + settings.FILE)
        settings.save()
        return

    if first_time:
        _speak("Hello. I'm Hard2Assist, and this is the first time you've run "
               "me, so let's set a few things up. You can say keep at any "
               "point to leave something as it is.")
    else:
        _speak("Let's go through your settings. Say keep to leave one alone.")

    for question in QUESTIONS:
        question(ears)

    # Written even when nothing changed, so the file exists and first run is
    # not offered again.
    settings.save()

    prefix = settings.get("prefix")
    _speak(f"All done. Say {prefix} help to hear what I can do, "
           f"or {prefix} customize to change these again.")
