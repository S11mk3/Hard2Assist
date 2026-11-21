"""The Hard2Assist window: a dot that breathes while listening, a status line, a hint line, the
log of everything said and done, and a box to type a command into.

The microphone runs on a background thread; its messages reach the Tk thread through a queue.
"""

import math
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog

import apps
import ask
import listener
import output
import registry
import settings
import speech
import storage
import theme
import win
import wizard
from output import log

WINDOW_SIZE = "860x640"
HINT_CLEAR_MS = 4000
MAX_LOG_LINES = 2000

PULSE_MS = 16         # how often the dot is redrawn
PULSE_PERIOD = 3.4    # seconds per breath
# Tk allocates a colour for every distinct string, so the blend is quantised to this many steps.
PULSE_STEPS = 40

# The listener's statuses are sentences for the console; the window shows one word.
STATES = {
    "Listening": "LISTENING",
    "Paused": "PAUSED",
    "Not in focus": "NOT IN FOCUS",
    "No microphone found": "NO MICROPHONE",
    "Microphone stopped": "MIC STOPPED",
    "Calibrating for background noise...": "CALIBRATING",
    listener.SETUP: "SETTING UP",
}


def default_hint():
    """Built with the live wake word, so it stays right after `customize` changes it."""
    return f'say "{settings.get("prefix")} help" to hear what I can do, or type below'


