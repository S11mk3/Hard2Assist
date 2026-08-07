"""The Hard2Assist window.

Two threads: this one runs tkinter, and a background one runs the microphone.
They only talk through a queue -- tkinter is not safe to touch from another
thread, and the microphone loop would otherwise be calling straight into it.
"""

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

import listener
import output
import registry

WINDOW_SIZE = "560x440"
STATUS_CLEAR_MS = 3000


class App:
    def __init__(self, root):
        self.root = root
        self.messages = queue.Queue()

        # One command at a time, whether it came from the microphone or the box.
        self.command_lock = threading.Lock()
        self._clear_status_job = None

        self._build_widgets()

        # Anything a command say()s now lands in our log instead of a console.
        output.on_message(self.log_from_any_thread)

        self.commands = registry.load()
        if not self.commands:
            self.log("No commands were found, so there is nothing to do.")
        else:
            self.log("Ready. Say 'computer help' or type 'help' below.")

        self.listener = listener.Listener(
            on_command=self.run_command,
            on_status=self.status_from_any_thread,
        )
        self.mic_thread = threading.Thread(target=self.listener.run, daemon=True)
        self.mic_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(100, self._drain)

    # -- layout ---------------------------------------------------------------

    def _build_widgets(self):
        self.root.title("Hard2Assist")
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(420, 320)

        self.status = tk.StringVar(value="Starting...")
        tk.Label(
            self.root, textvariable=self.status, anchor="w",
            font=("Segoe UI", 11, "bold"), padx=10, pady=8,
        ).pack(fill="x")

        self.log_box = scrolledtext.ScrolledText(
            self.root, wrap="word", state="disabled",
            font=("Consolas", 9), height=15,
        )
        self.log_box.pack(fill="both", expand=True, padx=10)

        entry_row = tk.Frame(self.root)
        entry_row.pack(fill="x", padx=10, pady=(8, 0))

        self.entry = tk.Entry(entry_row, font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.entry.bind("<Return>", lambda _event: self.run_typed())
        self.entry.focus()

        tk.Button(entry_row, text="Go", width=8, command=self.run_typed).pack(
            side="left", padx=(6, 0)
        )

        button_row = tk.Frame(self.root)
        button_row.pack(fill="x", padx=10, pady=8)

        self.listen_button = tk.Button(
            button_row, text="Stop listening", width=16,
            command=self.toggle_listening,
        )
        self.listen_button.pack(side="left")

        tk.Button(
            button_row, text="Help", width=10,
            command=lambda: self.run_command("help"),
        ).pack(side="left", padx=6)

        tk.Button(button_row, text="Quit", width=10, command=self.quit).pack(
            side="right"
        )

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

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_status(self, text, transient=False):
        self.status.set(text)

        if self._clear_status_job is not None:
            self.root.after_cancel(self._clear_status_job)
            self._clear_status_job = None

        if transient:
            self._clear_status_job = self.root.after(
                STATUS_CLEAR_MS, self._restore_status
            )

    def _restore_status(self):
        self._clear_status_job = None
        self.status.set("Paused" if self.listener.paused else "Listening")

    # -- actions --------------------------------------------------------------

    def run_command(self, command):
        """Run one command. Called from the microphone thread and from here."""
        with self.command_lock:
            self.log_from_any_thread(f"> {command}")
            try:
                result = registry.dispatch(self.commands, command)
            except Exception as e:
                self.log_from_any_thread(f"That command failed: {e}")
                return

        if result is registry.STOP:
            self.root.after(0, self.quit)

    def run_typed(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")

        # Typing "computer open notepad" and "open notepad" both work.
        command = listener.strip_prefix(text, required=False)
        if command:
            threading.Thread(
                target=self.run_command, args=(command,), daemon=True
            ).start()

    def toggle_listening(self):
        if self.listener.paused:
            self.listener.resume()
            self.listen_button.configure(text="Stop listening")
        else:
            self.listener.pause()
            self.listen_button.configure(text="Start listening")

    def quit(self):
        self.listener.stop()
        # Drop anything logged from here on. The widgets are going away, and in
        # the built .exe there is no console to fall back to.
        output.on_message(lambda _text: None)
        self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
