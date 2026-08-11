"""Command discovery and dispatch.

A command module is any .py file under commands/<group>/ that defines:

    NAME      -- the word the user says
    TAKES_ARG -- True if the rest of the sentence is passed to run()
    ARG_OPTIONAL -- optional; with TAKES_ARG, lets the command run with
                 nothing after it, receiving "". For commands that are
                 useful either way: `help` lists everything, `help open`
                 explains one command.
    HELP      -- one line shown by the `help` command
    ABOUT     -- optional; the fuller explanation `help <command>` shows.
                 Its first sentence is spoken, so write one that stands on
                 its own; the rest is only written. "{prefix}" anywhere in
                 the text becomes the live wake word.
    ALIASES   -- optional; single words the recogniser commonly returns
                 instead. Single words only: they are matched a word at a
                 time, so a multi-word alias could never match.
    PHRASES   -- optional; whole spoken sentences that name no command word
                 at all, such as "what can you do" for `help`.
    EXAMPLE   -- optional; a sample argument, spoken back when the user needs
                 to be told how the command is used.
    run()     -- run(arg) if TAKES_ARG, otherwise run()

Commands are registered purely by their presence on disk: adding one means
dropping a file into the folder, with no central list to update. Files whose
name starts with an underscore are skipped, so a group can keep shared helpers
alongside its commands.
"""

import difflib
import glob
import importlib.util
import os
import sys

import settings
from output import detail, say

# Sentinel a command returns to request shutdown. Only `stop` uses it.
STOP = object()

# Words that only glue a sentence together. Stripped from the front of an
# argument so "set the volume to fifty" hands `volume` the same "fifty" that
# "volume fifty" does. Deliberately short: "up", "all" and "my" carry meaning
# to one command or another and must survive.
ARG_FILLER = ("to", "the", "a", "an", "at", "on", "of", "is", "for")

# Words that introduce a command without belonging to it. Stripped from the
# front of an argument that was spoken *before* the command word, so "turn up
# the volume" reaches `volume` with "up", exactly as "volume up" does.
LEAD_WORDS = ("turn", "set", "put", "make", "change", "adjust", "please",
              "can", "could", "would", "you", "i", "just", "want", "let",
              "lets", "let's")

# How close the first word must be to a command name before it is taken *as*
# that command and run.
MATCH_CUTOFF = 0.75

# How close a word must be to a command name before it is offered as a
# suggestion. Looser than MATCH_CUTOFF, because this only ever produces advice
# the user can ignore rather than running anything.
SUGGEST_CUTOFF = 0.7


def _roots():
    """Directories that may contain a commands/ folder.

    Running from source there is only one. In the built .exe there are three:
    the PyInstaller bundle (sys._MEIPASS, where the shipped commands are
    unpacked), the directory next to the .exe itself, and the user's own
    folder in %APPDATA%.

    The last one exists because the .exe is installed rather than copied
    somewhere by hand, and an install folder is not always writable -- under
    Program Files it certainly is not. %APPDATA% always is, so dropping in a
    new command works wherever the app was installed.
    """
    if getattr(sys, "frozen", False):
        return [
            sys._MEIPASS,
            os.path.dirname(sys.executable),
            settings.USER_DIR,
        ]
    return [os.path.dirname(os.path.abspath(__file__))]


_loaded = None
_aliases = {}
_phrases = []


def load():
    """Import every command module. Returns {name: module}.

    The result is cached so callers (such as `help`) can request the command
    list without rescanning the disk.
    """
    global _loaded
    if _loaded is not None:
        return _loaded

    commands = {}

    for root in _roots():
        pattern = os.path.join(root, "commands", "*", "*.py")

        for path in sorted(glob.glob(pattern)):
            if os.path.basename(path).startswith("_"):
                continue

            module = _import_file(path)
            if module is None:
                continue

            if not hasattr(module, "NAME") or not hasattr(module, "run"):
                detail(f"Skipping {os.path.basename(path)}: it needs a NAME and a run()")
                continue

            name = module.NAME.lower()
            if name in commands:
                # First root wins; a command next to the .exe never overrides
                # a bundled one of the same name.
                continue

            commands[name] = module

    _loaded = commands
    _build_aliases(commands)
    _build_phrases(commands)
    return commands


def _build_aliases(commands):
    """Map each declared alias onto its command.

    Aliases absorb consistent recognition errors -- for example, Google's
    recogniser returns "clothes" for "close" far more often than not.

    They must be single words. dispatch() matches on the first word alone,
    so an alias like "stop talking" would never be reached -- worse, its
    first word can belong to another command, which is exactly what made
    "stop talking" quit the app instead of silencing it.
    """
    global _aliases
    _aliases = {}

    for name, module in commands.items():
        for alias in getattr(module, "ALIASES", ()):
            alias = alias.lower()
            # A real command name always takes priority over an alias.
            if alias not in commands:
                _aliases.setdefault(alias, name)


