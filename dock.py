"""The dock: a pill at the top of the screen, like a phone's music island.

It breathes while it waits, shows a live waveform and the words while a command is being said,
shimmers while it works, and shows what it says while it talks. Click it to open the
conversation, a typing box and the settings; click while it talks to stop it; right-click for the
menu. It never takes the keyboard while closed, and gets out of the way of fullscreen apps.

The listener and the voice run on threads of their own; what they report reaches the Qt thread
through the signals of _Bridge.
"""

import math
import os
import sys
import threading
import time

from PySide6.QtCore import QEasingCurve, QObject, QPointF, QRectF, QSizeF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QWidget

import apps
import ask
import listener
import output
import registry
import settings
import speech
import storage
import style
import win
import wizard
from output import log
from panel import Panel

MARGIN = 22            # room around the pill for its glow
TOP = 8                # the pill's distance from the top of the screen
IDLE = QSizeF(64, 28)  # at rest: a small pill with a breathing dot in the middle
ACTIVE_HEIGHT = 42
MAX_WIDTH = 560
OPEN = QSizeF(440, 540)
LINGER_MS = 3500       # how long a reply stays up after the voice has finished


class _Bridge(QObject):
    status = Signal(str, bool)
    partial = Signal(str)
    level = Signal(float)
    message = Signal(str, object)
    download = Signal(float)
    done = Signal()
    ask = Signal(str, object)
    quit = Signal()
    show_panel = Signal()


