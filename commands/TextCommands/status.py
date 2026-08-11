"""Report how busy the CPU and memory are."""

import psutil

from output import detail, say

NAME = "status"
TAKES_ARG = False
ALIASES = ("stats", "statue", "system", "performance")
HELP = "status       -- how busy the CPU and memory are"

ABOUT = """\
Status says how busy the processor and the memory are, as percentages.
"how busy are you" and "performance" reach it too.
How many gigabytes are actually in use, and how many cores this PC has,
are written here underneath.
The processor figure is measured over a moment rather than read off
instantly, so it takes about half a second to answer.\
"""


def run():
    # cpu_percent() with no interval returns the average since some arbitrary
    # earlier call, so sample over a moment instead.
    cpu = psutil.cpu_percent(interval=0.4)
    memory = psutil.virtual_memory()

    say(f"CPU {round(cpu)} percent, memory {round(memory.percent)} percent")

    used = memory.used / (1024 ** 3)
    total = memory.total / (1024 ** 3)
    detail(f"  {used:.1f} of {total:.1f} GB in use, "
           f"{psutil.cpu_count(logical=True)} cores")
