"""Say what time it is."""

from datetime import datetime

from output import say

NAME = "time"
TAKES_ARG = False
ALIASES = ("thyme", "time's")
HELP = "time -- what time it is"

ABOUT = """\
Time says the time out loud.
"what time is it" works, and so does "what's the time".
It reads this PC's own clock, so it is right wherever you are without
needing the internet.\
"""


def run():
    say(f"It's {datetime.now().strftime('%#I:%M %p').lower()}")   # %#I: no leading zero, on Windows
