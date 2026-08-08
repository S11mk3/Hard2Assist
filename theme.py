"""Colours and fonts, in one place so the look is easy to change.

Black background, cyan accent, white text.
"""

BG = "#08090b"          # the window
PANEL = "#0d0f13"       # the log area, a shade lighter so it reads as a panel
LINE = "#1b2027"        # hairline dividers

ACCENT = "#22d3ee"      # cyan -- the app is alive and listening
ACCENT_DIM = "#0e7490"  # cyan, faded, for the outer pulse
TEXT = "#33ff00"        # normal text
DIM = "#6b7683"         # grey, hints and less important lines
WARN = "#f59e0b"        # amber, something did not work

TITLE_FONT = ("Segoe UI", 10, "bold")
STATE_FONT = ("Segoe UI Semibold", 19)
HINT_FONT = ("Segoe UI", 10)
LOG_FONT = ("Consolas", 10)


def blend(colour_a, colour_b, amount):
    """Mix two #rrggbb colours. amount=0 gives a, amount=1 gives b."""
    a = [int(colour_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(colour_b[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(x + (y - x) * amount) for x, y in zip(a, b)]
    return "#%02x%02x%02x" % tuple(mixed)
