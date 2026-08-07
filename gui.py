"""The Hard2Assist window.

Voice only -- there is nothing to click and nothing to type. The window shows
what it is doing and what it heard. Close it with the X, or say "computer stop".

Two threads: this one runs tkinter, and a background one runs the microphone.
They only talk through a queue -- tkinter is not safe to touch from another
thread, and the microphone loop would otherwise be calling straight into it.
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

WINDOW_SIZE = "520x460"
HINT_CLEAR_MS = 4000
PULSE_MS = 50
ICON = "H2A.ico"

DEFAULT_HINT = 'say "computer help" to hear what I can do'

# The listener describes itself in sentences, which suit the console. Up here we
# want one short word.
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

        # One command at a time, whichever thread asked for it.
        self.command_lock = threading.Lock()
        self._hint_job = None
        self._pulse = 0.0
        self._listening = False

        self._build_widgets()

        # Anything a command say()s now lands in our log instead of a console.
        output.on_message(self.log_from_any_thread)

        # When a command meets a program it has never heard of, it needs a path,
        # and you cannot say a path out loud. This is where the picker comes in.
        ask.on_request(self.ask_for_program)

        self.commands = registry.load()
        if self.commands:
            # Something in the log from the start, so the panel does not look
            # broken before you have said anything.
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

        # Talking into its own microphone would make it hear "Closing one
        # window" and act on the word "close", so it stops listening while it
        # speaks.
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

    # -- layout ---------------------------------------------------------------

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

        # The pulsing dot: alive and listening, or still and grey.
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

        # A plain Text rather than ScrolledText: a scrollbar would be the one
        # piece of grey Windows chrome in an otherwise dark window, and the log
        # follows itself anyway.
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
        """Title bar and taskbar icon.

        The .exe already carries the icon as a file, but a running window has
        its own, so it has to be set here too. Inside the bundle the file lives
        in PyInstaller's unpacked folder.
        """
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, ICON)

        if not os.path.isfile(path):
            return  # not worth failing over; you just get the default icon

        try:
            # default= sets it for the application rather than just this
            # window, which is what the taskbar reads.
            self.root.iconbitmap(default=path)
            self.root.iconbitmap(path)
        except tk.TclError:
            pass

    # -- the pulse ------------------------------------------------------------

    def _animate(self):
        centre, base = 60, 13

        if self._listening:
            self._pulse += 0.09
            breathe = (math.sin(self._pulse) + 1) / 2          # 0..1

            radius = base + breathe * 3
            self.canvas.itemconfigure(
                self.dot, fill=theme.blend(theme.ACCENT_DIM, theme.ACCENT, breathe)
            )

            # The ring expands outward and fades into the background.
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

    # -- messages between threads ---------------------------------------------

    def log_from_any_thread(self, text):
        self.messages.put(("log", text))

    def status_from_any_thread(self, text, transient=False):
        self.messages.put(("status", text, transient))

    def _drain(self):
        """Pull whatever the microphone thread has queued into the widgets."""
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

    # -- widgets --------------------------------------------------------------

    def log(self, text, tag=None):
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

    # -- running commands -----------------------------------------------------

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
        """Open the file picker and wait for an answer.

        Called from the microphone thread, but tkinter dialogs only work on the
        thread running the window, so the request is handed over with after()
        and this side waits for the result.
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

        # A timeout, so a dialog left open does not wedge the command thread
        # for the rest of the session.
        done.wait(timeout=180)
        return answer.get("path") or None

    def quit(self):
        self.listener.stop()
        speech.stop()
        # Drop anything logged from here on. The widgets are going away, and in
        # the built .exe there is no console to fall back to.
        output.on_message(lambda _text: None)
        self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
