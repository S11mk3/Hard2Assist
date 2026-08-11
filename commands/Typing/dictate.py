"""Keep typing everything you say, until you say "computer stop dictating".

The wake word is dropped for the duration, and comes back only for the
sentence that ends dictation -- see STOP_PHRASES. That is what `type` cannot
offer: a wake word before every sentence is unusable for a paragraph.

Listening for its own answers is safe here because this runs on the
microphone thread, which already owns the open audio source. See
listener.listen_once().
"""

import re

import listener
import session
import settings
import speech
import spoken
from output import detail, say

NAME = "dictate"
TAKES_ARG = False
ALIASES = ("dictation", "dictating", "dictates", "dictated")
PHRASES = ("start typing", "take a note", "take notes", "start dictating")
HELP = "dictate      -- type everything you say until you say stop dictating"

ABOUT = """\
Dictate types everything you say, with no wake word needed, until you tell
it to stop.
It is for paragraphs; "type" is for a line. "take a note" and "start
typing" start it too.
Say "{prefix} stop dictating" to finish. That one sentence needs the wake
word, because everything else you say is being typed. A bare "stop" is
deliberately not enough -- it ends ordinary sentences too. Said on the end
of a line, the line is typed first and nothing is lost.
It also stops by itself after a while of silence, so a microphone that
stops working never traps it.
Each line is typed as you finish saying it, and shown here rather than
read back.\
"""

# What ends dictation, said after the wake word: "computer stop dictating".
#
# Dictation types everything it hears, so its exit has to be something that
# cannot turn up in what is being dictated. A bare "stop" ends ordinary
# sentences ("the bus came to a stop"); the wake word in front is what makes
# the phrase impossible to dictate by accident.
STOP_PHRASES = ("stop dictating", "stop dictation", "stop typing", "stop")

# Politeness allowed on either side of the phrase, so "computer please stop
# dictating now" works. Generous, because the wake word in front is what makes
# the whole thing a command rather than a sentence.
FILLER = ("please", "now", "just", "can you", "could you", "would you",
          "you", "i want you to")

# How long to wait for each sentence. Longer than the main loop's timeout:
# the user is composing rather than issuing a command, and pausing to think
# should not be read as a pause in the dictation.
TIMEOUT = 12

# Consecutive silences before it gives up on its own.
#
# The escape hatch. Dictation holds the command lock on the microphone thread
# for as long as it runs, so nothing else can be said while it does -- not
# `stop`, not `quiet`.
MAX_SILENCE = 3


def run():
    ears = listener.current()
    if ears is None:
        say("Dictation needs the microphone, which isn't running.")
        return

    # Where the text will land, with our own window moved aside if it was in
    # front. Says why itself when there is nowhere sensible to type.
    target = session.keyboard_target()
    if target is None:
        return

    # From settings rather than the literal word "computer", so the sentence
    # names the phrase that actually works after `customize`.
    say(f"Dictating into {target}. Say {settings.get('prefix')} stop dictating "
        f"when you're done.")

    # Without this the microphone opens while that sentence is still playing,
    # and the app hears its own "say computer stop dictating" and stops.
    speech.wait()

    typed = _listen(ears)

    if typed:
        line = "line" if typed == 1 else "lines"
        say(f"Stopped dictating. {typed} {line} typed.")
    else:
        say("Stopped dictating.")


def _stop_pattern():
    """Matches the exit phrase where it ends an utterance.

    Anchored to the end, so a line quoting the phrase mid-sentence is still
    typed. It has to reach past the end of a sentence because one utterance is
    not always one sentence: the recogniser groups by pauses, so a phrase said
    straight after a line arrives joined onto it.

    Built per call rather than at import, so a wake word changed through
    `customize` takes effect on the next thing said.
    """
    prefix = re.escape(settings.get("prefix"))

    # Longest first, or "stop" would match and leave "dictating" behind.
    phrases = "|".join(re.escape(phrase) for phrase
                       in sorted(STOP_PHRASES, key=len, reverse=True))
    filler = "|".join(re.escape(word) for word
                      in sorted(FILLER, key=len, reverse=True))

    gap = r"[\s,.!?]+"

    return re.compile(
        rf"(?:^|{gap}){prefix}"          # the wake word, alone or after a line
        rf"(?:{gap}(?:{filler}))*"       # "please", "can you"
        rf"{gap}(?:{phrases})"           # the phrase itself
        rf"(?:{gap}(?:{filler}))*"       # "now", "please"
        rf"[\s,.!?]*$",                  # trailing punctuation
        re.IGNORECASE,
    )


def _split_stop(heard):
    """Split an utterance into what to type and whether it ends dictation.

    Returns (text, stopping). The phrase said on its own types nothing; said on
    the end of a sentence it types the sentence first, so the last thing the
    user dictated is not lost to the words that ended the session.
    """
    heard = heard.strip()

    trimmed = _stop_pattern().sub("", heard).strip()

    return (trimmed, True) if trimmed != heard else (heard, False)


def _listen(ears):
    """The dictation loop. Returns how many lines were typed."""
    typed = 0
    silences = 0

    while True:
        heard = ears.listen_once(timeout=TIMEOUT)

        if not heard:
            silences += 1
            if silences >= MAX_SILENCE:
                detail("(nothing heard for a while, so dictation stopped)")
                return typed
            continue

        silences = 0

        heard, stopping = _split_stop(heard)

        text = spoken.prepare(heard) if heard else ""
        if not text:
            if stopping:
                return typed
            continue

        # Written, never spoken: reading each line back would make it hard to
        # keep a train of thought.
        detail(f"  > {text}")

        if not spoken.type_out(text):
            say("Windows stopped letting me type there.")
            return typed

        # Sentences arrive one utterance at a time and would otherwise run
        # together. Not after a line break, which is already a separator.
        if not text.endswith("\n"):
            spoken.type_out(" ")

        typed += 1

        # The stop rode in on the end of that line, which is now typed.
        if stopping:
            return typed
