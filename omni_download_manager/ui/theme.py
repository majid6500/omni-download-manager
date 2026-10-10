"""Design tokens and the application stylesheet.

Every colour used anywhere in the UI comes from a :class:`Palette`. The stylesheet is
generated from the palette, and custom-painted widgets read the same palette, so adding
a theme means adding one more palette object.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    sidebar: str
    surface: str
    surface_hover: str
    surface_raised: str
    input: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    accent_soft: str      # translucent accent, QSS rgba() syntax
    success: str
    warning: str
    danger: str
    track: str            # progress bar background
    scroll: str
    scroll_hover: str


DARK = Palette(
    name="dark",
    bg="#0F1218", sidebar="#0B0E13", surface="#161A22", surface_hover="#1B202A",
    surface_raised="#1F2430", input="#10141B", border="#242A36", border_strong="#323A4A",
    text="#E8EBF2", text_muted="#9BA4B5", text_faint="#667085",
    accent="#fc037f", accent_hover="#ff3d9c", accent_pressed="#d90067", accent_text="#FFFFFF",
    accent_soft="rgba(252, 3, 127, 18%)",
    success="#3DD68C", warning="#F5B544", danger="#FF6B6B",
    track="#262C39", scroll="#2E3544", scroll_hover="#3D465A",
)

LIGHT = Palette(
    name="light",
    bg="#F3F5F9", sidebar="#FFFFFF", surface="#FFFFFF", surface_hover="#F7F9FC",
    surface_raised="#F1F4F9", input="#F7F9FC", border="#E3E7EF", border_strong="#CBD2DF",
    text="#151A23", text_muted="#5A6477", text_faint="#8B94A7",
    accent="#fc037f", accent_hover="#e60073", accent_pressed="#c90064", accent_text="#FFFFFF",
    accent_soft="rgba(252, 3, 127, 12%)",
    success="#12A66A", warning="#C47F00", danger="#D93F3F",
    track="#E6EAF2", scroll="#CBD2DF", scroll_hover="#AEB7C8",
)

PALETTES = {palette.name: palette for palette in (DARK, LIGHT)}

_STYLESHEET = Template(
    """
QWidget { color: $text; }
QMainWindow, QDialog, QWidget#Root { background: $bg; }
QWidget#SettingsPage, QWidget#SettingsContent, QScrollArea#SettingsScroll { background: $bg; }
QLabel { background: transparent; }
QLabel#PageTitle { font-size: 20pt; font-weight: 600; }
QLabel#SectionTitle { font-size: 11pt; font-weight: 600; }
QLabel[role="muted"] { color: $text_muted; }
QLabel[role="faint"] { color: $text_faint; }
QLabel[role="error"] { color: $danger; }

QWidget#BottomNavigation { background: $sidebar; border-top: 1px solid $border; }

QFrame#Toolbar { background: $bg; border-bottom: 1px solid $border; }
QFrame#ToolbarSeparator { background: $border; border: none; min-width: 1px; max-width: 1px; min-height: 24px; max-height: 24px; }
QLabel#SelectionCount { color: $text_muted; }

QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 12px; }
QFrame#Divider { background: $border; border: none; min-height: 1px; max-height: 1px; }

