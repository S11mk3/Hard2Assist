"""Hard2Assist itself, so "focus yourself" and "minimize hard to assist" have something to find.

launch is empty: `open` brings the running window forward instead of starting a second copy.
"""

from .app import App

ITSELF = App(
    "hard2assist",
    launch="",
    title="Hard2Assist",
    # The recogniser never spells the digit.
    aliases=("hard to assist", "hard 2 assist", "heart to assist", "hard to assist app",
             "yourself", "you", "assistant"),
    kind="itself",
)
