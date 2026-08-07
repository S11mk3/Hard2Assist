# Hard2Assist

Computer Voice Commander. Say "computer" followed by a command and it does it.

Windows only -- it uses the Windows API to find and close app windows.

## Install

    pip install -r requirements.txt

Speech recognition uses Google's free API, so it needs an internet connection.

If `pip install PyAudio` fails, install a prebuilt wheel instead:

    pip install pipwin && pipwin install pyaudio

## Run

    python hard2assist.py

It calibrates for background noise for a second, then listens. Ctrl+C or
"computer stop" quits.

## Commands

| Say | Does |
| --- | --- |
| `computer open notepad` | launches an app |
| `computer close notepad` | closes it, letting it save first |
| `computer kill notepad` | forces it to stop, without saving |
| `computer help` | lists every command and app |
| `computer stop` | quits |

`close` asks the window to close, the same as clicking its X, so anything with
unsaved work will still prompt you. `kill` does not ask. Use `close` unless it
won't work.

### Apps that run as administrator

Some apps run at a higher privilege level than Hard2Assist -- Device Manager,
Services, Disk Management, Computer Management, Event Viewer and Registry
Editor all can. Windows will not let a normal program send window messages to
one of those, so `close` reports that it was refused rather than pretending it
worked. `kill` often still gets them. To use `close` on them, start
Hard2Assist as administrator.

## Adding a command

Drop a file in `commands/<any folder>/`:

```python
NAME = "greet"
TAKES_ARG = False
HELP = "greet        -- say hello"

def run():
    print("Hello!")
```

It is picked up on the next start, and `help` lists it automatically. Set
`TAKES_ARG = True` and take a `run(argument)` to get the rest of the sentence.

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
| `hard2assist.py` | the listen loop |
| `registry.py` | finds command modules, decides which one you asked for |
| `apps.py` | the app catalogue |
| `win.py` | the only Windows API code |
| `commands/` | one file per command |
