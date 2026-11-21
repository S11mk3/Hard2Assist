"""The spoken setup conversation: on first launch, and whenever the user says `customize`.

Every answer is read back and confirmed, since a voice interface has no other way to show what
it understood, and no question can trap the user: after three failed tries the current value is
kept. Questions need no wake word, because the wake word is one of the things being chosen.
"""

import re

import listener
import registry
import settings
import speech
from output import detail, say

ATTEMPTS = 3

YES = {"yes", "yeah", "yep", "yup", "correct", "right", "sure", "ok", "okay", "confirm",
       "affirmative", "that's right", "thats right", "do it"}

# "know" and "now" are what the recogniser returns for a spoken "no" often enough to count.
NO = {"no", "nope", "nah", "wrong", "incorrect", "negative", "cancel", "not right", "no thanks",
      "know", "now"}

# A word that turns the yes-word after it into a no: "that's not right".
NEGATIONS = {"not", "don't", "dont"}

KEEP = {"keep", "keep it", "skip", "same", "unchanged", "next", "leave it", "no change"}

# Too common to wake on: they would turn ordinary sentences into commands, or are what people
# say around the word they want ("let's use jarvis please").
COMMON = {"the", "and", "you", "for", "are", "but", "this", "that", "with", "have", "what", "hey",
          "okay", "hello", "please", "just", "use", "make", "call", "want", "like", "would",
          "let's", "lets", "word", "wake", "instead", "can", "could"}


def _speak(text):
    """Say something and wait until it has been said, or the question overlaps its answer."""
    say(text)
    speech.wait()


def _hear(ears):
    """One spoken answer as lowercase words without punctuation, or None.

    In a noisy room the recogniser can write out a sentence of background before the answer, and
    the answer comes last, so only the last sentence is kept.
    """
    heard = ears.listen_once()
    if not heard:
        return None

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", heard.strip()) if re.search(r"\w", s)]
    if sentences:
        heard = sentences[-1]

    answer = " ".join(re.findall(r"[\w']+", heard.lower().replace("’", "'")))
    if answer:
        detail(f"  > {answer}")
    return answer or None


def _yes_or_no(answer):
    """True, False, or None if the answer is neither.

    Settled by the first word that decides it, so "no, that's not right" is a no although
    "right" is in it, and "yes I know" is a yes although "know" stands in for "no".
    """
    if answer in YES:
        return True
    if answer in NO:
        return False
    for word in answer.split():
        if word in NO or word in NEGATIONS:
            return False
        if word in YES:
            return True
    return None


def confirm(ears, question, attempts=ATTEMPTS):
    """Ask a yes/no question out loud. True, False, or None if never understood."""
    for attempt in range(attempts):
        _speak(question if attempt == 0 else "Was that a yes or a no?")
        answer = _hear(ears)
        verdict = None if answer is None else _yes_or_no(answer)
        if verdict is not None:
            return verdict
    return None


def _ask(ears, opening, retry, interpret):
    """Ask until understood and confirmed. Returns the value, or None to keep the current one.

    interpret(answer) returns (value, read-back question), or (None, "") if it did not understand.
    """
    for attempt in range(ATTEMPTS):
        _speak(opening if attempt == 0 else retry)
        answer = _hear(ears)
        if answer is None:
            continue
        if answer in KEEP:
            return None

        value, read_back = interpret(answer)
        if value is None:
            continue

        confirmed = confirm(ears, read_back)
        if confirmed:
            return value
        if confirmed is None:
            return None
        # A clear "no": spend the next attempt asking again.
    return None


def wake_word_in(answer):
    """The word to wake on out of an answer: the last one that can serve as a wake word.

    Not a command or anything the conversation itself listens for, or saying it would do two
    things at once.
    """
    taken = registry.command_words() | YES | NO | KEEP | COMMON
    for word in reversed(answer.split()):
        if settings.valid_prefix(word) and word not in taken:
            return word
    return None


def _ask_prefix(ears):
    current = settings.get("prefix")

    def interpret(answer):
        word = wake_word_in(answer)
        return (word, f"I heard {word}. Should I answer to {word} from now on?") if word else (None, "")

    chosen = _ask(ears,
                  f"First, the wake word. Right now I answer to {current}. Say a single word you would "
                  f"like to use instead, or say keep to leave it as {current}.",
                  "Sorry, I need one word, at least three letters, that isn't one of my commands. Once more?",
                  interpret)

    if chosen is None:
        _speak(f"Keeping {current}.")
        return
    settings.set("prefix", chosen)
    _speak(f"Done. Say {chosen} before every command from now on.")


FOCUSED_WORDS = ("only", "focus", "focused", "focussed", "selected", "front")
ALWAYS_WORDS = ("always", "all", "everything", "background", "anytime", "constantly")


def listen_when_in(answer):
    """"always", "focused", or None, out of an answer to when to listen.

    Focus words are looked for first, and "not always" counts as one: an answer like "only when
    in focus, not always" holds both, and means focus.
    """
    words = answer.split()
    if "not always" in answer or any(word in FOCUSED_WORDS for word in words):
        return "focused"
    if any(word in ALWAYS_WORDS for word in words):
        return "always"
    return None


def _ask_listening(ears):
    if ears.may_listen is None:
        return   # console mode has no window to be in focus

    current = settings.get("listen_when")
    now = "all the time" if current == "always" else "only while my window is in focus"

    def interpret(answer):
        when = listen_when_in(answer)
        if when == "always":
            return "always", "I heard always. Should I keep listening even when my window is minimised?"
        if when == "focused":
            return "focused", "I heard only when in focus. Should I listen only while my window is in front?"
        return None, ""

    chosen = _ask(ears,
                  "Next, when should I listen. I can listen all the time, even when my window is minimised, "
                  "which is hands free but means the microphone is always on. Or I can listen only while my "
                  "window is in focus, which is more private, since the microphone is switched off otherwise, "
                  f"but means you have to click me first. Right now I listen {now}. Say always, or say focus, "
                  "or say keep.",
                  "Sorry. Say always, or say focus.",
                  interpret)

    if chosen is None:
        _speak(f"Keeping it as it is. I listen {now}.")
        return
    settings.set("listen_when", chosen)
    _speak("Done. I'll listen all the time." if chosen == "always"
           else "Done. I'll only listen while my window is in focus.")


QUESTIONS = (_ask_prefix, _ask_listening)


def on_ready(ears):
    """The Listener's on_ready hook: set up on first run."""
    if settings.is_first_run():
        run(ears, first_time=True)


def run(ears=None, first_time=False):
    """Walk the user through the settings, through the open microphone."""
    ears = ears or listener.current()
    if ears is None:
        detail("Setup needs the microphone, which is not running.")
        return

    if not speech.ready():
        # Every question is spoken; without a voice the user could not hear them.
        detail("No voice on this PC, so setup was skipped and the defaults were kept. "
               f"Settings live in {settings.FILE}")
        settings.save()
        return

    was_enabled = speech.enabled()
    speech.set_enabled(True)   # even after `quiet`: the conversation is nothing but questions
    try:
        if first_time:
            _speak("Hello. I'm Hard2Assist, and this is the first time you've run me, so let's set a few "
                   "things up. You can say keep at any point to leave something as it is.")
        else:
            _speak("Let's go through your settings. Say keep to leave one alone.")

        for question in QUESTIONS:
            question(ears)

        settings.save()   # even when nothing changed, so first run is not offered again
        prefix = settings.get("prefix")
        _speak(f"All done. Say {prefix} help to hear what I can do, or {prefix} customize to change these again.")
    finally:
        speech.set_enabled(was_enabled)
