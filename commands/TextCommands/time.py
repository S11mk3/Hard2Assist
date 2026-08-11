"""Say what time it is."""

from datetime import datetime

from output import say

NAME = "time"
TAKES_ARG = False
ALIASES = ("thyme", "time's")
HELP = "time         -- what time it is"

ABOUT = """\
Time says the time out loud.
"what time is it" works, and so does "what's the time".
It reads this PC's own clock, so it is right wherever you are without
needing the internet.\
"""


def run():
    now = datetime.now()
    # %#I is the Windows strftime code for "hour without a leading zero":
    # "It's 7:05" reads naturally where "It's 07:05" does not.
    say(f"It's {now.strftime('%#I:%M %p').lower()}")
