"""Turning what was heard into what gets typed.

Shared by `type` and `dictate`, which need exactly the same treatment: the
recogniser returns bare lowercase words with no punctuation at all, so what
arrives is "hello there comma how are you".

Top-level rather than a helper beside the two commands, because command
modules are loaded by file path and their folder never goes on sys.path --
one command cannot import another, or anything sitting next to it.
"""

import re

import win

# Spoken names for characters nobody can dictate directly.
#
# Kept deliberately short. Every entry here is a word that can no longer be
# typed literally -- with "period" in the table there is no way to type the
# sentence "the period was long" -- so each one has to earn its place. These
# are the ones worth the trade; a longer list costs more surprises than it
# saves keystrokes.
SPOKEN = {
    "new line": "\n",
    "newline": "\n",
    "next line": "\n",
    "new paragraph": "\n\n",
    "comma": ",",
    "period": ".",
    "full stop": ".",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
}

# Whole words only, so "commas" and "periodic" are still typed as themselves.
# Longest first, or "new line" would never match past "new".
#
# Case-insensitive, because the recogniser does not reliably return lowercase.
# It capitalises the first word of an utterance often enough that a dictated
# "new line" comes back as "New line" -- and matching that literally typed the
# words instead of breaking the line, which is the one thing the entry exists
# for. The lookup lowercases the match to find the key again.
_SPOKEN = re.compile(
    r"\b(" + "|".join(sorted(SPOKEN, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def prepare(heard):
    """The text to type for a recognised phrase.

    Two fixes, and no more than two: substitute the spoken characters, and
    capitalise the first letter so a typed sentence does not start
    mid-thought.
    """
    text = _SPOKEN.sub(lambda m: SPOKEN[m.group(1).lower()], heard.strip())

    # A substitution leaves the space that surrounded the spoken word --
    # "hello , how" -- which is not how anyone writes.
    text = re.sub(r" +([,.?!])", r"\1", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]

    return text


def type_out(text):
    """Type text, turning newlines into real Enter presses. False if refused.

    A newline cannot go through as a character: send_text() injects Unicode,
    and a Unicode line feed is not what a text box listens for. Enter is a
    key, so it has to be sent as one.
    """
    for i, line in enumerate(text.split("\n")):
        if i and not win.send_keys(win.VK_RETURN):
            return False
        if line and not win.send_text(line):
            return False

    return True
