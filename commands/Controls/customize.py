"""Go through the setup conversation again."""

import wizard

NAME = "customize"
TAKES_ARG = False
ALIASES = ("customise", "settings", "setup", "preferences", "configure")
HELP = "customize    -- change the wake word and how I listen"


def run():
    # Runs on the microphone thread, which is exactly where the conversation
    # needs to be: the audio source is open and owned by this thread.
    wizard.run()
