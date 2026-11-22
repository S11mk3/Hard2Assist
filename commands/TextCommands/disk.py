"""Report how much disk space is free."""

import os

import psutil

from output import detail, say, warn

NAME = "disk"
TAKES_ARG = False
ALIASES = ("disc",)
SYNONYMS = ("storage", "space", "drive")
HELP = "disk -- how much drive space is free"

ABOUT = """\
Disk says how much space is free on the drive Windows is on.
"how much space is left" and "storage" reach it too.
Every other drive is written here underneath, with how full each one is.
An empty card reader or DVD drive is skipped rather than reported as
zero.\
"""

GB = 1024 ** 3


def run():
    drives = []
    for part in psutil.disk_partitions(all=False):
        try:
            drives.append((part.mountpoint.rstrip("\\"), psutil.disk_usage(part.mountpoint)))
        except OSError:
            continue   # an empty card reader or DVD drive

    if not drives:
        warn("I could not read any drives.")
        return

    system = os.environ.get("SYSTEMDRIVE", "C:").upper()
    drives.sort(key=lambda entry: entry[0].upper() != system)   # Windows' own drive first

    drive, usage = drives[0]
    # "The C drive": the voice runs a bare "C drive" together into something else.
    say(f"The {drive.rstrip(':')} drive has {round(usage.free / GB)} gigabytes free")
    for drive, usage in drives:
        detail(f"  {drive}  {usage.free / GB:.0f} GB free of {usage.total / GB:.0f} GB  "
               f"({usage.percent:.0f}% used)")
