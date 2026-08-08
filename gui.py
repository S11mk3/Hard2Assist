"""The Hard2Assist window.

A dark, mostly hands-off window: a pulsing dot that shows whether the app is
listening, a status line, a hint line, and a log panel that everything the
commands say or write scrolls into. The microphone runs on a background
thread; messages cross into the Tk thread through a queue.
"""

import math
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import apps
import ask
import listener
import output
import registry
import speech
import theme

WINDOW_SIZE = "800x600"
HINT_CLEAR_MS = 4000
PULSE_MS = 50
ICON = "H2A.ico"

DEFAULT_HINT = 'say "computer help" to hear what I can do'

# The listener reports its state in full sentences, which suit the console.
# The window's state label wants one short word instead.
STATES = {
    "Listening": "LISTENING",
    "Paused": "PAUSED",
    "No microphone found": "NO MICROPHONE",
    "Microphone stopped": "MIC STOPPED",
}


class App:
    def __init__(self, root):
        self.root = root
        self.messages = queue.Queue()

        # Commands run one at a time, whichever thread asked for one.
        self.command_lock = threading.Lock()
        self._hint_job = None
        self._pulse = 0.0
        self._listening = False
        self._last_speech_error = ""
        self._said_muted = False

        self._build_widgets()

        # Route everything commands say() into the log panel instead of a
        # console (the built .exe does not have one).
        output.on_message(self.log_from_any_thread)

        # When `open` meets a program it has never seen, it needs a file path,
        # which cannot be dictated -- so the window provides a file picker.
        ask.on_request(self.ask_for_program)

        self.commands = registry.load()
        if self.commands:
            # Put something in the log immediately, so the panel does not look
            # broken before the first command is spoken.
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
        )

        # Mute the microphone while speaking, otherwise the app hears its own
        # replies (e.g. "Closing one window") and acts on the word "close".
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

        self.state = tk.StringVar(value="STARTING")
        tk.Label(
            self.root, textvariable=self.state, font=theme.STATE_FONT,
            bg=theme.BG, fg=theme.TEXT,
        ).pack(pady=(10, 0))

        self.hint = tk.StringVar(value=DEFAULT_HINT)
        tk.Label(
            self.root, textvariable=self.hint, font=theme.HINT_FONT,
            bg=theme.BG, fg=theme.DIM, wraplength=440,
        ).pack(pady=(4, 14))

        tk.Frame(self.root, bg=theme.LINE, height=1).pack(fill="x", padx=22)

        # A plain Text widget rather than ScrolledText: a native scrollbar
        # would be the only piece of grey Windows chrome in an otherwise dark
        # window, and the log auto-scrolls to the end anyway.
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
        explicitly as well. Inside the bundle the .ico lives in PyInstaller's
        unpacked folder (sys._MEIPASS).
        """
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, ICON)

        if not os.path.isfile(path):
            # Not worth failing over; the window just gets the default icon.
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
        """Redraw the dot and ring, then reschedule."""
        centre, base = 60, 13

        if self._listening:
            self._pulse += 0.09
            breathe = (math.sin(self._pulse) + 1) / 2  # oscillates 0..1

            radius = base + breathe * 3
            self.canvas.itemconfigure(
                self.dot, fill=theme.blend(theme.ACCENT_DIM, theme.ACCENT, breathe)
            )

            # The ring expands outward while fading into the background.
            ring_radius = base + 6 + breathe * 26
            self.canvas.itemconfigure(
                self.ring,
                outline=theme.blend(theme.ACCENT_DIM, theme.BG, breathe),
            )
        else:
            radius = base
            ring_radius = base + 6
            self.canvas.itemconfigure(self.dot, fill=theme.DIM)
            self.canvas.itemconfigure(self.ring, outline=theme.LINE)

        self.canvas.coords(
            self.dot,
            centre - radius, centre - radius, centre + radius, centre + radius,
        )
        self.canvas.coords(
            self.ring,
            centre - ring_radius, centre - ring_radius,
            centre + ring_radius, centre + ring_radius,
        )

        self.root.after(PULSE_MS, self._animate)

    # -- messages between threads ----------------------------------------------

    def log_from_any_thread(self, text):
        self.messages.put(("log", text))

    def status_from_any_thread(self, text, transient=False):
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
                                  "Not allowed", "Windows won't", "I won't",
                                  "Cannot reach", "Speech recognition needs")):
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
        self._hint_job = None
        self.hint.set(DEFAULT_HINT)

    def _watch_speech(self):
        """Report it in the log if the voice stops working.

        Failing silently would leave the user wondering whether the app heard
        them at all, so speech problems are surfaced as soon as they happen.
        """
        problem = speech.error()
        if problem and problem != self._last_speech_error:
            self._last_speech_error = problem
            self.log(f"I could not speak that: {problem}", tag="warn")

        if speech.available() and not speech.enabled():
            if not self._said_muted:
                self._said_muted = True
                self.log("Speaking is off. Say 'computer speak' to turn it "
                         "back on.", tag="dim")
        else:
            self._said_muted = False

        self.root.after(2000, self._watch_speech)

    # -- running commands ------------------------------------------------------

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

        Called from the microphone thread, but tkinter dialogs must run on
        the thread that owns the window -- so the dialog is scheduled with
        after() and this thread blocks on an event until it is answered.
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

        # Time out eventually so a dialog left open forever does not wedge
        # the command thread for the rest of the session.
        done.wait(timeout=180)
        return answer.get("path") or None

    def quit(self):
        self.listener.stop()
        speech.stop()
        # Discard anything logged from here on: the widgets are being torn
        # down, and the built .exe has no console to fall back to.
        output.on_message(lambda _text: None)
        self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
