"""Turning what was heard into what gets typed.

Shared by `type` and `dictate`. The recogniser returns bare lowercase words
with no punctuation, so "hello there comma how are you" is what arrives.

Top level rather than a helper beside the two commands: command modules are
loaded by file path and their folder never joins sys.path, so one command
cannot import another or anything sitting next to it.
"""

import re

import win

# Spoken names for characters that cannot be dictated directly.
#
# Short by necessity: each entry is a word that can no longer be typed
# literally, so "the period was long" cannot be dictated while "period" is in
# the table.
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

# Whole words only, so "commas" and "periodic" are typed as themselves.
# Longest first, or "new line" would never match past "new".
#
# Case-insensitive: the recogniser capitalises the first word of an utterance
# often enough that a dictated "new line" arrives as "New line". The lookup
# lowercases the match to find the key again.
_SPOKEN = re.compile(
    r"\b(" + "|".join(sorted(SPOKEN, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def prepare(heard):
    """The text to type for a recognised phrase.

    Substitutes the spoken characters and capitalises the first letter.
    """
    text = _SPOKEN.sub(lambda m: SPOKEN[m.group(1).lower()], heard.strip())

    # A substitution leaves the space that surrounded the spoken word --
    # "hello , how" -- so close it up.
    text = re.sub(r" +([,.?!])", r"\1", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    if text and text[0].isalpha():
        text = text[0].upper() + text[1:]

    return text


def type_out(text):
    """Type text, turning newlines into Enter presses. False if refused.

    A newline cannot go through as a character: send_text() injects Unicode,
    and a text box listens for the Enter key rather than a line feed.
    """
    for i, line in enumerate(text.split("\n")):
        if i and not win.send_keys(win.VK_RETURN):
            return False
        if line and not win.send_text(line):
            return False

    return True
