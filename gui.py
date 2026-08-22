"""The Hard2Assist window.

A pulsing dot showing whether the app is listening, a status line, a hint
line, and a log panel that everything the commands say or write scrolls into.
The microphone runs on a background thread; messages cross into the Tk thread
through a queue.
"""

import math
import os
import queue
import sys
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
import theme
import win
import wizard

WINDOW_SIZE = "860x640"
HINT_CLEAR_MS = 4000
ICON = "H2A.ico"

# How often the dot is redrawn, and how long one full breath takes.
PULSE_MS = 16
PULSE_PERIOD = 3.4

# The blend is quantised to this many steps. Tk allocates a colour for every
# distinct string it is given, so a fresh one per frame makes the canvas do
# far more work than the eye can see across these two narrow ranges.
PULSE_STEPS = 40

def default_hint():
    """The resting hint line, built with the live wake word so it stays right
    after `customize` changes it."""
    return f'say "{settings.get("prefix")} help" to hear what I can do'

# The listener reports its state in full sentences, which suit the console.
# The window's state label wants one short word instead.
STATES = {
    "Listening": "LISTENING",
    "Paused": "PAUSED",
    "Not in focus": "NOT IN FOCUS",
    "No microphone found": "NO MICROPHONE",
    "Microphone stopped": "MIC STOPPED",
    "Calibrating for background noise...": "CALIBRATING",
    listener.SETUP: "SETTING UP",
}


