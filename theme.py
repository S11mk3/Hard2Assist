"""Colours and fonts, kept in one place so the look is easy to change.

Dark background, cyan accent, white log text.
"""

BG = "#08090b"          # window background
PANEL = "#0d0f13"       # log area, one shade lighter so it reads as a panel
LINE = "#1b2027"        # hairline dividers

ACCENT = "#22d3ee"      # cyan: the app is alive and listening
ACCENT_DIM = "#0e7490"  # faded cyan, used by the outer pulse ring
TEXT = "#fcfdfc"        # normal log text
DIM = "#6b7683"         # grey: hints and secondary lines
WARN = "#f59e0b"        # amber: something did not work

TITLE_FONT = ("Segoe UI", 11, "bold")
STATE_FONT = ("Segoe UI Semibold", 22)
HINT_FONT = ("Segoe UI", 12)
LOG_FONT = ("Consolas", 13)


def blend(colour_a, colour_b, amount):
    """Mix two #rrggbb colours. amount=0 gives colour_a, amount=1 gives colour_b."""
    a = [int(colour_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(colour_b[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(x + (y - x) * amount) for x, y in zip(a, b)]
    return "#%02x%02x%02x" % tuple(mixed)
