"""What opens when the dock is clicked: the conversation, a box to type a command into, and the
settings."""

import os

from PySide6.QtCore import QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

import models
import registry
import settings
import speech
import storage
import style
import win
from version import NAME, VERSION

MAX_BUBBLES = 300
BUBBLE_WIDTH = 330

# Glyphs in Segoe Fluent Icons / Segoe MDL2 Assets.
GEAR, CLOSE, BACK, SEND = "\ue713", "\ue711", "\ue72b", "\ue724"


def _icon_button(glyph, tip, on_click):
    button = QPushButton(glyph)
    button.setObjectName("icon")
    button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.clicked.connect(on_click)
    return button


def _label(text, name=None):
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(True)
    return label


class _Toggle(QCheckBox):
    """A switch: a checkbox drawn as a track with a knob that slides."""

    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 0.0
        self._slide = QVariantAnimation(self, duration=160)
        self._slide.valueChanged.connect(self._moved)
        self.toggled.connect(self._animate)

    def setChecked(self, on):
        super().setChecked(on)
        self._slide.stop()
        self._position = 1.0 if on else 0.0

    def _animate(self, on):
        self._slide.stop()
        self._slide.setStartValue(self._position)
        self._slide.setEndValue(1.0 if on else 0.0)
        self._slide.start()

    def _moved(self, value):
        self._position = value
        self.update()

    def sizeHint(self):
        return QSize(46 + self.fontMetrics().horizontalAdvance(self.text()), 26)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, (self.height() - 18) / 2, 34, 18)
        off, on = QColor(255, 255, 255, 46), QColor(style.ACCENT)
        mix = self._position
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*(round(a + (b - a) * mix) for a, b in zip(off.getRgb(), on.getRgb(), strict=True))))
        p.drawRoundedRect(track, 9, 9)
        p.setBrush(QColor(255, 255, 255) if self.isEnabled() else QColor(150, 150, 150))
        p.drawEllipse(QRectF(track.left() + 2 + mix * 16, track.top() + 2, 14, 14))
        p.setPen(style.TEXT if self.isEnabled() else style.DIM)
        p.drawText(QRectF(44, 0, self.width() - 44, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class Panel(QWidget):
    """The open dock's contents. Commands typed here go out through `submitted`."""

    submitted = Signal(str)
    closed = Signal()
    microphone_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setStyleSheet(style.PANEL_CSS)
        self._pages = QStackedLayout(self)
        self._pages.addWidget(self._conversation_page())
        self._pages.addWidget(self._settings_page())
        self._last_detail = None

    # -- the conversation --

    def _conversation_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(_label(NAME, "heading"))
        header.addStretch()
        header.addWidget(_icon_button(GEAR, "Settings", self.show_settings))
        header.addWidget(_icon_button(CLOSE, "Close", self.closed.emit))
        layout.addLayout(header)

        self._list = QVBoxLayout()
        self._list.setSpacing(6)
        self._list.addStretch()
        holder = QWidget()
        holder.setLayout(self._list)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(holder)
        self._scroll.verticalScrollBar().rangeChanged.connect(
            lambda _low, high: self._scroll.verticalScrollBar().setValue(high))
        layout.addWidget(self._scroll, 1)

        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText('Type a command, like "open notepad"')
        self._input.returnPressed.connect(self._submit)
        row.addWidget(self._input, 1)
        row.addWidget(_icon_button(SEND, "Run it", self._submit))
        layout.addLayout(row)
        return page

    def _submit(self):
        text = self._input.text().strip()
        self._input.clear()
        if text:
            self.submitted.emit(text)

    def focus_input(self):
        self._pages.setCurrentIndex(0)
        self._input.setFocus()

    def add(self, text, tag):
        """One line of the conversation. Lines typed or said by the user start with "> "; a run
        of detail lines -- a list, a table -- shares one block."""
        if not text.strip():
            if self._last_detail is not None:
                self._last_detail.setText(self._last_detail.text() + "\n")
            return

        if tag is None and not text.startswith(">"):
            if self._last_detail is not None:
                self._last_detail.setText(self._last_detail.text() + "\n" + text)
                return
            bubble = _label(text, "dim")
            bubble.setFont(style.font(9, families=style.MONO_FAMILIES))
            bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._last_detail = bubble
            self._insert(bubble, mine=False, wide=True)
            return

        self._last_detail = None
        mine = text.startswith(">")
        words = text[1:].strip() if mine else text
        bubble = _label(words)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        colour = style.ACCENT if mine else style.WARN if tag == "warn" else style.TEXT
        bubble.setStyleSheet(
            f"background: {style.rgba(colour, 34 if mine else 20 if tag == 'warn' else 16)};"
            f"color: {style.rgba(style.TEXT if tag != 'warn' else style.WARN)};"
            "border-radius: 14px; padding: 8px 12px;")
        # A wrapping label asks for too little width on its own; give short replies their one line.
        # Measured in the style sheet's font, which the label only takes on once it is shown.
        bubble.setMinimumWidth(min(BUBBLE_WIDTH, QFontMetrics(style.font(10)).horizontalAdvance(words) + 30))
        self._insert(bubble, mine)

    def _insert(self, bubble, mine, wide=False):
        row = QHBoxLayout()
        if mine:
            row.addStretch()
        row.addWidget(bubble, 0 if not wide else 1)
        if not mine and not wide:
            row.addStretch()
        bubble.setMaximumWidth(10_000 if wide else BUBBLE_WIDTH)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        self._list.addWidget(holder)
        while self._list.count() > MAX_BUBBLES + 1:   # +1 for the stretch at the top
            old = self._list.takeAt(1).widget()
            if old is not None:
                old.deleteLater()

    # -- the settings --

    def _settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(_icon_button(BACK, "Back", lambda: self._pages.setCurrentIndex(0)))
        header.addWidget(_label("Settings", "heading"))
        header.addStretch()
        header.addWidget(_icon_button(CLOSE, "Close", self.closed.emit))
        layout.addLayout(header)

        # Wake word
        layout.addWidget(_label("Wake word", "dim"))
        row = QHBoxLayout()
        self._wake = QLineEdit(settings.get("prefix"))
        save = QPushButton("Save")
        save.clicked.connect(self._save_wake_word)
        self._wake.returnPressed.connect(self._save_wake_word)
        row.addWidget(self._wake, 1)
        row.addWidget(save)
        layout.addLayout(row)
        self._wake_note = _label("", "dim")
        self._wake_note.hide()
        layout.addWidget(self._wake_note)

        # Voice
        layout.addWidget(_label("Voice", "dim"))
        row = QHBoxLayout()
        self._voice = QComboBox()
        for voice, label in models.voices():
            self._voice.addItem(label, voice)
        self._voice.setCurrentIndex(max(0, self._voice.findData(settings.get("voice"))))
        self._voice.activated.connect(self._choose_voice)
        listen = QPushButton("Listen")
        listen.clicked.connect(self._preview_voice)
        row.addWidget(self._voice, 1)
        row.addWidget(listen)
        layout.addLayout(row)

        # Speed
        self._speed_label = _label("", "dim")
        layout.addWidget(self._speed_label)
        self._speed = QSlider(Qt.Orientation.Horizontal)
        self._speed.setRange(int(settings.SPEED[0] * 100), int(settings.SPEED[1] * 100))
        self._speed.setValue(int(settings.get("speed") * 100))
        self._speed.valueChanged.connect(self._show_speed)
        self._speed.sliderReleased.connect(lambda: settings.set("speed", self._speed.value() / 100))
        self._show_speed(self._speed.value())
        layout.addWidget(self._speed)

        # Microphone
        layout.addWidget(_label("Microphone", "dim"))
        self._mic = QComboBox()
        self._mic.addItem("Windows default", "")
        for name in _microphones():
            self._mic.addItem(name, name)
        self._mic.setCurrentIndex(max(0, self._mic.findData(settings.get("microphone"))))
        self._mic.activated.connect(self._choose_microphone)
        layout.addWidget(self._mic)

        layout.addSpacing(6)
        sounds = _Toggle("Chimes when I hear you, and when something fails")
        sounds.setChecked(settings.get("sounds"))
        sounds.toggled.connect(lambda on: settings.set("sounds", on))
        layout.addWidget(sounds)

        startup = _Toggle("Start when Windows starts")
        startup.setChecked(win.starts_with_windows())
        startup.setEnabled(storage.FROZEN)   # only the installed app can be started at sign-in
        startup.toggled.connect(win.set_starts_with_windows)
        layout.addWidget(startup)

        layout.addStretch()
        footer = QHBoxLayout()
        footer.addWidget(_label(f"{NAME} {VERSION}", "dim"))
        footer.addStretch()
        log_button = QPushButton("Open log")
        log_button.clicked.connect(lambda: os.startfile(os.path.join(storage.USER_DIR, "log.txt")))
        footer.addWidget(log_button)
        layout.addLayout(footer)
        return page

    def show_settings(self):
        self._wake.setText(settings.get("prefix"))
        self._note("")
        self._pages.setCurrentIndex(1)

    def _note(self, text):
        self._wake_note.setText(text)
        self._wake_note.setVisible(bool(text))

    def _save_wake_word(self):
        word = self._wake.text().strip().lower()
        if not settings.valid_prefix(word):
            self._note("One word, letters only, at least three of them.")
        elif word in registry.command_words():
            self._note(f'"{word}" is one of my commands, so it can\'t wake me too.')
        else:
            settings.set("prefix", word)
            self._note(f'Say "{word}" before every command from now on.')

    def _choose_voice(self):
        voice = self._voice.currentData()
        if voice != settings.get("voice"):
            settings.set("voice", voice)
            speech.change_voice(voice)
        self._preview_voice()

    def _preview_voice(self):
        name = self._voice.currentText().split(" (")[0]
        speech.speak(f"Hi, I'm {name}. This is how I'll sound.")

    def _show_speed(self, value):
        self._speed_label.setText(f"Speaking speed  {value / 100:.2f}x")

    def _choose_microphone(self):
        settings.set("microphone", self._mic.currentData())
        self.microphone_changed.emit()


def _microphones():
    """The names of the input devices, as Windows' default sound system lists them."""
    try:
        import sounddevice
        api = sounddevice.default.hostapi
        return sorted({device["name"] for device in sounddevice.query_devices()
                       if device["max_input_channels"] > 0 and device["hostapi"] == api})
    except Exception:
        return []
