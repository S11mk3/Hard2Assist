"""Report how busy the CPU and memory are."""

import psutil

from output import detail, say

NAME = "status"
TAKES_ARG = False
ALIASES = ("statue",)
SYNONYMS = ("stats", "system", "performance")
PHRASES = ("how busy are you", "how busy is it")
HELP = "status -- how busy the CPU and memory are"

ABOUT = """\
Status says how busy the processor and the memory are, as percentages.
"how busy are you" and "performance" reach it too.
How many gigabytes are actually in use, and how many cores this PC has,
are written here underneath.
The processor figure is measured over a moment rather than read off
instantly, so it takes about half a second to answer.\
"""


def run():
    # Without an interval, cpu_percent() averages since some arbitrary earlier call.
    cpu = psutil.cpu_percent(interval=0.4)
    memory = psutil.virtual_memory()
    say(f"CPU {round(cpu)} percent, memory {round(memory.percent)} percent")
    detail(f"  {memory.used / 1024 ** 3:.1f} of {memory.total / 1024 ** 3:.1f} GB in use, "
           f"{psutil.cpu_count(logical=True)} cores")
