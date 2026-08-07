"""How much disk space is left."""

import psutil

from output import announce, say

NAME = "disk"
TAKES_ARG = False
ALIASES = ("disc", "storage", "space", "drive")
HELP = "disk         -- how much drive space is free"


def run():
    reported = []

    for part in psutil.disk_partitions(all=False):
        # Skip anything with no disc in it -- an empty card reader or DVD drive
        # raises rather than reporting zero.
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue

        free = usage.free / (1024 ** 3)
        total = usage.total / (1024 ** 3)
        drive = part.mountpoint.rstrip("\\")
        reported.append((drive, free, total, usage.percent))

    if not reported:
        announce("I could not read any drives.")
        return

    first = reported[0]
    announce(f"{first[0]} has {round(first[1])} gigabytes free")

    for drive, free, total, percent in reported:
        say(f"  {drive}  {free:.0f} GB free of {total:.0f} GB  ({percent:.0f}% used)")
