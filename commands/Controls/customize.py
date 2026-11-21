"""Go through the setup conversation again."""

import wizard

NAME = "customize"
TAKES_ARG = False
# Not "settings": that is Windows Settings, an app, and "computer settings" should open it.
SYNONYMS = ("customise", "setup", "preferences", "configure")
HELP = "customize -- change the wake word and how I listen"

ABOUT = """\
Customize walks through the setup conversation again, out loud.
It asks two things. First, the wake word you want instead of "computer" --
any single word of three letters or more, so "jarvis" makes it "jarvis
open notepad". Second, whether I listen all the time, or only while my
window is in focus.
Each answer is explained, read back, and confirmed before it is saved.
Say "keep" to leave one as it is.
"setup" and "preferences" reach this too. Your answers are saved and used
from then on.\
"""


def run():
    wizard.run()
