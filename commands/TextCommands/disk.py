"""Report how much disk space is free."""

import psutil

from output import detail, say

NAME = "disk"
TAKES_ARG = False
ALIASES = ("disc", "storage", "space", "drive")
HELP = "disk         -- how much drive space is free"

ABOUT = """\
Disk says how much space is free on your main drive.
"how much space is left" and "storage" reach it too.
Every other drive is written here underneath, with how full each one is.
An empty card reader or DVD drive is skipped rather than reported as
zero.\
"""


def run():
    reported = []

    for part in psutil.disk_partitions(all=False):
        # Skip drives with no media in them: an empty card reader or DVD
        # drive raises here instead of reporting zero.
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue

        free = usage.free / (1024 ** 3)
        total = usage.total / (1024 ** 3)
        drive = part.mountpoint.rstrip("\\")
        reported.append((drive, free, total, usage.percent))

    if not reported:
        say("I could not read any drives.")
        return

    # Speak only the primary drive; the full per-drive breakdown is written.
    first = reported[0]
    say(f"{first[0]} has {round(first[1])} gigabytes free")

    for drive, free, total, percent in reported:
        detail(f"  {drive}  {free:.0f} GB free of {total:.0f} GB  ({percent:.0f}% used)")
