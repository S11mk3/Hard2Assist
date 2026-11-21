"""Type everything said, without the wake word, until "computer stop dictating".

It runs on the microphone thread, which owns the open microphone, so it listens through
listener.listen_once() -- and holds that thread, so no other command is heard meanwhile.
"""

import re

import listener
import session
import settings
import speech
import spoken
from output import detail, plural, say, warn

NAME = "dictate"
TAKES_ARG = False
SYNONYMS = ("dictation",)
ALIASES = ("dictating", "dictates", "dictated")
PHRASES = ("start typing", "take a note", "take notes", "start dictating")
HELP = "dictate -- type everything you say until you say stop dictating"

ABOUT = """\
Dictate types everything you say, with no wake word needed, until you tell
it to stop.
It is for paragraphs; "type" is for a line. "take a note" and "start
typing" start it too.
It types into the app you last named -- "open notepad", then "dictate" --
even if you click into another window meanwhile. If you haven't named one,
it types into the window in front.
Say "{prefix} stop dictating" to finish. That one sentence needs the wake
word, because everything else you say is being typed. A bare "stop" is
deliberately not enough -- it ends ordinary sentences too. Said on the end
of a line, the line is typed first and nothing is lost.
It also stops by itself after a while of silence, so a microphone that
stops working never traps it.
Each line is typed as you finish saying it, and shown here rather than
read back.\
"""

# Said after the wake word to finish. The wake word is what makes them impossible to dictate by
# accident: a bare "stop" ends ordinary sentences ("the bus came to a stop").
STOP_PHRASES = ("stop dictating", "stop dictation", "stop typing", "stop")

# Allowed either side of the phrase: "computer please stop dictating now".
FILLER = ("please", "now", "just", "can you", "could you", "would you", "you", "i want you to")

TIMEOUT = 12        # per sentence: pausing to think is not the end of the dictation
PHRASE_LIMIT = 20   # a dictated sentence runs longer than a command
MAX_SILENCE = 3     # silences in a row before it stops by itself: the way out if all else fails


def run():
    ears = listener.current()
    if ears is None:
        say("Dictation needs the microphone, which isn't running.")
        return

    target = session.keyboard_target()
    if target is None:
        return

    say(f"Dictating into {target}. Say {settings.get('prefix')} stop dictating when you're done.")
    speech.wait()   # or it hears its own "say computer stop dictating", and stops

    typed = _listen(ears)
    say(f"Stopped dictating. {plural(typed, 'line')} typed." if typed else "Stopped dictating.")


def _stop_pattern():
    """The exit phrase where it ends an utterance -- which can hold the last sentence as well,
    since the recogniser groups by pauses. Built each time, to follow a changed wake word."""
    def either(words):
        return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))

    gap = r"[\s,.!?]+"
    return re.compile(
        rf"(?:^|(?<=[\s,.!?])){re.escape(settings.get('prefix'))}"   # keeps the full stop before it
        rf"(?:{gap}(?:{either(FILLER)}))*{gap}(?:{either(STOP_PHRASES)})(?:{gap}(?:{either(FILLER)}))*"
        r"[\s,.!?]*$",
        re.IGNORECASE)


def _split_stop(heard):
    """(text to type, whether dictation ends). A sentence said before the phrase is still typed,
    without a comma left dangling where the phrase came off."""
    heard = heard.strip()
    trimmed = _stop_pattern().sub("", heard).rstrip(" ,").strip()
    return (trimmed, True) if trimmed != heard else (heard, False)


def _listen(ears):
    """The dictation loop. Returns how many lines were typed."""
    typed = silences = 0
    while True:
        heard = ears.listen_once(timeout=TIMEOUT, phrase_limit=PHRASE_LIMIT)
        if not heard:
            silences += 1
            if silences >= MAX_SILENCE:
                detail("(nothing heard for a while, so dictation stopped)")
                return typed
            continue
        silences = 0

        heard, stopping = _split_stop(heard)
        text = spoken.prepare(heard) if heard else ""
        if text:
            # Every line, so a click elsewhere meanwhile cannot send the rest somewhere else.
            if session.keyboard_target() is None:
                return typed
            detail(f"  > {text}")   # written, never read back: that would break a train of thought
            if not spoken.type_out(text):
                warn("Windows stopped letting me type there.")
                return typed
            if not text.endswith("\n"):
                spoken.type_out(" ")   # or one sentence runs into the next
            typed += 1
        if stopping:
            return typed