def _build_phrases(commands):
    """Index the whole sentences commands declare in PHRASES.

    These exist for the phrasings that contain no command word at all, which
    the word scan in understand() cannot reach: "what can you do" means
    `help` without ever saying "help".

    Longest phrase first, so a specific phrase is preferred over a shorter
    one that happens to be part of it.
    """
    global _phrases

    found = []
    for name, module in commands.items():
        for phrase in getattr(module, "PHRASES", ()):
            found.append((tuple(phrase.lower().split()), name))

    _phrases = sorted(found, key=lambda entry: len(entry[0]), reverse=True)


def _scan(commands, words):
    """Find a command named anywhere in the sentence, not just at the front.

    This is what lets the app be spoken to in sentences: "what time is it"
    and "can you open notepad" reach the same commands as "time" and "open
    notepad", with everything after the command word taken as the argument.

    Real names are searched across the whole sentence before any alias is
    considered, so "can you show me the time" reaches `time` rather than
    being caught by "show", which `focus` declares as an alias.

    Returns (index of the command word, name, exact), or (None, None, False).
    `exact` says whether the word was a real command name rather than an
    alias -- understand() weighs the two differently against a phrase.
    """
    for i, word in enumerate(words):
        if word in commands:
            return i, word, True

    for i, word in enumerate(words):
        if word in _aliases:
            return i, _aliases[word], False

    return None, None, False


def _phrase(words):
    """Find a declared PHRASES sentence inside the utterance.

    Returns (where the phrase starts, where it ends, name), or
    (None, None, None). The start is what lets understand() tell whether a
    command word was spoken before the phrase or inside it.
    """
    for phrase, name in _phrases:
        length = len(phrase)
        for i in range(len(words) - length + 1):
            if tuple(words[i:i + length]) == phrase:
                return i, i + length, name

    return None, None, None


def _argument(words):
    """The words after a command word, as the argument the command expects."""
    while words and words[0] in ARG_FILLER:
        words = words[1:]

    return " ".join(words).strip()


def _before(words):
    """An argument spoken in front of the command word: "mute the volume".

    Kept to a word or two. Anything longer is a sentence that merely happened
    to end on a command word, and guessing an argument out of it produces a
    worse reply than admitting the command needs one.
    """
    while words and words[-1] in ARG_FILLER:
        words = words[:-1]

    while words and words[0] in LEAD_WORDS:
        words = words[1:]

    if not words or len(words) > 2:
        return ""

    return " ".join(words)


def understand(commands, utterance):
    """Work out which command an utterance asks for, and with what argument.

    Returns (name, argument, corrected_from), where corrected_from is the
    word that was corrected when a guess was involved, and None when the
    match was exact. Returns (None, None, None) when nothing matches.

    Tried in order, most specific first:

        1. a declared PHRASES sentence       "what can you do"
        2. a command word anywhere           "what time is it", "open notepad"
        3. the first word nearly names one   "tim" -> "time"

    Phrases are tested before single words, not after, because a phrase can
    contain a command word that means something else in context. "stop
    talking" asks for `quiet`; matching the word "stop" first would quit the
    app instead -- the same trap that made multi-word ALIASES unworkable.

    With one exception: a real command name spoken *before* the phrase keeps
    the sentence, and the phrase becomes part of its argument. "help full
    screen" is a question about `fullscreen`, not a request to maximise
    something -- and without this it reached `fullscreen` with no argument
    and was answered with "'fullscreen' needs something after it". The same
    rule lets "type stop talking" type the words instead of going quiet.

    Only exact names count for that, never aliases: aliases are loose enough
    ("show", "hide", "space", "voice") that "show me what's open" would stop
    meaning `windows` and start meaning `focus`.

    Fuzzy matching stays last and stays limited to the first word. Running it
    over every word in a sentence turns ordinary filler into a command often
    enough to be worse than not matching at all.
    """
    words = utterance.lower().split()
    if not words:
        return None, None, None

    start, after, phrase_name = _phrase(words)
    index, name, exact = _scan(commands, words)

    # 1: a declared sentence, which outranks any single word inside it --
    #    unless a command was named ahead of it. A phrase starting level with
    #    the command word still wins, which is what keeps "stop talking"
    #    meaning `quiet` and "close yourself" meaning `stop`.
    if phrase_name is not None and not (exact and index < start):
        # Nothing to report as corrected: the phrase matched word for word.
        # Handing back the utterance instead made every declared phrasing
        # look like a mishearing that got rescued -- "what's open" logged
        # "(heard 'what's open', taking it as 'windows')", which reads as the
        # app being unsure about a sentence it knows perfectly well.
        return phrase_name, _argument(words[after:]), None

    # 2: a command word somewhere in the sentence.
    if name is not None:
        corrected = words[index] if words[index] != name else None
        argument = _argument(words[index + 1:])

        # Only when nothing followed the command word, so "volume up" and
        # "turn the volume up" keep taking their argument from the right.
        if not argument:
            argument = _before(words[:index])

        return name, argument, corrected

    # 3: the first word, mangled by the recogniser.
    close = difflib.get_close_matches(words[0], list(commands), n=1,
                                      cutoff=MATCH_CUTOFF)
    if close:
        return close[0], _argument(words[1:]), words[0]

    return None, None, None


