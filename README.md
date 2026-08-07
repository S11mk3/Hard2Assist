# Hard2Assist

Computer Voice Commander. Say "computer" followed by a command and it does it.

Windows only -- it uses the Windows API to find and close app windows.

## Using it

Run `Hard2Assist.exe`. A small window opens and starts listening.

- **Speak**: say "computer open notepad".
- **Or type**: use the box at the bottom. The word "computer" is optional there,
  so it works with no microphone.
- **Stop listening**: the button pauses the microphone without quitting.
- **Quit**: the X button. The microphone is released -- nothing keeps listening
  in the background.

Speech recognition uses Google's free API, so it needs an internet connection.
Typed commands work offline.

## Commands

| Say | Does |
| --- | --- |
| `computer open notepad` | launches an app |
| `computer close notepad` | closes it, letting it save first |
| `computer kill notepad` | forces it to stop, without saving |
| `computer close all notepad` | closes every notepad window |
| `computer help` | lists every command and app |
| `computer stop` | quits |

`close` asks the window to close, the same as clicking its X, so anything with
unsaved work will still prompt you. `kill` does not ask. Use `close` unless it
won't work.

### Which window gets closed

`close cmd` closes the **most recently opened** cmd, so opening one by voice and
then closing it leaves your own windows alone. `close all cmd` closes every one.

The one case this gets wrong: if you open a cmd by hand *after* the one
Hard2Assist opened, that newer one is what `close cmd` targets.

### Apps that run as administrator

Some apps run at a higher privilege level than Hard2Assist -- Device Manager,
Services, Disk Management, Computer Management, Event Viewer and Registry
Editor all can. Windows will not let a normal program send window messages to
one of those, so `close` reports that it was refused rather than pretending it
worked. `kill` often still gets them. To use `close` on them, start
Hard2Assist as administrator.

## Building the .exe

    pip install -r requirements.txt
    python build.py

That writes `dist\Hard2Assist.exe`. Python and every library are packed inside
it, so you can copy that single file to a Windows PC with nothing installed and
it will run.

## Running from source

    pip install -r requirements.txt
    python hard2assist.py

`python hard2assist.py --console` runs it in the terminal with no window, which
is easier to debug.

## Adding a command

Drop a file in `commands/<any folder>/`:

```python
from output import say

NAME = "greet"
TAKES_ARG = False
HELP = "greet        -- say hello"

def run():
    say("Hello!")
```

It is picked up on the next start, and `help` lists it automatically. Set
`TAKES_ARG = True` and take a `run(argument)` to get the rest of the sentence.

Use `say()` rather than `print()` -- the built .exe has no console, so a
`print()` would go nowhere or raise.

This works with the .exe too: put a `commands` folder next to
`Hard2Assist.exe`, drop your file in, and restart. No rebuild needed.

## Adding an app

Add one line to the `APPS` list in `apps.py`:

```python
App("notepad", "notepad", "Notepad")
#    name      launch      window title
```

`launch` goes to the Windows shell, so an exe, a `.msc` console or a
`ms-settings:` URI all work. `title` is how `close` and `kill` find the window
once it is open -- a substring is enough. `aliases=(...)` adds other things you
might say, including misspellings the recogniser tends to produce.

## Layout

| File | Does |
| --- | --- |
| `hard2assist.py` | entry point -- window, or `--console` |
| `gui.py` | the window |
| `listener.py` | the microphone loop |
| `registry.py` | finds command modules, decides which one you asked for |
| `apps.py` | the app catalogue |
| `win.py` | the only Windows API code |
| `output.py` | routes messages to the log or the terminal |
| `build.py` | builds the .exe |
| `commands/` | one file per command |
