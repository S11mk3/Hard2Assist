"""Hard2Assist itself, so "focus yourself" has something to resolve to.

The window commands go through the same catalogue as everything else, and the
app was the one thing missing from it: without this entry, "computer focus
hard to assist" answered "I don't know an app called hard to assist".
"""

from .app import App

# launch is empty on purpose: `open` special-cases this entry and focuses the
# running window instead of starting a second copy, which would mean two
# microphones fighting over the same commands.
ITSELF = App(
    "hard2assist",
    launch="",
    title="Hard2Assist",
    # What the recogniser actually returns for the name -- it never spells
    # the digit -- plus the natural ways of pointing at the app itself.
    aliases=("hard to assist", "hard 2 assist", "heart to assist",
             "hard to assist app", "yourself", "you", "assistant"),
    protected=True,
    kind="itself",
)