QPushButton {
    background: $surface_raised; border: 1px solid $border; border-radius: 8px;
    padding: 8px 16px; font-weight: 500; color: $text;
}
QPushButton:hover { background: $surface_hover; border-color: $border_strong; }
QPushButton:pressed { background: $surface; border-color: $border_strong; }
QPushButton:disabled { background: $surface; border-color: $border; color: $text_faint; }
QPushButton:focus { border-color: $accent; }
QPushButton[variant="primary"] { background: $accent; border: 1px solid $accent; color: $accent_text; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_pressed; border-color: $accent_pressed; }
QPushButton[variant="primary"]:disabled {
    background: $surface_raised; border-color: $border; color: $text_faint;
}
QPushButton[variant="danger"] { background: $danger; border-color: $danger; color: #FFFFFF; }
QPushButton[variant="danger"]:hover { background: $danger; border-color: $text_muted; }
QPushButton[variant="danger"]:disabled {
    background: $surface_raised; border-color: $border; color: $text_faint;
}
QPushButton[variant="ghost"] { background: transparent; border-color: transparent; }
QPushButton[variant="ghost"]:hover { background: $surface_hover; }
QPushButton[variant="ghost"]:disabled { background: transparent; color: $text_faint; }
QPushButton[variant="segment"] { background: transparent; border: 1px solid $border; padding: 7px 18px; }
QPushButton[variant="segment"]:hover { border-color: $border_strong; }
QPushButton[variant="segment"]:checked {
    background: $accent_soft; border-color: $accent; color: $accent;
}
QPushButton[variant="segment"]:disabled { background: transparent; border-color: $border; color: $text_faint; }

/* Icon-only buttons of the fixed toolbar. */
QPushButton[variant="tool"], QPushButton[variant="tool-primary"], QPushButton[variant="tool-plain"] {
    background: transparent; border: 1px solid transparent; border-radius: 8px;
    padding: 0; min-width: 46px; min-height: 46px;
}
QPushButton[variant="tool"]:hover { background: $surface_hover; border-color: $border; }
QPushButton[variant="tool"]:pressed { background: $surface_raised; border-color: $border_strong; }
QPushButton[variant="tool"]:focus { border-color: $accent; }
QPushButton[variant="tool"]:disabled { background: transparent; border-color: transparent; }
QPushButton[variant="tool-primary"] { background: $accent; border-color: $accent; }
QPushButton[variant="tool-primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="tool-primary"]:pressed { background: $accent_pressed; border-color: $accent_pressed; }
QPushButton[variant="tool-primary"]:disabled {
    background: $surface_raised; border-color: $border;
}
QPushButton[variant="tool-plain"]:hover,
QPushButton[variant="tool-plain"]:pressed,
QPushButton[variant="tool-plain"]:focus,
QPushButton[variant="tool-plain"]:disabled {
    background: transparent; border-color: transparent;
}
QPushButton[variant="back"] {
    background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 0;
}
QPushButton[variant="back"]:hover { background: $surface_hover; border-color: transparent; }
QPushButton[variant="back"]:pressed { background: $surface_raised; border-color: transparent; }
QPushButton[variant="back"]:focus { border-color: transparent; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $input; border: 1px solid $border; border-radius: 8px; padding: 8px 12px;
    color: $text;
    selection-background-color: $accent; selection-color: $accent_text;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: $border_strong; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: $accent; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    border-color: $border; color: $text_faint;
}
QLineEdit:read-only { color: $text_muted; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: $surface_raised; border: 1px solid $accent; selection-background-color: $surface_hover;
}

QListView#DownloadList { background: transparent; border: none; }
QAbstractScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px 2px 2px 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 4px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QToolTip {
    background: $surface_raised; color: $text; border: 1px solid $border_strong;
    border-radius: 6px; padding: 5px 8px;
}
QMenu {
    background: $surface_raised; border: 1px solid $border_strong; border-radius: 10px; padding: 6px;
}
QMenu::item { padding: 8px 18px 8px 10px; border-radius: 6px; margin: 1px 0; }
QMenu::item:selected { background: $surface_hover; }
QMenu::item:disabled { color: $text_faint; }
QMenu::icon { padding-left: 6px; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }
"""
)


def build_stylesheet(palette: Palette) -> str:
    return _STYLESHEET.substitute(asdict(palette))


class ThemeManager(QObject):
    """Holds the active palette and applies it to the application."""

    changed = Signal()

    def __init__(self, name: str = "dark") -> None:
        super().__init__()
        self._palette = PALETTES.get(name, DARK)

    @property
    def palette(self) -> Palette:
        return self._palette

    def apply(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(self._palette))

    def set_theme(self, name: str) -> None:
        palette = PALETTES.get(name)
        if palette is None or palette is self._palette:
            return
        self._palette = palette
        self.apply()
        self.changed.emit()