class App:
    """The window, its widgets, and the threads feeding them."""

    def __init__(self, root):
        self.root = root
        self.messages = queue.Queue()

        # Commands run one at a time, whichever thread asked for one.
        self.command_lock = threading.Lock()
        self._hint_job = None

        # When the current spell of listening began, or None while at rest.
        self._pulse_start = None

        # Last colour given to each canvas item, so an unchanged one is not
        # re-sent every frame.
        self._colours = {}

        self._listening = False
        self._last_speech_error = ""
        self._said_muted = False

        self._build_widgets()

        # Route everything the commands say() into the log panel instead of a
        # console; the built .exe does not have one.
        output.on_message(self.log_from_any_thread)

        # `open` needs a file path when it meets an unknown program, and a
        # path cannot be dictated, so the window provides a file picker.
        ask.on_request(self.ask_for_program)

        self.commands = registry.load()
        if self.commands:
            # Put something in the log immediately, so the panel does not look
            # broken before the first command.
            tally = apps.counts()
            self.log(f"Ready. {len(self.commands)} commands, "
                     f"{sum(tally.values())} apps "
                     f"({tally.get('installed', 0)} found on this PC).",
                     tag="dim")
        else:
            self.log("No commands were found, so there is nothing to do.")

        self.listener = listener.Listener(
            on_command=self.run_command,
            on_status=self.status_from_any_thread,
            on_ready=wizard.on_ready,
            may_listen=self.may_listen,
        )

        # Mute the microphone while speaking, or the app hears its own replies
        # ("Closing one window") and acts on the word "close".
        if speech.start():
            speech.on_speaking(self.listener.pause, self.listener.resume)
        else:
            self.log("No voice available on this PC -- replies will be "
                     "written only.", tag="dim")

        self.mic_thread = threading.Thread(target=self.listener.run, daemon=True)
        self.mic_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(100, self._drain)
        self.root.after(PULSE_MS, self._animate)
        self.root.after(2000, self._watch_speech)

    # -- layout ----------------------------------------------------------------

    def _build_widgets(self):
        """Create the window and everything in it."""
        self.root.title("Hard2Assist")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(420, 380)
        self.root.configure(bg=theme.BG)
        self._set_icon()

        tk.Label(
            self.root, text="H A R D 2 A S S I S T", font=theme.TITLE_FONT,
            bg=theme.BG, fg=theme.DIM,
        ).pack(pady=(16, 0))

        # The pulsing dot: animated while listening, still and grey otherwise.
        self.canvas = tk.Canvas(
            self.root, width=120, height=120, bg=theme.BG,
            highlightthickness=0,
        )
        self.canvas.pack(pady=(14, 0))
        self.ring = self.canvas.create_oval(0, 0, 0, 0, outline=theme.ACCENT_DIM)
        self.dot = self.canvas.create_oval(0, 0, 0, 0, fill=theme.ACCENT, width=0)

        # Both are created with no size, so give them the resting shape now:
        # _animate() only redraws the dot at rest when it transitions there.
        self._draw(None)

        self.state = tk.StringVar(value="STARTING")
        tk.Label(
            self.root, textvariable=self.state, font=theme.STATE_FONT,
            bg=theme.BG, fg=theme.TEXT,
        ).pack(pady=(10, 0))

        self.hint = tk.StringVar(value=default_hint())
        tk.Label(
            self.root, textvariable=self.hint, font=theme.HINT_FONT,
            bg=theme.BG, fg=theme.DIM, wraplength=560,
        ).pack(pady=(4, 14))

        tk.Frame(self.root, bg=theme.LINE, height=1).pack(fill="x", padx=22)

        # A plain Text widget rather than ScrolledText: a native scrollbar
        # would be the only piece of grey Windows chrome in a dark window, and
        # the log auto-scrolls to the end anyway.
        self.log_box = tk.Text(
            self.root, wrap="word", state="disabled", font=theme.LOG_FONT,
            bg=theme.PANEL, fg=theme.TEXT, insertbackground=theme.TEXT,
            relief="flat", highlightthickness=0, padx=14, pady=10,
        )
        self.log_box.pack(fill="both", expand=True, padx=0, pady=0)

        self.log_box.tag_configure("command", foreground=theme.ACCENT)
        self.log_box.tag_configure("normal", foreground=theme.TEXT)
        self.log_box.tag_configure("warn", foreground=theme.WARN)
        self.log_box.tag_configure("dim", foreground=theme.DIM)

    def _set_icon(self):
        """Set the title bar and taskbar icon.

        The .exe file carries the icon, but the running window needs it set
        explicitly too. Inside the bundle the .ico lives in PyInstaller's
        unpacked folder (sys._MEIPASS).
        """
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, ICON)

        if not os.path.isfile(path):
            # Not worth failing over; the window gets the default icon.
            return

        try:
            # default= applies the icon to the whole application, which is
            # what the taskbar reads; the second call covers this window.
            self.root.iconbitmap(default=path)
            self.root.iconbitmap(path)
        except tk.TclError:
            pass

    # -- the pulse -------------------------------------------------------------

    def _animate(self):
        """Advance the pulse and reschedule.

        The phase comes from the clock rather than a fixed step per frame. Tk
        delivers after() callbacks late whenever the log panel or the
        microphone thread is busy, and a fixed step turns every late callback
        into a visible stall; reading the clock makes a late frame take a
        longer step instead.
        """
        if self._listening:
            if self._pulse_start is None:
                self._pulse_start = time.monotonic()

            turn = ((time.monotonic() - self._pulse_start)
                    * (2 * math.pi / PULSE_PERIOD))

            # (1 - cos)/2 rather than (sin + 1)/2, so each spell of listening
            # opens from the resting size instead of jumping to mid-breath.
            self._draw((1 - math.cos(turn)) / 2)

        elif self._pulse_start is not None:
            # Just stopped listening: settle back to the resting dot, once.
            self._pulse_start = None
            self._draw(None)

        self.root.after(PULSE_MS, self._animate)

    def _draw(self, breathe):
        """Paint the dot and ring. `breathe` runs 0..1, or None for at rest."""
        centre, base = 60, 13

        if breathe is None:
            radius, ring_radius = base, base + 6
            dot_colour, ring_colour = theme.DIM, theme.LINE
        else:
            radius = base + breathe * 3
            ring_radius = base + 6 + breathe * 26

            shade = round(breathe * PULSE_STEPS) / PULSE_STEPS
            dot_colour = theme.blend(theme.ACCENT_DIM, theme.ACCENT, shade)
            # The ring expands outward while fading into the background.
            ring_colour = theme.blend(theme.ACCENT_DIM, theme.BG, shade)

        self._paint(self.dot, "fill", dot_colour)
        self._paint(self.ring, "outline", ring_colour)

        self.canvas.coords(
            self.dot,
            centre - radius, centre - radius, centre + radius, centre + radius,
        )
        self.canvas.coords(
            self.ring,
            centre - ring_radius, centre - ring_radius,
            centre + ring_radius, centre + ring_radius,
        )

    def _paint(self, item, option, colour):
        """Recolour a canvas item, skipping the call when nothing changed."""
        if self._colours.get(item) == colour:
            return

        self._colours[item] = colour
        self.canvas.itemconfigure(item, **{option: colour})

    # -- messages between threads ----------------------------------------------

    def log_from_any_thread(self, text):
        """Queue a log line from the microphone thread."""
        self.messages.put(("log", text))

    def status_from_any_thread(self, text, transient=False):
        """Queue a status change from the microphone thread."""
        self.messages.put(("status", text, transient))

    def _drain(self):
        """Move queued messages from the microphone thread into the widgets."""
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "log":
                    self.log(message[1])
                else:
                    self.set_status(message[1], message[2])
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    # -- widgets ---------------------------------------------------------------

    def log(self, text, tag=None):
        """Append a line to the log panel, colour-coded by content."""
        if tag is None:
            if text.startswith(">"):
                tag = "command"
            elif text.startswith(("Could not", "I could not", "I don't know",
                                  "Not allowed", "Windows won't",
                                  "Windows would not", "Windows wouldn't",
                                  "I won't", "I can't reach",
                                  "The microphone stopped")):
                tag = "warn"
            else:
                tag = "normal"

        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_status(self, text, transient=False):
        """Update the state label, or flash a transient message on the hint line."""
        if transient:
            self.hint.set(text)
            if self._hint_job is not None:
                self.root.after_cancel(self._hint_job)
            self._hint_job = self.root.after(HINT_CLEAR_MS, self._restore_hint)
            return

        self.state.set(STATES.get(text, text.upper().rstrip(".")))
        self._listening = text == "Listening"

    def _restore_hint(self):
        """Put the default hint back after a transient message."""
        self._hint_job = None
        self.hint.set(default_hint())

    def _watch_speech(self):
        """Report it in the log if the voice stops working, then reschedule.

        Failing silently would leave the user wondering whether the app heard
        them at all.
        """
        problem = speech.error()
        if problem and problem != self._last_speech_error:
            self._last_speech_error = problem
            self.log(f"I could not speak that: {problem}", tag="warn")

        if speech.available() and not speech.enabled():
            if not self._said_muted:
                self._said_muted = True
                self.log(f"Speaking is off. Say '{settings.get('prefix')} "
                         "speak' to turn it back on.", tag="dim")
        else:
            self._said_muted = False

        self.root.after(2000, self._watch_speech)

    # -- running commands ------------------------------------------------------

    def may_listen(self):
        """Whether the "listen only while in focus" setting is satisfied.

        Read live rather than captured at startup, so changing it through
        `customize` takes effect straight away.
        """
        if settings.get("listen_when") == "always":
            return True
        return win.foreground_is_ours()

    def run_command(self, command):
        """Run one command. Called from the microphone thread."""
        with self.command_lock:
            self.log_from_any_thread(f"> {command}")
            try:
                result = registry.dispatch(self.commands, command)
            except Exception as e:
                self.log_from_any_thread(f"Could not run that: {e}")
                return

        if result is registry.STOP:
            self.root.after(0, self.quit)

    def ask_for_program(self, name):
        """Open the file picker and wait for the chosen path.

        Called from the microphone thread, but tkinter dialogs must run on the
        thread that owns the window: the dialog is scheduled with after() and
        this thread blocks on an event until it is answered.
        """
        answer = {}
        done = threading.Event()

        def show():
            try:
                answer["path"] = filedialog.askopenfilename(
                    parent=self.root,
                    title=f"Where is {name}?",
                    filetypes=[("Programs", "*.exe;*.lnk"), ("All files", "*.*")],
                )
            finally:
                done.set()

        self.root.after(0, show)

        # Time out eventually, so a dialog left open forever does not wedge
        # the command thread for the rest of the session.
        done.wait(timeout=180)
        return answer.get("path") or None

    def quit(self):
        """Stop the microphone and the voice, then close the window."""
        self.listener.stop()
        speech.stop()
        # Discard anything logged from here on: the widgets are being torn
        # down, and the built .exe has no console to fall back to.
        output.on_message(lambda _text: None)
        self.root.destroy()


def run():
    """Open the window and run until it is closed."""
    root = tk.Tk()
    App(root)
    root.mainloop()
