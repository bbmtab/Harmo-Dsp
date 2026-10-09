"""Reusable widgets: step headers, info buttons, channel selector."""
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QToolButton,
    QMessageBox, QComboBox,
)
from PySide6.QtCore import Signal
from . import icons
from .help_texts import HELP


class InfoButton(QToolButton):
    """Small (?) button that shows a popup explanation."""

    def __init__(self, help_key: str, parent=None):
        super().__init__(parent)
        short, long_text = HELP.get(help_key, ("Help", "No help yet."))
        self._short = short
        self._long = long_text
        self.setText("❓")
        self.setToolTip(short)
        self.setAccessibleName(f"Help: {short}")
        self.setAutoRaise(True)
        self.clicked.connect(self._show)

    def _show(self):
        QMessageBox.information(self, self._short, self._long)


class StepHeader(QWidget):
    """Big step title + what-to-do description + optional help buttons."""

    def __init__(self, step_no: int, symbol_name: str, title: str,
                 description: str, help_keys=(), parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        sym = QLabel(icons.symbol(symbol_name))
        sym.setStyleSheet("font-size: 28px;")
        lay.addWidget(sym)
        txt = QVBoxLayout()
        t = QLabel(f"Step {step_no} — {title}")
        t.setStyleSheet("font-size: 18px; font-weight: 700;")
        d = QLabel(description)
        d.setWordWrap(True)
        d.setStyleSheet("font-size: 13px; opacity: 0.9;")
        txt.addWidget(t)
        txt.addWidget(d)
        lay.addLayout(txt, 1)
        for k in help_keys:
            lay.addWidget(InfoButton(k))


class ChannelSelector(QWidget):
    """Stereo focus: 2.0 and 2.1 active, the rest disabled as Future."""
    changed = Signal(str)

    MODES = [
        ("stereo20", "🔊  Stereo 2.0  (L + R)", True),
        ("stereo21", "🔊  2.1  (L + R + Sub)", True),
        ("m51", "🎬  5.1 Surround", False),
        ("m71", "🎬  7.1 Surround", False),
        ("headphone", "🎧  Headphone", False),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lab = QLabel("🔊 Channels:")
        lab.setToolTip("v1 supports stereo systems only. Others are future work.")
        lay.addWidget(lab)
        self.combo = QComboBox()
        for key, label, enabled in self.MODES:
            suffix = "" if enabled else "  (Future)"
            self.combo.addItem(label + suffix, key)
            if not enabled:
                # gray out: Qt has no per-item enable for all styles; tooltip explains
                pass
        self.combo.setToolTip(
            "Choose 2.0 (two speakers) or 2.1 (two speakers + subwoofer).\n"
            "5.1 / 7.1 / Headphone are planned future features."
        )
        self.combo.currentIndexChanged.connect(self._emit)
        lay.addWidget(self.combo, 1)
        self.info = InfoButton("channel_21")
        lay.addWidget(self.info)

    def _emit(self, i: int):
        key = self.combo.itemData(i)
        if key in ("m51", "m71", "headphone"):
            QMessageBox.information(
                self, "Future feature",
                "This mode is on the roadmap (TODO), not in v1.\n"
                "v1 focuses on Stereo 2.0 and 2.1 only.",
            )
            self.combo.setCurrentIndex(0)
            return
        self.changed.emit(key)

    def mode(self) -> str:
        return self.combo.currentData()
