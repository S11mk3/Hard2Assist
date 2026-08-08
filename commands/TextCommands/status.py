"""Report how busy the CPU and memory are."""

import psutil

from output import detail, say

NAME = "status"
TAKES_ARG = False
ALIASES = ("stats", "statue", "system", "performance")
HELP = "status       -- how busy the CPU and memory are"


def run():
    # Sample over a short interval; without one, cpu_percent() returns the
    # average since some arbitrary earlier call, which is meaningless here.
    cpu = psutil.cpu_percent(interval=0.4)
    memory = psutil.virtual_memory()

    say(f"CPU {round(cpu)} percent, memory {round(memory.percent)} percent")

    used = memory.used / (1024 ** 3)
    total = memory.total / (1024 ** 3)
    detail(f"  {used:.1f} of {total:.1f} GB in use, "
           f"{psutil.cpu_count(logical=True)} cores")
