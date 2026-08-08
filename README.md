<div align="center">

# Hard2Assist

**Talk to your PC. It listens, does the thing, and tells you it did.**

Hard2Assist is a voice assistant for Windows. Say **"computer"** followed by a command
and it opens programs and websites, closes windows, controls volume and media playback,
and answers questions about your PC — battery, time, disk space, CPU load — out loud.
It ships as a single `.exe` with everything packed inside, so there is nothing to install.

<img src="docs/window.png" alt="The Hard2Assist window, listening" width="560">

</div>

---

## Setup

### Option 1 — the .exe (recommended)

Download (or build, see below) `Hard2Assist.exe` and double-click it. That is the whole
setup: Python and every library are bundled inside the file.

You only need two things:

- 🎤 **a microphone**
- 🌐 **an internet connection** — recognition uses Google's free speech API

### Option 2 — run from source

```
pip install -r requirements.txt
python hard2assist.py             # the window
python hard2assist.py --console   # the same thing in a terminal, no window
```

### Building the .exe yourself

```
pip install -r requirements.txt
pip install pyinstaller
python build.py
```

That writes `dist\Hard2Assist.exe`. Copy that one file anywhere. After building, open it
and say `computer help` — seeing every command listed is how you know the build is
complete, because a build missing a piece still starts and looks fine.

---

## How to use

Start Hard2Assist, wait for **LISTENING**, then say **"computer"** followed by what
you want:

| Say this | And it |
| --- | --- |
| `computer open notepad` | launches an app, a program, or a website |
| `computer open obs studio` | opens anything in your Start Menu — no setup |
| `computer open youtube` | opens the site in your browser |
| `computer close notepad` | closes it, letting it save first |
| `computer kill notepad` | forces it to stop |
| `computer time` | 🔊 *"It's 8:02 pm"* |
| `computer date` | 🔊 *"It's Friday, August 8"* |
| `computer battery` | 🔊 *"82 percent, charging"* |
| `computer status` | 🔊 *"CPU 12 percent, memory 46 percent"* |
| `computer disk` | 🔊 *"C has 58 gigabytes free"* |
| `computer volume 50` | sets it to exactly 50%. "fifty" works too |
| `computer volume up` | louder. `down` and `mute` too |
| `computer play` | play or pause whatever is playing |
| `computer next` | skip a track. `back` for the previous one |
| `computer search how to cook rice` | opens the results in your browser |
| `computer help` | lists everything it knows |
| `computer stop` | quits |

Every command confirms what it did, and the log keeps the whole conversation:

<div align="center">
<img src="docs/session.png" alt="A session: opening notepad, checking time and battery, setting the volume, and a corrected mishearing" width="560">
</div>

A few things worth knowing while you use it:

- **It talks back.** Short answers are spoken; long lists are written to the window
  instead, so `computer help` says *"I know 17 commands and 139 apps, they're on screen"*
  rather than reading all of them out. Say `computer quiet` to silence it and
  `computer speak` to turn the voice back on.

- **It knows what is on your PC.** Every shortcut in your Start Menu is found at
  startup — over a hundred programs on a typical machine — so `computer open obs studio`
  works without any configuration. Install something new and it works next time you
  start. Say `computer help` to see the full list:

  <div align="center">
  <img src="docs/help.png" alt="The help command listing every command on screen" width="560">
  </div>

- **If it does not know something, it asks.** Say `computer open photoshop` for a
  program it has not found and a file picker opens. Click the program once and it is
  remembered forever, in `%APPDATA%\Hard2Assist\my-apps.json`. (You cannot dictate
  `C:\Program Files\...` out loud, so it does not ask you to.)

- **It expects to be misheard.** Speech recognition hears **"clothes"** when you say
  **"close"**, nearly every time. Commands carry a list of what they actually get
  misheard as, and anything still unmatched goes through fuzzy matching. It always
  tells you when it corrects something — you can see it in the screenshot above:

  ```
  > clothes notepad
  (heard 'clothes', taking it as 'close')
  ```

  App names get the same treatment: `computer open ccleaner` finds *CCleaner 7*, and
  `computer open obs` finds *OBS Studio*.

- **`close` closes the right window.** `close cmd` closes the **most recently opened**
  cmd, so opening one by voice and closing it leaves the one you were already working
  in alone. `close all cmd` closes every one.

- **It does not hear itself.** While it speaks, the microphone is off. Otherwise it
  would hear *"Closing one window"*, pick the word *close* out of it, and set off again.

---

## Adding your own

### A command

Drop a file in any folder under `commands/`:

```python
from output import say

NAME = "greet"
TAKES_ARG = False
ALIASES = ("greeting", "great")   # what the recogniser might hear instead
HELP = "greet        -- say hello"

def run():
    say("Hello!")
```

It is picked up on the next start and `help` lists it automatically. Use
`TAKES_ARG = True` and `run(argument)` to receive the rest of the sentence.

**`say()` writes and speaks. `detail()` only writes.** Speaking is the default so a new
command is never accidentally silent — reach for `detail()` only when the output is a
list or a long explanation nobody would want read aloud.

This works with the built .exe too: put a `commands` folder next to `Hard2Assist.exe`,
drop the file in, restart. No rebuild needed.

### An app or a website

One line in `apps/system.py` or `apps/websites.py`:

```python
App("notepad", "notepad", "Notepad")
#    name      launch      window title

site("youtube", "https://www.youtube.com")
```

`launch` goes to the Windows shell, so an exe, a `.msc` console, a `ms-settings:` URI,
a `.lnk` shortcut or a URL all work.

---

## Project layout

```
hard2assist.py      entry point -- the window, or --console
gui.py              the window
theme.py            colours and fonts, all in one place
listener.py         the microphone loop
speech.py           the voice
registry.py         finds commands, works out which one you meant
output.py           say() writes and speaks, detail() only writes
ask.py              asking you for a file mid-command
win.py              the only Windows API code
audio.py            reading and setting the exact volume
build.py            builds the .exe

commands/
  TextCommands/     answers      help time date battery status disk
  SystemApps/       acting       open close kill
  Controls/         the PC       volume play next back quiet speak stop
  Web/              online       search

apps/
  app.py            what an app is -- name, how to launch it, how to find its window
  system.py         built into Windows
  installed.py      found in your Start Menu, plus ones you picked
  websites.py       sites
```

---

## Known limits

- **Elevated apps.** Device Manager, Services, Registry Editor and friends can run as
  administrator. Windows will not let a normal program send window messages to one, so
  `close` reports that it was refused rather than pretending. `kill` usually still
  works. Run Hard2Assist as administrator to `close` them.
- **Closing Start Menu programs is best-effort.** They are found by window title, which
  does not always match the shortcut name. Programs you pick yourself are matched by
  their process and close reliably. Opening always works.
- **Speech needs the internet.** There is no offline recognition.
