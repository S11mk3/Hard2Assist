"""Finding the commands, and working out which one a sentence asks for.

A command is any .py file under commands/<group>/ (names starting "_" are skipped) defining:

    NAME          the word the user says
    TAKES_ARG     True if the rest of the sentence is passed to run()
    HELP          its line in `help`: "usage -- what it does"
    run()         run(argument) if TAKES_ARG, else run()

and optionally:

    ARG_OPTIONAL  with TAKES_ARG, it also runs with nothing after it, receiving ""
    ALIASES       single words the recogniser returns instead of NAME; reported as corrections
    SYNONYMS      single words meaning the same as NAME; matched without comment
    PHRASES       sentences naming no command word ("what can you do"); a dict maps each phrase
                  to the argument it implies ({"new tab": "new tab"})
    VERBATIM      the argument is text, passed exactly as heard (`type`, `search`)
    EXACT_ONLY    never reached by guessing at a misheard first word (`kill`, `close`, `stop`)
    EXAMPLE       a sample use, spoken back when the user needs telling how
    settle()      called before the next command in a chain runs: `open` waits for its window
    ABOUT         what `help <command>` shows; its first sentence is spoken, and "{prefix}"
                  becomes the live wake word

Commands are loaded by path, so code they share lives at the top level (session.py, spoken.py).
"""

import difflib
import glob
import importlib.util
import os
import re
import sys

import apps
import settings
import storage
import win
from output import detail, log, say, warn

# Returned by a command to quit the app. Only `stop` does.
STOP = object()

# Glue taken off the front of an argument: "set the volume to fifty" gives `volume` "fifty".
# Short, because "up", "all" and "my" mean something to one command or another.
ARG_FILLER = ("to", "the", "a", "an", "at", "on", "of", "is", "for")

# Politeness off the end: "open notepad, please" names notepad.
TRAILING_FILLER = ("please", "now")

# Words introducing a command without belonging to it, taken off an argument spoken *before* the
# command word: "turn up the volume" gives `volume` "up".
LEAD_WORDS = ("turn", "set", "put", "make", "change", "adjust", "please", "can", "could", "would",
              "you", "i", "just", "want", "let", "lets", "let's")

# What may come before a command word when the wake word was only a guess; see opens_with_command().
OPENERS = frozenset(LEAD_WORDS + ARG_FILLER + ("what", "what's", "whats", "how", "much", "tell", "me"))

# Taken off each end of a word before matching -- "Notepad," "50." -- but apostrophes stay.
PUNCTUATION = ",.?!;:\"()"

# How close a misheard first word must be to a command name to be run as it.
MATCH_CUTOFF = 0.75
# How close any word must be to be offered as "did you mean"; looser, since it is only advice.
SUGGEST_CUTOFF = 0.7

# Words joining two commands in one sentence: "open notepad and type hello".
CHAIN_WORDS = ("and", "then")

_commands = None
_aliases = {}   # word -> (command name, reported as a correction)
_phrases = []   # (words, command name, implied argument), longest first


def _roots():
    """Folders holding a commands/ folder.

    The built app also loads commands dropped beside the .exe or into %APPDATA%\\Hard2Assist --
    unless it is running as administrator, since anything placed in those user-writable folders
    would then run with administrator rights.
    """
    if not storage.FROZEN:
        return [storage.BUNDLE_DIR]
    if win.is_elevated():
        detail("(Running as administrator, so commands added outside the install were not loaded.)")
        return [storage.BUNDLE_DIR]
    return [storage.BUNDLE_DIR, storage.EXE_DIR, storage.USER_DIR]


def load():
    """Import every command, once. Returns {name: module}."""
    global _commands
    if _commands is not None:
        return _commands

    commands = {}
    for index, root in enumerate(_roots()):
        for path in sorted(glob.glob(os.path.join(root, "commands", "*", "*.py"))):
            if os.path.basename(path).startswith("_"):
                continue
            module = _import(path, index)
            if module is None:
                continue
            if not hasattr(module, "NAME") or not hasattr(module, "run"):
                detail(f"Skipping {os.path.basename(path)}: it needs a NAME and a run()")
                continue
            # The first root wins: a file beside the .exe never replaces a bundled command.
            commands.setdefault(module.NAME.lower(), module)

    _commands = commands
    _index(commands)
    return commands


