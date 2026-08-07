"""How hard the PC is working."""

import psutil

from output import detail, say

NAME = "status"
TAKES_ARG = False
ALIASES = ("stats", "statue", "system", "performance")
HELP = "status       -- how busy the CPU and memory are"


def run():
    # A short sample, otherwise cpu_percent returns whatever it measured since
    # some arbitrary earlier moment, which is usually nonsense.
    cpu = psutil.cpu_percent(interval=0.4)
    memory = psutil.virtual_memory()

    say(f"CPU {round(cpu)} percent, memory {round(memory.percent)} percent")

    used = memory.used / (1024 ** 3)
    total = memory.total / (1024 ** 3)
    detail(f"  {used:.1f} of {total:.1f} GB in use, "
        f"{psutil.cpu_count(logical=True)} cores")