def usage(module):
    """How to say this command, phrased to be read back to the user.

    Built from EXAMPLE so the advice is a sentence the user can repeat
    verbatim, and from the live wake word so it stays right after the word
    has been changed through `customize`.
    """
    example = getattr(module, "EXAMPLE", "") or module.NAME

    return f"{settings.get('prefix')} {example}"


def _suggest(commands, utterance):
    """The command an unrecognised utterance most likely meant, or None.

    Every word is tried, because the command word is not necessarily the
    first one in a spoken sentence.

    Matched against command names only, never aliases. Aliases are there to
    be matched exactly, and they are short and odd enough ("switch", "ope",
    "folks") that scoring ordinary words against them suggests nonsense --
    "make me a sandwich" scores 0.86 against `focus`'s "switch" alias.
    """
    for word in utterance.lower().split():
        if len(word) < 3:
            continue

        close = difflib.get_close_matches(word, list(commands), n=1,
                                          cutoff=SUGGEST_CUTOFF)
        if close:
            return commands[close[0]]

    return None


def _report_unknown(commands, utterance):
    """Tell the user what to say instead, rather than sending them to `help`.

    A list of every command is no use to someone who has just been
    misunderstood once: the useful answer is the one command they probably
    wanted and the exact words that would have worked.
    """
    module = _suggest(commands, utterance)

    if module is not None:
        say(f"I don't know '{utterance}'. Did you mean {module.NAME}? "
            f"Say {usage(module)}.")
        return

    # Nothing close. Offer real examples built from the loaded commands, so
    # they cannot drift out of step with what is actually available.
    examples = [usage(commands[name]) for name in ("open", "time")
                if name in commands]

    if examples:
        say(f"I don't know '{utterance}'. You can say things like ")
        detail(f"{', or '.join(examples)}.")
        return

    say(f"I don't know '{utterance}'.")


def _import_file(path):
    """Load a single .py file as a module, by path.

    Loading by path rather than through a `commands` package is what allows
    the built .exe to pick up command files dropped in next to it: a package
    is bound to the folder it was first imported from, so files added later
    in a different folder would never be found.
    """
    # The module name includes the full path so that same-named files in
    # different groups do not collide in sys.modules.
    unique = "h2a_command_" + path.replace(os.sep, "_").replace(":", "").lstrip("_")

    try:
        spec = importlib.util.spec_from_file_location(unique, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        detail(f"Could not load {os.path.basename(path)}: {e}")
        sys.modules.pop(unique, None)
        return None


def dispatch(commands, utterance):
    """Run the command an utterance asks for.

    The command word may sit anywhere in the sentence, and everything after
    it becomes the argument: "open task manager" and "can you open task
    manager" both run `open` with "task manager". See understand().
    """
    utterance = utterance.strip()
    if not utterance:
        return None

    name, argument, corrected_from = understand(commands, utterance)

    if name is None:
        _report_unknown(commands, utterance)
        return None

    if corrected_from:
        # Written but not spoken: the command's own confirmation, which
        # follows immediately, already says what it decided to do.
        detail(f"(heard '{corrected_from}', taking it as '{name}')")

    module = commands[name]

    if getattr(module, "TAKES_ARG", False):
        # ARG_OPTIONAL commands do something sensible with nothing after
        # them, so being told they need an argument would be a lie: `help`
        # on its own is the command's main use, not a mistake.
        if not argument and not getattr(module, "ARG_OPTIONAL", False):
            say(f"'{module.NAME}' needs something after it, like "
                f"{usage(module)}.")
            return None
        return module.run(argument)

    return module.run()