def _import(path, root_index):
    """Load one file as a module, by path. A `commands` package would be bound to one folder."""
    group = os.path.basename(os.path.dirname(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    unique = re.sub(r"\W", "_", f"h2a_command_{root_index}_{group}_{stem}")
    try:
        spec = importlib.util.spec_from_file_location(unique, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        sys.modules.pop(unique, None)
        log.exception("Could not load %s", path)
        detail(f"Could not load {os.path.basename(path)}: {e}")
        return None


def _index(commands):
    global _aliases, _phrases
    _aliases, _phrases = {}, []

    for name, module in commands.items():
        for words, reported in ((getattr(module, "ALIASES", ()), True), (getattr(module, "SYNONYMS", ()), False)):
            for word in words:
                if word.lower() not in commands:   # a real command name outranks an alias
                    _aliases.setdefault(word.lower(), (name, reported))

        phrases = getattr(module, "PHRASES", ())
        for phrase, implied in (phrases.items() if isinstance(phrases, dict) else dict.fromkeys(phrases, "").items()):
            _phrases.append((tuple(phrase.lower().split()), name, implied))

    # Longest first, so a specific phrase beats a shorter one inside it.
    _phrases.sort(key=lambda entry: len(entry[0]), reverse=True)


def command_words():
    """Every command name, alias and synonym."""
    load()
    return set(_commands) | set(_aliases)


def _clean(token):
    return token.lower().replace("\u2019", "'").strip(PUNCTUATION)


def _tokens(utterance):
    """(words, spoken): lowercase and trimmed of punctuation to match, and as heard for a VERBATIM
    argument. The offline recogniser capitalises and punctuates. Same length, word for word."""
    words, spoken = [], []
    for token in utterance.split():
        word = _clean(token)
        if word:
            words.append(word)
            spoken.append(token)
    return words, spoken


def _verbatim(name):
    return getattr(_commands[name], "VERBATIM", False)


def _argument(words, spoken, verbatim):
    """The words after a command word as its argument: as heard for a VERBATIM command, otherwise
    without the glue around them."""
    if verbatim:
        return " ".join(spoken).strip()
    while words and words[0] in ARG_FILLER:
        words = words[1:]
    while words and words[-1] in TRAILING_FILLER:
        words = words[:-1]
    return " ".join(words)


def _before(words):
    """An argument spoken before the command word ("mute the volume"). A word or two at most:
    anything longer is a sentence that happened to end on a command word."""
    while words and words[-1] in ARG_FILLER:
        words = words[:-1]
    while words and words[0] in LEAD_WORDS:
        words = words[1:]
    return " ".join(words) if 0 < len(words) <= 2 else ""


def _scan(words):
    """(index, name, exact) of the command named in a sentence, or (None, None, False).

    Real names are looked for across the whole sentence before any alias, so "can you show me
    the time" reaches `time` rather than `focus`, whose synonym "show" comes first.
    """
    for i, word in enumerate(words):
        if word in _commands:
            return i, word, True
    for i, word in enumerate(words):
        if word in _aliases:
            return i, _aliases[word][0], False
    return None, None, False


def _phrase(words):
    """(start, end, name, implied argument) of a declared phrase in the sentence, or Nones."""
    for phrase, name, implied in _phrases:
        for i in range(len(words) - len(phrase) + 1):
            if tuple(words[i:i + len(phrase)]) == phrase:
                return i, i + len(phrase), name, implied
    return None, None, None, None


def understand(utterance):
    """(name, argument, corrected_from) for what an utterance asks, or (None, None, None).

    Most specific first:
        1. a declared phrase              "what can you do", "stop talking"
        2. a command word anywhere        "what time is it", "can you open notepad"
        3. a guess at the first word      "tim" -> `time`; never for EXACT_ONLY commands

    A phrase outranks a command word inside it -- "stop talking" means `quiet`, not `stop` --
    unless a real command name comes before the phrase, which then takes it as its argument
    ("type stop talking"). corrected_from is the alias or guessed word, when there was one.
    """
    commands = load()
    words, spoken = _tokens(utterance)
    if not words:
        return None, None, None

    start, after, phrase_name, implied = _phrase(words)
    index, name, exact = _scan(words)

    if phrase_name is not None and not (exact and index < start):
        argument = _argument(words[after:], spoken[after:], _verbatim(phrase_name))
        return phrase_name, " ".join(part for part in (implied, argument) if part), None

    if name is not None:
        argument = _argument(words[index + 1:], spoken[index + 1:], _verbatim(name))
        if not argument and not _verbatim(name):
            argument = _before(words[:index])
        reported = not exact and _aliases[words[index]][1]
        return name, argument, words[index] if reported else None

    # Guessing stays limited to the first word: over every word, ordinary filler turns into
    # commands. And never into one that destroys or quits on a mishearing.
    guessable = [name for name, module in commands.items() if not getattr(module, "EXACT_ONLY", False)]
    close = difflib.get_close_matches(words[0], guessable, n=1, cutoff=MATCH_CUTOFF)
    if close:
        return close[0], _argument(words[1:], spoken[1:], _verbatim(close[0])), words[0]

    # The recogniser sometimes glues a command onto the next word: "OpenObs Studio".
    for name in sorted(guessable, key=len, reverse=True):
        if words[0].startswith(name) and len(words[0]) - len(name) >= 2:
            name, argument, _ = understand(" ".join([name, spoken[0][len(name):], *spoken[1:]]))
            return name, argument, words[0]

    return None, None, None


def opens_with_command(utterance):
    """Whether an utterance starts the way a command does, after nothing but OPENERS.

    For when the wake word was a guess: misheard, or found after the start of what was heard.
    understand() takes a command word from anywhere, which is far too loose then -- "commuter
    traffic made me lose track of time" would answer with the time.
    """
    load()
    words = _tokens(utterance)[0]
    for i, word in enumerate(words):
        if any(tuple(words[i:i + len(phrase)]) == phrase for phrase, _, _ in _phrases):
            return True
        if word in _commands or word in _aliases:
            return True
        if word not in OPENERS:
            return False
    return False


def usage(module):
    """How to say a command, built from its EXAMPLE and the live wake word."""
    return f"{settings.get('prefix')} {getattr(module, 'EXAMPLE', '') or module.NAME}"


def suggest(utterance):
    """The command an unrecognised utterance most likely meant, or None.

    Names only, never aliases: aliases are short and odd enough ("switch", "folks") that ordinary
    words score well against them.
    """
    commands = load()
    for word in _tokens(utterance)[0]:
        if len(word) >= 3:
            close = difflib.get_close_matches(word, list(commands), n=1, cutoff=SUGGEST_CUTOFF)
            if close:
                return commands[close[0]]
    return None


def _report_unknown(utterance):
    """Offer the one command they probably meant, in words that would have worked."""
    module = suggest(utterance)
    if module is not None:
        warn(f"I don't know '{utterance}'. Did you mean {module.NAME}? Say {usage(module)}.")
        return

    # Perhaps an app named without a verb: "computer notepad".
    app = apps.find(" ".join(_tokens(utterance)[0]))
    if app is not None:
        warn(f"I don't know '{utterance}'. If you meant the app, say {settings.get('prefix')} open {app.name}.")
        return

    examples = [usage(_commands[name]) for name in ("open", "time") if name in _commands]
    if examples:
        warn(f"I don't know '{utterance}'. You can say things like {examples[0]}.")
        if len(examples) > 1:
            detail(f"Or: {', or '.join(examples[1:])}.")
        return

    warn(f"I don't know '{utterance}'.")


def _chain(utterance):
    """Split "open notepad and type hello" into the commands in it.

    Only before an exact command name, and never inside a VERBATIM command's text, which takes
    everything after it: "type salt and pepper" and "search cats and dogs" stay whole.
    """
    tokens = utterance.split()
    for i in range(1, len(tokens) - 1):
        if _clean(tokens[i]) in CHAIN_WORDS and _clean(tokens[i + 1]) in _commands:
            head = tokens[:i]
            while head and _clean(head[-1]) in CHAIN_WORDS:   # "and then"
                head = head[:-1]
            first = " ".join(head).rstrip(",")
            name = understand(first)[0]
            if name is None or _verbatim(name):
                break
            return [first, *_chain(" ".join(tokens[i + 1:]))]
    return [utterance]


def dispatch(utterance):
    """Run the one command an utterance asks for. Returns what the command returns."""
    utterance = utterance.strip()
    if not utterance:
        return None

    name, argument, corrected = understand(utterance)
    if name is None:
        _report_unknown(utterance)
        return None

    if corrected:
        # Written, not spoken: the command's own confirmation follows straight away.
        detail(f"(heard '{corrected}', taking it as '{name}')")

    module = _commands[name]
    if not getattr(module, "TAKES_ARG", False):
        return module.run()
    if not argument and not getattr(module, "ARG_OPTIONAL", False):
        say(f"'{module.NAME}' needs something after it, like {usage(module)}.")
        return None
    return module.run(argument)


def run(utterance):
    """Run everything an utterance asks for, logging it and containing any error, so one failing
    command cannot take the microphone loop down. Returns STOP when the app should quit."""
    detail(f"> {utterance}")
    load()
    parts = _chain(utterance.strip())
    for i, part in enumerate(parts):
        try:
            if dispatch(part) is STOP:
                return STOP
            name = understand(part)[0]
            if i + 1 < len(parts) and hasattr(_commands.get(name), "settle"):
                _commands[name].settle()
        except Exception as e:
            log.exception("Command failed: %s", part)
            warn(f"Could not run that: {e}")
            return None
    return None
