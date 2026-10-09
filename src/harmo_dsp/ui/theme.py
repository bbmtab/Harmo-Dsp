"""Light / dark theme manager (Fusion + palette, no external files)."""
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#1e1e1e"))
    p.setColor(QPalette.WindowText, QColor("#f0f0f0"))
    p.setColor(QPalette.Base, QColor("#252526"))
    p.setColor(QPalette.AlternateBase, QColor("#2d2d30"))
    p.setColor(QPalette.ToolTipBase, QColor("#2d2d30"))
    p.setColor(QPalette.ToolTipText, QColor("#f0f0f0"))
    p.setColor(QPalette.Text, QColor("#f0f0f0"))
    p.setColor(QPalette.Button, QColor("#2d2d30"))
    p.setColor(QPalette.ButtonText, QColor("#f0f0f0"))
    p.setColor(QPalette.Highlight, QColor("#007acc"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#4da6ff"))
    return p


def _light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#f5f5f5"))
    p.setColor(QPalette.WindowText, QColor("#1a1a1a"))
    p.setColor(QPalette.Base, QColor("#ffffff"))
    p.setColor(QPalette.AlternateBase, QColor("#ececec"))
    p.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipText, QColor("#1a1a1a"))
    p.setColor(QPalette.Text, QColor("#1a1a1a"))
    p.setColor(QPalette.Button, QColor("#e8e8e8"))
    p.setColor(QPalette.ButtonText, QColor("#1a1a1a"))
    p.setColor(QPalette.Highlight, QColor("#007acc"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#0066cc"))
    return p


class ThemeManager:
    LIGHT = "light"
    DARK = "dark"

    def __init__(self, app: QApplication):
        self.app = app
        self.current = self.DARK

    def apply(self, name: str) -> None:
        self.app.setStyle(QStyleFactory.create("Fusion"))
        if name == self.LIGHT:
            self.app.setPalette(_light_palette())
        else:
            self.app.setPalette(_dark_palette())
            name = self.DARK
        self.current = name
        # Slight global rounding for modern look; palette carries the rest.
        self.app.setStyleSheet(
            "QToolTip { padding: 6px; border: 1px solid palette(mid); }"
            "QGroupBox { font-weight: 600; margin-top: 12px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )

    def toggle(self) -> str:
        nxt = self.LIGHT if self.current == self.DARK else self.DARK
        self.apply(nxt)
        return nxt