class Dock(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Hard2Assist")
        self.setWindowIcon(QIcon(os.path.join(storage.BUNDLE_DIR, "H2A.ico")))

        self.mode = "starting"   # starting downloading setup idle hearing working speaking problem
        self.text = "Getting ready"
        self.progress = 0.0
        self.level = 0.0
        self.hover = False
        self.expanded = False
        self.reply_tag = None
        self.started = time.monotonic()
        self.hidden_for_fullscreen = False
        self.size_now = QSizeF(IDLE)

        self.panel = Panel()
        self.panel.setParent(self)
        self.panel.hide()
        self.panel.closed.connect(self.collapse)

        self.morph = QVariantAnimation(self)
        self.morph.setDuration(420)
        self.morph.setEasingCurve(QEasingCurve.Type.OutBack)
        self.morph.valueChanged.connect(self._resize)
        self.morph.finished.connect(self._morphed)

        self.linger = QTimer(self, singleShot=True, timeout=lambda: self._set("idle", ""))
        self.frames = QTimer(self, timeout=self._tick)
        self.frames.start(16)
        QTimer(self, timeout=self._watch_fullscreen).start(700)
        QTimer(self, timeout=self._watch_speech).start(2000)
        self._speech_error = ""

        self._resize(self.size_now)

    # -- placement and size --

    def _resize(self, size):
        self.size_now = QSizeF(size)
        screen = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        width, height = int(size.width()) + 2 * MARGIN, int(size.height()) + 2 * MARGIN
        self.setGeometry(screen.center().x() - width // 2, screen.top() + TOP - MARGIN, width, height)
        if self.expanded:
            self.panel.setGeometry(self._card().adjusted(18, 16, -18, -16).toRect())
        self.update()

    def _target(self):
        if self.expanded:
            return QSizeF(OPEN)
        text = self._shown_text()
        if not text:
            return QSizeF(IDLE)
        metrics = QFontMetrics(style.font(10.5, QFont.Weight.DemiBold))
        return QSizeF(min(MAX_WIDTH, 64 + metrics.horizontalAdvance(text)), ACTIVE_HEIGHT)

    def _shown_text(self):
        if self.mode == "idle":
            return f'Say "{_prefix()}" or click me' if self.hover else ""
        if self.mode == "downloading":
            return f"Getting my voice ready  {round(self.progress * 100)}%"
        return self.text

    def _refit(self):
        target = self._target()
        if target == self.morph.endValue() and self.morph.state() == QVariantAnimation.State.Running:
            return
        if abs(target.width() - self.size_now.width()) < 1 and abs(target.height() - self.size_now.height()) < 1:
            self.update()
            return
        self.morph.stop()
        self.morph.setStartValue(self.size_now)
        self.morph.setEndValue(target)
        self.morph.start()

    def _morphed(self):
        if self.expanded:
            self.panel.setGeometry(self._card().adjusted(18, 16, -18, -16).toRect())
            self.panel.show()
            self.panel.focus_input()

    def _card(self):
        width, height = self.size_now.width(), self.size_now.height()
        return QRectF((self.width() - width) / 2, MARGIN, width, height)

    # -- state --

    def _set(self, mode, text=None, linger=False):
        self.mode = mode
        if text is not None:
            self.text = text
        self.linger.stop()
        if linger:
            self.linger.start(LINGER_MS)
        self._refit()

    def on_status(self, text, transient):
        if transient:
            return
        if text == "Downloading":
            self._set("downloading")
        elif text == "Getting ready":
            self._set("starting", "Getting ready")
        elif text == "Can't download":
            self._set("problem", "No internet to download my voice. Retrying")
        elif text == "No microphone":
            self._set("problem", "No microphone")
        elif text == listener.SETUP:
            self._set("setup", "Setting up")
        elif text == "Speaking":
            self._set("speaking")
        elif text == "Listening" and self.mode in ("speaking", "working"):
            self._set(self.mode, linger=True)
        elif text == "Listening" and self.mode in ("starting", "downloading", "setup", "problem"):
            self._set("idle", "")

    def on_partial(self, text):
        self._set("hearing", text.strip())

    def on_message(self, text, tag):
        self.panel.add(text, tag)
        if text.startswith(">"):
            self._set("working", text[1:].strip())
        elif tag in ("say", "warn"):
            self.reply_tag = tag
            self._set("speaking" if speech.enabled() else self.mode, text)

    def on_done(self):
        """A command finished. Without a voice nothing else would bring the pill back to rest."""
        if not speech.talking():
            self._set(self.mode if self.mode in ("speaking", "working") else "idle", linger=True)

    def on_download(self, fraction):
        self.progress = fraction
        if self.mode == "downloading":
            self._refit()

    def on_level(self, level):
        self.level = max(self.level, min(1.0, math.sqrt(level) * 2.4))

    # -- input --

    def enterEvent(self, _event):
        self.hover = True
        if self.mode == "idle":
            self._refit()

    def leaveEvent(self, _event):
        self.hover = False
        if self.mode == "idle":
            self._refit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._menu(event.globalPosition().toPoint())
        elif not self.expanded:
            if speech.talking():
                speech.stop_talking()   # click to stop it talking
            else:
                self.expand()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.collapse()

    def changeEvent(self, event):
        # Clicking anywhere else closes the panel, unless one of our own dialogs is in front.
        if event.type() == event.Type.ActivationChange and self.expanded and not self.isActiveWindow() \
                and QApplication.activeModalWidget() is None:
            QTimer.singleShot(0, self.collapse)
        super().changeEvent(event)

    def _menu(self, where):
        menu = QMenu(self)
        menu.setStyleSheet(f"QMenu {{ background: rgb(22, 24, 30); color: white; border: 1px solid "
                           f"{style.rgba(style.EDGE)}; padding: 6px; border-radius: 10px; }}"
                           f"QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}"
                           f"QMenu::item:selected {{ background: {style.rgba(style.ACCENT, 80)}; }}")
        menu.addAction("Open", self.expand)
        menu.addAction("Settings", lambda: (self.expand(), self.panel.show_settings()))
        menu.addSeparator()
        menu.addAction("Quit Hard2Assist", QApplication.quit)
        menu.exec(where)

    def expand(self):
        if self.expanded:
            return
        self.expanded = True
        win.set_no_activate(int(self.winId()), False)
        self.raise_()
        self.activateWindow()
        self._refit()

    def collapse(self):
        if not self.expanded:
            return
        self.expanded = False
        self.panel.hide()
        win.set_no_activate(int(self.winId()), True)
        self._refit()

    # -- watching --

    def _watch_fullscreen(self):
        hide = win.fullscreen_in_front()
        if hide != self.hidden_for_fullscreen:
            self.hidden_for_fullscreen = hide
            self.setVisible(not hide)
            if not hide:
                win.set_no_activate(int(self.winId()), not self.expanded)

    def _watch_speech(self):
        problem = speech.error()
        if problem and problem != self._speech_error:
            self._speech_error = problem
            self.panel.add(f"My voice had a problem: {problem}", "warn")

    # -- painting --

    def _tick(self):
        self.level *= 0.86   # falls back between the microphone's reports
        if self.isVisible():
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = time.monotonic() - self.started
        card = self._card()
        radius = min(card.height() / 2, 26)
        path = QPainterPath()
        path.addRoundedRect(card, radius, radius)

        glow = {"hearing": style.ACCENT, "working": style.ACCENT, "speaking": style.VOICE,
                "problem": style.WARN}.get(self.mode)
        if glow is not None and not self.expanded:
            strength = 0.55 + 0.45 * (self.level if self.mode == "hearing" else 0.5 + 0.5 * math.sin(t * 3))
            for i in range(1, 9):
                colour = QColor(glow)
                colour.setAlpha(int(20 * strength * (1 - i / 9)))
                p.setPen(QPen(colour, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                grow = i * 1.6
                p.drawRoundedRect(card.adjusted(-grow, -grow, grow, grow), radius + grow, radius + grow)

        p.setPen(QPen(style.EDGE, 1))
        p.setBrush(style.INK)
        p.drawPath(path)

        if self.mode == "working" and not self.expanded:   # a sheen sweeping across
            x = card.left() + card.width() * ((t * 0.9) % 1.6 - 0.3)
            gradient = QLinearGradient(x - 60, 0, x + 60, 0)
            gradient.setColorAt(0, QColor(255, 255, 255, 0))
            gradient.setColorAt(0.5, QColor(255, 255, 255, 22))
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(path, gradient)

        if self.expanded or self.morph.state() == QVariantAnimation.State.Running and self.morph.endValue() == OPEN:
            return

        text = self._shown_text()
        self._paint_icon(p, QPointF(card.left() + 22, card.center().y()) if text else card.center(), t)
        if text:
            p.setFont(style.font(10.5, QFont.Weight.DemiBold))
            colour = style.WARN if self.mode == "problem" or (self.mode == "speaking" and self.reply_tag == "warn") \
                else style.DIM if self.mode == "idle" else style.TEXT
            p.setPen(colour)
            area = QRectF(card.left() + 42, card.top(), card.width() - 56, card.height())
            elided = QFontMetrics(p.font()).elidedText(text, Qt.TextElideMode.ElideLeft if self.mode == "hearing"
                                                       else Qt.TextElideMode.ElideRight, int(area.width()))
            p.drawText(area, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

    def _paint_icon(self, p, centre, t):
        mode = self.mode
        if mode in ("hearing", "speaking"):
            colour = style.ACCENT if mode == "hearing" else style.VOICE
            p.setPen(QPen(colour, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(5):
                if mode == "hearing":
                    amount = self.level * (0.55 + 0.45 * math.sin(t * 11 + i * 1.9)) * (1 - abs(i - 2) * 0.18)
                else:
                    amount = 0.35 + 0.3 * math.sin(t * 7 + i * 1.3) * math.sin(t * 2.7 + i)
                half = 2 + 9 * max(0.0, min(1.0, amount))
                x = centre.x() - 12 + i * 6
                p.drawLine(QPointF(x, centre.y() - half), QPointF(x, centre.y() + half))
        elif mode in ("working", "starting", "setup"):
            p.setPen(QPen(style.ACCENT if mode != "starting" else style.DIM, 2.4, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(centre.x() - 8, centre.y() - 8, 16, 16), int(-t * 360 * 16) % (360 * 16), 260 * 16)
        elif mode == "downloading":
            ring = QRectF(centre.x() - 8, centre.y() - 8, 16, 16)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 40), 2.4))
            p.drawEllipse(ring)
            p.setPen(QPen(style.ACCENT, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring, 90 * 16, -int(360 * 16 * self.progress))
        else:   # idle, problem: a breathing dot
            colour = QColor(style.WARN if mode == "problem" else style.ACCENT)
            breath = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 3.2)
            halo = QColor(colour)
            halo.setAlpha(int(70 * breath))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(halo)
            p.drawEllipse(centre, 6 + 4 * breath, 6 + 4 * breath)
            p.setBrush(colour)
            p.drawEllipse(centre, 4.2, 4.2)


def _prefix():
    return settings.get("prefix")


def run():
    """Open the dock and run until it is closed."""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bridge = _Bridge()
    dock = Dock()

    output.on_message(bridge.message.emit)
    bridge.message.connect(dock.on_message)
    bridge.status.connect(dock.on_status)
    bridge.partial.connect(dock.on_partial)
    bridge.level.connect(dock.on_level)
    bridge.download.connect(dock.on_download)
    bridge.done.connect(dock.on_done)
    bridge.quit.connect(QApplication.quit)
    bridge.show_panel.connect(dock.expand)
    win.on_shown_again(bridge.show_panel.emit)

    def ask_for_program(name):
        """The file picker, for the listener's thread: Qt dialogs must open on the Qt thread."""
        answer = {"done": threading.Event()}
        bridge.ask.emit(name, answer)
        answer["done"].wait(timeout=180)
        return answer.get("path") or None

    def show_picker(name, answer):
        try:
            answer["path"] = QFileDialog.getOpenFileName(dock, f"Where is {name}?", "",
                                                          "Programs (*.exe *.lnk);;All files (*.*)")[0]
        finally:
            answer["done"].set()

    bridge.ask.connect(show_picker)
    ask.on_request(ask_for_program)

    def on_command(text):
        try:
            if registry.run(text) is registry.STOP:
                bridge.quit.emit()
        finally:
            bridge.done.emit()

    ears = listener.Listener(on_command=on_command, on_status=bridge.status.emit, on_ready=wizard.on_ready,
                             opens_with_command=registry.opens_with_command, on_partial=bridge.partial.emit,
                             on_level=bridge.level.emit, on_download=bridge.download.emit)
    dock.panel.submitted.connect(ears.submit)
    dock.panel.microphone_changed.connect(ears.reopen)
    speech.on_speaking(ears.pause, ears.resume)
    speech.start()
    registry.load()

    def warm_up():
        tally = apps.counts()
        output.detail(f"Ready. {len(registry.load())} commands, {sum(tally.values())} apps "
                      f"({tally['installed']} found on this PC).")

    threading.Thread(target=warm_up, daemon=True, name="catalogue").start()
    threading.Thread(target=ears.run, daemon=True, name="microphone").start()

    dock.show()
    win.set_no_activate(int(dock.winId()), True)
    app.aboutToQuit.connect(lambda: (ears.stop(), speech.stop(), output.on_message(lambda _t, _g=None: None)))
    try:
        app.exec()
    except Exception:
        log.exception("The dock crashed")
        raise
