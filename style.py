"""Colours and fonts for the dock, in one place."""

from PySide6.QtGui import QColor, QFont

INK = QColor(9, 10, 14)            # the pill and panel: nearly black, solid, like a phone's island
EDGE = QColor(255, 255, 255, 24)   # its hairline rim
RAISED = QColor(255, 255, 255, 14) # bubbles and fields on it
TEXT = QColor(244, 246, 250)
DIM = QColor(138, 148, 165)
ACCENT = QColor(34, 211, 238)      # cyan: listening and hearing
VOICE = QColor(167, 139, 250)      # violet: talking
WARN = QColor(251, 176, 59)        # amber: something is wrong

TEXT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas"]


def font(points, weight=QFont.Weight.Normal, families=None):
    f = QFont()
    f.setFamilies(families or TEXT_FAMILIES)
    f.setPointSizeF(points)
    f.setWeight(weight)
    return f


def rgba(colour, alpha=None):
    """A colour as CSS for Qt style sheets."""
    return f"rgba({colour.red()}, {colour.green()}, {colour.blue()}, {colour.alpha() if alpha is None else alpha})"


# Qt style sheet for everything inside the open panel.
PANEL_CSS = f"""
QWidget {{ color: {rgba(TEXT)}; font-family: "Segoe UI Variable Text", "Segoe UI"; font-size: 10pt; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {rgba(TEXT, 40)}; border-radius: 3px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
QLineEdit, QComboBox {{
    background: {rgba(RAISED)}; border: 1px solid {rgba(EDGE)}; border-radius: 12px;
    padding: 7px 12px; selection-background-color: {rgba(ACCENT, 120)};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {rgba(ACCENT, 150)}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: rgb(22, 24, 30); border: 1px solid {rgba(EDGE)}; selection-background-color: {rgba(ACCENT, 90)};
    outline: none; padding: 4px;
}}
QPushButton {{
    background: {rgba(RAISED)}; border: 1px solid {rgba(EDGE)}; border-radius: 12px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {rgba(TEXT, 28)}; }}
QPushButton#icon {{ background: transparent; border: none; padding: 4px; border-radius: 10px;
    font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 11pt; color: {rgba(DIM)}; }}
QPushButton#icon:hover {{ background: {rgba(TEXT, 22)}; color: {rgba(TEXT)}; }}
QSlider::groove:horizontal {{ height: 4px; background: {rgba(TEXT, 30)}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {rgba(ACCENT)}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {rgba(TEXT)}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QLabel#dim {{ color: {rgba(DIM)}; font-size: 9pt; }}
QLabel#heading {{ font-size: 12.5pt; font-weight: 600; }}
"""
