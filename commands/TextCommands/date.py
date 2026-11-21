"""Say what day it is."""

from datetime import datetime

from output import say

NAME = "date"
TAKES_ARG = False
ALIASES = ("dates",)
SYNONYMS = ("day", "today")
HELP = "date -- what day it is"

ABOUT = """\
Date says the day of the week and the date out loud.
"what day is it" and "today" both reach it.\
"""


def run():
    say(f"It's {datetime.now().strftime('%A, %B %#d')}")   # %#d: no leading zero, on Windows
