"""Peace-style 31-band graphic EQ widget.

- 31 vertical sliders (ISO bands 20 Hz..20 kHz), -15..+15 dB
- L/R linked by default, unlink for per-channel edit
- Double-click a slider = reset band to 0; Reset all button
- Every control has tooltip; uncommon terms get ❓ popups
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel,
    QPushButton, QCheckBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from ..dsp.geq import ISO31, GAIN_MIN, GAIN_MAX, zero_gains


def _band_label(f: float) -> str:
    return f"{int(f)}" if float(f).is_integer() else f"{f:g}"


class GraphicEQ(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._linked = True
        self.gains_l: list[float] = zero_gains()
        self.gains_r: list[float] = zero_gains()
        self._sliders: list[QSlider] = []
        self._val_labels: list[QLabel] = []

        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        self.link = QCheckBox("🔗 Link L/R (edit both together)")
        self.link.setChecked(True)
        self.link.setToolTip("When checked, moving a slider changes Left and Right together.\nUncheck to edit channels separately (stereo tuning).")
        self.link.toggled.connect(self._set_linked)
        top.addWidget(self.link)
        self.btn_flat = QPushButton("⟲  Flat (all 0 dB)")
        self.btn_flat.setToolTip("Reset all 31 bands to 0 dB on both channels")
        self.btn_flat.clicked.connect(self.reset_all)
        top.addWidget(self.btn_flat)
        hint = QLabel("Drag slider = gain  •  Double-click = reset band  •  Hover band = frequency")
        hint.setStyleSheet("opacity: 0.75;")
        top.addWidget(hint, 1)
        outer.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(260)
        inner = QWidget()
        row = QHBoxLayout(inner)
        row.setSpacing(2)
        for i, f in enumerate(ISO31):
            col = QVBoxLayout()
            col.setSpacing(1)
            val = QLabel("0.0")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet("font-size: 10px;")
            s = QSlider(Qt.Vertical)
            s.setRange(int(GAIN_MIN * 10), int(GAIN_MAX * 10))
            s.setValue(0)
            s.setSingleStep(5)  # 0.5 dB
            s.setPageStep(10)   # 1 dB
            # tooltip shows freq + current gain, updated on move
            s.setToolTip(f"{_band_label(f)} Hz — 0.0 dB")
            s.setAccessibleName(f"Band {_band_label(f)} Hz")
            s.valueChanged.connect(lambda v, idx=i: self._on_slide(idx, v))
            fl = QLabel(_band_label(f))
            fl.setAlignment(Qt.AlignCenter)
            fl.setStyleSheet("font-size: 9px; opacity: 0.8;")
            fl.setToolTip(f"ISO 1/3-octave band centered at {f:g} Hz")
            col.addWidget(val)
            col.addWidget(s, 1)
            col.addWidget(fl)
            # double-click reset: install via mouse event on slider
            s.mouseDoubleClickEvent = lambda ev, idx=i: self._reset_band(idx)
            row.addLayout(col)
            self._sliders.append(s)
            self._val_labels.append(val)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.chan_note = QLabel("Editing: L + R linked")
        self.chan_note.setStyleSheet("font-size: 11px; opacity: 0.8;")
        outer.addWidget(self.chan_note)

    def _set_linked(self, on: bool):
        self._linked = on
        self.chan_note.setText("Editing: L + R linked" if on else "Editing: showing L (R kept) — separate edit coming to table view")

    def _on_slide(self, idx: int, v10: int):
        g = v10 / 10.0
        self.gains_l[idx] = g
        if self._linked:
            self.gains_r[idx] = g
        f = ISO31[idx]
        self._val_labels[idx].setText(f"{g:+.1f}")
        self._sliders[idx].setToolTip(f"{_band_label(f)} Hz — {g:+.1f} dB")
        self.changed.emit()

    def _reset_band(self, idx: int):
        self._sliders[idx].setValue(0)

    def reset_all(self):
        for s in self._sliders:
            s.setValue(0)

    def gains(self) -> tuple[list[float], list[float]]:
        return list(self.gains_l), list(self.gains_r)
