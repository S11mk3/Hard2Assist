"""Turning what was heard into what gets typed, for `type` and `dictate`.

Punctuation can be spoken -- "hello there comma how are you question mark" -- and the offline
recogniser also adds punctuation of its own around those words, so a spoken mark replaces any
the recogniser put beside it rather than doubling up.
"""

import re

import win

# Each of these words can no longer be typed literally ("the period was long"), so the list is
# kept short.
MARKS = {
    "comma": ",",
    "period": ".",
    "full stop": ".",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
}
BREAKS = {
    "new line": "\n",
    "newline": "\n",
    "next line": "\n",
    "new paragraph": "\n\n",
}


def _either(words):
    # Longest first, or "new line" would never match past "new".
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


_PUNCTUATION = r"[,.;:!?]"

# Whole words only, so "commas" and "periodic" stay themselves. A mark takes the place of the
# recogniser's punctuation on both sides of it; a break keeps the full stop before it.
_MARK = re.compile(rf"\s*{_PUNCTUATION}*\s*\b({_either(MARKS)})\b{_PUNCTUATION}*", re.IGNORECASE)
_BREAK = re.compile(rf"[ \t]*\b({_either(BREAKS)})\b{_PUNCTUATION}*[ \t]*", re.IGNORECASE)


def prepare(heard):
    """The text to type: spoken punctuation substituted, and each sentence and line capitalised."""
    text = _MARK.sub(lambda m: MARKS[m.group(1).lower()], heard.strip())
    text = _BREAK.sub(lambda m: BREAKS[m.group(1).lower()], text)
    return re.sub(r"(^|[.!?]\s+|\n)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)


def type_out(text):
    """Type text, newlines as Enter presses (a text box ignores a typed line feed). False if refused."""
    for i, line in enumerate(text.split("\n")):
        if i and not win.send_keys(win.VK_RETURN):
            return False
        if line and not win.send_text(line):
            return False
    return True