class App:
    """The window, its widgets, and the threads feeding them."""

    def __init__(self, root):
        self.root = root
        self.messages = queue.Queue()
        self._hint_job = None
        self._pulse_start = None   # when the current spell of listening began
        self._colours = {}         # last colour per canvas item, so unchanged ones are not re-sent
        self._listening = False
        self._last_speech_error = ""
        self._said_muted = False
        self._said_no_voice = False

        self._build_widgets()
        root.report_callback_exception = self._crashed
        output.on_message(lambda text, tag=None: self.messages.put(("log", text, tag)))
        ask.on_request(self.ask_for_program)

        self.commands = registry.load()
        if not self.commands:
            self.log("No commands were found, so there is nothing to do.", "warn")

        self.listener = listener.Listener(
            on_command=self.run_command,
            on_status=lambda text, transient=False: self.messages.put(("status", text, transient)),
            on_ready=wizard.on_ready,
            may_listen=self.may_listen,
            opens_with_command=registry.opens_with_command,
        )
        speech.on_speaking(self.listener.pause, self.listener.resume)
        speech.start()

        # The Start Menu and Store scans are read off the Tk thread, so the window opens at once.
        threading.Thread(target=self._count_apps, daemon=True, name="catalogue").start()
        threading.Thread(target=self.listener.run, daemon=True, name="microphone").start()

        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(100, self._drain)
        root.after(PULSE_MS, self._animate)
        root.after(2000, self._watch_speech)

    # -- layout --

    def _build_widgets(self):
        root = self.root
        root.title("Hard2Assist")
        root.geometry(WINDOW_SIZE)
        root.minsize(420, 380)
        root.configure(bg=theme.BG)
        self._set_icon()

        tk.Label(root, text="H A R D 2 A S S I S T", font=theme.TITLE_FONT,
                 bg=theme.BG, fg=theme.DIM).pack(pady=(16, 0))

        self.canvas = tk.Canvas(root, width=120, height=120, bg=theme.BG, highlightthickness=0)
        self.canvas.pack(pady=(14, 0))
        self.ring = self.canvas.create_oval(0, 0, 0, 0, outline=theme.ACCENT_DIM)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, fill=theme.ACCENT, width=0)
        self._draw(None)

        self.state = tk.StringVar(value="STARTING")
        tk.Label(root, textvariable=self.state, font=theme.STATE_FONT,
                 bg=theme.BG, fg=theme.TEXT).pack(pady=(10, 0))

        self.hint = tk.StringVar(value=default_hint())
        tk.Label(root, textvariable=self.hint, font=theme.HINT_FONT, bg=theme.BG, fg=theme.DIM,
                 wraplength=560).pack(pady=(4, 14))

        tk.Frame(root, bg=theme.LINE, height=1).pack(fill="x", padx=22)

        # Packed before the log, which expands, so a small window cannot squeeze it out.
        typing = tk.Frame(root, bg=theme.PANEL)
        typing.pack(side="bottom", fill="x")
        tk.Frame(root, bg=theme.LINE, height=1).pack(side="bottom", fill="x")
        tk.Label(typing, text=">", font=theme.LOG_FONT, bg=theme.PANEL,
                 fg=theme.ACCENT).pack(side="left", padx=(14, 6))
        self.entry = tk.Entry(typing, font=theme.LOG_FONT, bg=theme.PANEL, fg=theme.TEXT,
                              insertbackground=theme.TEXT, relief="flat", highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 14))
        self.entry.bind("<Return>", self._submit)
        self.entry.focus_set()   # so typing into the window goes straight into the box

        # A plain Text rather than ScrolledText: a native scrollbar would be the one piece of grey
        # Windows chrome in a dark window, and the log follows the end anyway.
        self.log_box = tk.Text(root, wrap="word", state="disabled", font=theme.LOG_FONT,
                               bg=theme.PANEL, fg=theme.TEXT, insertbackground=theme.TEXT,
                               relief="flat", highlightthickness=0, padx=14, pady=10)
        self.log_box.pack(fill="both", expand=True)
        for tag, colour in (("command", theme.ACCENT), ("normal", theme.TEXT),
                            ("warn", theme.WARN), ("dim", theme.DIM)):
            self.log_box.tag_configure(tag, foreground=colour)

    def _set_icon(self):
        """The .exe carries the icon, but the running window needs it set too."""
        path = os.path.join(storage.BUNDLE_DIR, "H2A.ico")
        if os.path.isfile(path):
            try:
                self.root.iconbitmap(default=path)   # the whole app, which the taskbar reads
                self.root.iconbitmap(path)           # and this window
            except tk.TclError:
                pass

    # -- the pulse --

    def _animate(self):
        """Advance the pulse. The phase comes from the clock, so a late frame takes a longer step
        rather than stalling."""
        if self._listening:
            if self._pulse_start is None:
                self._pulse_start = time.monotonic()
            turn = (time.monotonic() - self._pulse_start) * (2 * math.pi / PULSE_PERIOD)
            # (1 - cos)/2, so each spell of listening starts from the resting size.
            self._draw((1 - math.cos(turn)) / 2)
        elif self._pulse_start is not None:
            self._pulse_start = None
            self._draw(None)
        self.root.after(PULSE_MS, self._animate)

    def _draw(self, breathe):
        """Paint the dot and ring. breathe runs 0..1, or None for at rest."""
        centre, base = 60, 13
        if breathe is None:
            radius, ring_radius = base, base + 6
            dot_colour, ring_colour = theme.DIM, theme.LINE
        else:
            radius, ring_radius = base + breathe * 3, base + 6 + breathe * 26
            shade = round(breathe * PULSE_STEPS) / PULSE_STEPS
            dot_colour = theme.blend(theme.ACCENT_DIM, theme.ACCENT, shade)
            ring_colour = theme.blend(theme.ACCENT_DIM, theme.BG, shade)   # fades as it grows

        for item, option, colour, size in ((self.dot, "fill", dot_colour, radius),
                                           (self.ring, "outline", ring_colour, ring_radius)):
            if self._colours.get(item) != colour:
                self._colours[item] = colour
                self.canvas.itemconfigure(item, **{option: colour})
            self.canvas.coords(item, centre - size, centre - size, centre + size, centre + size)

    # -- messages from other threads --

    def _drain(self):
        try:
            while True:
                kind, text, extra = self.messages.get_nowait()
                if kind == "log":
                    self.log(text, extra)
                else:
                    self.set_status(text, extra)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def log(self, text, tag=None):
        if tag is None:
            tag = "command" if text.startswith(">") else "normal"
        box = self.log_box
        box.configure(state="normal")
        box.insert("end", text + "\n", tag)
        excess = int(box.index("end-1c").split(".")[0]) - MAX_LOG_LINES
        if excess > 0:
            box.delete("1.0", f"{excess + 1}.0")
        box.see("end")
        box.configure(state="disabled")

    def set_status(self, text, transient=False):
        """Set the state label, or flash a transient message on the hint line."""
        if transient:
            self.hint.set(text)
            if self._hint_job is not None:
                self.root.after_cancel(self._hint_job)
            self._hint_job = self.root.after(HINT_CLEAR_MS, self._restore_hint)
            return
        self.state.set(STATES.get(text, text.upper().rstrip(".")))
        self._listening = text == "Listening"

    def _restore_hint(self):
        self._hint_job = None
        self.hint.set(default_hint())

    def _watch_speech(self):
        """Report in the log when the voice is missing, fails, or has been turned off."""
        if speech.started() and not speech.available():
            if not self._said_no_voice:
                self._said_no_voice = True
                self.log(f"No voice on this PC, so replies are only written. ({speech.error()})", "dim")
        elif speech.error() and speech.error() != self._last_speech_error:
            self._last_speech_error = speech.error()
            self.log(f"I could not speak that: {self._last_speech_error}", "warn")

        muted = speech.available() and not speech.enabled()
        if muted and not self._said_muted:
            self.log(f"Speaking is off. Say '{settings.get('prefix')} speak' to turn it back on.", "dim")
        self._said_muted = muted
        self.root.after(2000, self._watch_speech)

    def _crashed(self, *exc_info):
        log.error("Window error", exc_info=exc_info)
        self.log(f"Something went wrong: {exc_info[1]} (details in {os.path.join(storage.USER_DIR, 'log.txt')})",
                 "warn")

    def _count_apps(self):
        tally = apps.counts()
        self.messages.put(("log", f"Ready. {len(self.commands)} commands, {sum(tally.values())} apps "
                                  f"({tally['installed']} found on this PC).", "dim"))

    # -- commands --

    def _submit(self, _event=None):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        if text:
            self.listener.submit(text)

    def may_listen(self):
        """Whether "only listen while in focus" allows listening now; read live, so `customize`
        takes effect at once."""
        return settings.get("listen_when") == "always" or win.foreground_is_ours()

    def run_command(self, command):
        """Called on the microphone thread, which waits for each command, so none overlap."""
        if registry.run(command) is registry.STOP:
            self.root.after(0, self.quit)

    def ask_for_program(self, name):
        """The file picker, for the microphone thread: Tk dialogs must run on the Tk thread, so
        it is scheduled there and this thread waits for the answer."""
        answer = {}
        done = threading.Event()

        def show():
            try:
                answer["path"] = filedialog.askopenfilename(
                    parent=self.root, title=f"Where is {name}?",
                    filetypes=[("Programs", "*.exe;*.lnk"), ("All files", "*.*")])
            finally:
                done.set()

        self.root.after(0, show)
        done.wait(timeout=180)   # a picker left open must not wedge the microphone thread for good
        return answer.get("path") or None

    def quit(self):
        self.listener.stop()
        speech.stop()
        output.on_message(lambda _text, _tag=None: None)   # the widgets are going away
        self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
