"""Unified EQ view (Peace-style): 31 sliders on top, selected band's
settings directly below — no tab switching per frequency.

Each band = one full APO Filter (On/Type/Fc/Gain/Q/Ch/T60).
Click a slider (or ◀ ▶) to select a band; edit its settings below.
Gains still show on sliders; everything else lives in the detail panel.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel,
    QPushButton, QCheckBox, QScrollArea, QComboBox, QDoubleSpinBox,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from ..dsp.geq import ISO31, GAIN_MIN, GAIN_MAX
from ..dsp.peq import FILTER_TYPES, CHANNELS, PeqBand, _TYPE

FILTER_TIPS = {
    "PK": "Peak: cut/boost around Fc. Q = width (high Q = narrow).",
    "LP": "Low-Pass: remove everything above Fc.",
    "LPQ": "Low-Pass + Q: cutoff with resonance at Fc.",
    "HP": "High-Pass: remove everything below Fc (rumble/DC).",
    "HPQ": "High-Pass + Q: cutoff with resonance at Fc.",
    "BP": "Band-Pass murni: keep only around Fc. No gain (APO rule).",
    "LS": "Low Shelf: lift/cut everything below Fc (bass).",
    "LS 6dB": "Low Shelf corner 6dB/oct.",
    "LS 12dB": "Low Shelf corner 12dB/oct.",
    "HS": "High Shelf: lift/cut everything above Fc (treble).",
    "HS 6dB": "High Shelf corner 6dB/oct.",
    "HS 12dB": "High Shelf corner 12dB/oct.",
    "LSC": "Low Shelf center-frequency form + Q.",
    "HSC": "High Shelf center-frequency form + Q.",
    "NO": "Notch: remove narrow hum at Fc. No gain (APO rule).",
    "AP": "All-Pass: rotate phase only. No gain (APO rule).",
    "Modal": "Modal: room-mode correction with T60 target.",
}


def _band_label(f: float) -> str:
    return f"{int(f)}" if float(f).is_integer() else f"{f:g}"


class GraphicEQ(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sel = 12  # 1000 Hz selected by default
        self._on: list[bool] = [True] * 31
        self._type: list[str] = ["PK"] * 31
        self._fc: list[float] = list(ISO31)
        self._gain: list[float] = [0.0] * 31
        self._q: list[float] = [1.0] * 31
        self._t60: list[float] = [100.0] * 31
        self._ch: list[str] = ["all"] * 31
        self._sliders: list[QSlider] = []
        self._val_labels: list[QLabel] = []
        self._freq_labels: list[QLabel] = []
        self._updating = False

        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_flat = QPushButton("⟲  Flat (all 0 dB)")
        self.btn_flat.setToolTip("Reset all 31 bands to 0 dB (keeps types)")
        self.btn_flat.clicked.connect(self.reset_all)
        top.addWidget(self.btn_flat)
        hint = QLabel("Drag = gain  •  Click slider = select band (settings below)  •  Double-click = reset band")
        hint.setStyleSheet("opacity: 0.75;")
        top.addWidget(hint, 1)
        outer.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(230)
        inner = QWidget()
        row = QHBoxLayout(inner)
        row.setSpacing(2)
        for i, f in enumerate(ISO31):
            col = QVBoxLayout()
            col.setSpacing(1)
            val = QLabel("+0.0")
            val.setAlignment(Qt.AlignCenter)
            val.setStyleSheet("font-size: 10px;")
            s = QSlider(Qt.Vertical)
            s.setRange(int(GAIN_MIN * 10), int(GAIN_MAX * 10))
            s.setValue(0)
            s.setSingleStep(5)
            s.setPageStep(10)
            s.setToolTip(f"{_band_label(f)} Hz — +0.0 dB (click to select)")
            s.setAccessibleName(f"Band {_band_label(f)} Hz")
            s.valueChanged.connect(lambda v, idx=i: self._on_slide(idx, v))
            s.sliderPressed.connect(lambda idx=i: self.select(idx))
            fl = QLabel(_band_label(f))
            fl.setAlignment(Qt.AlignCenter)
            fl.setStyleSheet("font-size: 9px; opacity: 0.8;")
            col.addWidget(val)
            col.addWidget(s, 1)
            col.addWidget(fl)
            s.mouseDoubleClickEvent = lambda ev, idx=i: self._reset_band(idx)
            row.addLayout(col)
            self._sliders.append(s)
            self._val_labels.append(val)
            self._freq_labels.append(fl)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # ---- detail panel: settings of the SELECTED band, right below ----
        det = QGroupBox("⚙ Band settings (selected slider)")
        dlay = QHBoxLayout(det)
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setToolTip("Select previous band")
        self.btn_prev.clicked.connect(lambda: self.select((self._sel - 1) % 31))
        self.btn_next = QPushButton("▶")
        self.btn_next.setToolTip("Select next band")
        self.btn_next.clicked.connect(lambda: self.select((self._sel + 1) % 31))
        dlay.addWidget(self.btn_prev)
        self.sel_title = QLabel("")
        self.sel_title.setStyleSheet("font-weight: 700; font-size: 14px;")
        dlay.addWidget(self.sel_title)
        dlay.addWidget(self.btn_next)
        self.d_on = QCheckBox("On")
        self.d_on.setToolTip("Off = skip this band in export (keeps your values)")
        self.d_on.toggled.connect(self._detail_edited)
        dlay.addWidget(self.d_on)
        self.d_type = QComboBox()
        for code, label, _, _, _ in FILTER_TYPES:
            self.d_type.addItem(f"{code}", code)
        self.d_type.setToolTip(FILTER_TIPS["PK"])
        self.d_type.currentIndexChanged.connect(self._type_changed)
        dlay.addWidget(QLabel("Type:"))
        dlay.addWidget(self.d_type)
        self.d_fc = QDoubleSpinBox()
        self.d_fc.setRange(10, 24000)
        self.d_fc.setDecimals(1)
        self.d_fc.setSuffix(" Hz")
        self.d_fc.setToolTip("Center/cutoff — free value, not locked to slider position")
        self.d_fc.setMinimumWidth(110)
        self.d_fc.valueChanged.connect(self._detail_edited)
        dlay.addWidget(QLabel("Fc:"))
        dlay.addWidget(self.d_fc)
        self.d_gain = QDoubleSpinBox()
        self.d_gain.setRange(-15, 15)
        self.d_gain.setDecimals(1)
        self.d_gain.setSuffix(" dB")
        self.d_gain.setToolTip("Same as the slider — edit here or drag above")
        self.d_gain.valueChanged.connect(self._gain_edited)
        dlay.addWidget(QLabel("Gain:"))
        dlay.addWidget(self.d_gain)
        self.d_q = QDoubleSpinBox()
        self.d_q.setRange(0.1, 20)
        self.d_q.setDecimals(2)
        self.d_q.setToolTip("Q = width. High Q narrow (bass), low Q wide (>500 Hz).")
        self.d_q.valueChanged.connect(self._detail_edited)
        dlay.addWidget(QLabel("Q:"))
        dlay.addWidget(self.d_q)
        self.d_ch = QComboBox()
        self.d_ch.addItem("All", "all")
        self.d_ch.addItem("L", "L")
        self.d_ch.addItem("R", "R")
        self.d_ch.setToolTip("Which speaker: All = both L and R blocks.")
        self.d_ch.currentIndexChanged.connect(self._detail_edited)
        dlay.addWidget(QLabel("Ch:"))
        dlay.addWidget(self.d_ch)
        self.d_t60 = QDoubleSpinBox()
        self.d_t60.setRange(10, 2000)
        self.d_t60.setDecimals(0)
        self.d_t60.setSuffix(" ms")
        self.d_t60.setToolTip("Modal only: target decay time.")
        self.d_t60.valueChanged.connect(self._detail_edited)
        self.d_t60_lab = QLabel("T60:")
        dlay.addWidget(self.d_t60_lab)
        dlay.addWidget(self.d_t60)
        outer.addWidget(det)

        self.select(self._sel)

    # ---- selection ----
    def select(self, idx: int):
        self._sel = idx
        for i, fl in enumerate(self._freq_labels):
            fl.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: palette(highlight);"
                if i == idx else "font-size: 9px; opacity: 0.8;")
        self._updating = True
        try:
            self.sel_title.setText(f"{_band_label(self._fc[idx])} Hz")
            self.d_on.setChecked(self._on[idx])
            self.d_type.setCurrentIndex(max(0, self.d_type.findData(self._type[idx])))
            self.d_type.setToolTip(FILTER_TIPS.get(self._type[idx], ""))
            self.d_fc.setValue(self._fc[idx])
            self.d_gain.setValue(self._gain[idx])
            self.d_q.setValue(self._q[idx])
            self.d_ch.setCurrentIndex({"all": 0, "L": 1, "R": 2}.get(self._ch[idx], 0))
            self.d_t60.setValue(self._t60[idx])
            self._sync_enabled()
        finally:
            self._updating = False

    def _sync_enabled(self):
        has_gain, has_q = _TYPE.get(self._type[self._sel], (True, True))
        self.d_gain.setEnabled(has_gain)
        self.d_q.setEnabled(has_q)
        is_modal = self._type[self._sel] == "Modal"
        self.d_t60.setEnabled(is_modal)
        self.d_t60_lab.setEnabled(is_modal)

    # ---- edits ----
    def _on_slide(self, idx: int, v10: int):
        g = v10 / 10.0
        self._gain[idx] = g
        self._val_labels[idx].setText(f"{g:+.1f}")
        self._sliders[idx].setToolTip(f"{_band_label(self._fc[idx])} Hz — {g:+.1f} dB (click to select)")
        if idx == self._sel and not self._updating:
            self._updating = True
            try:
                self.d_gain.setValue(g)
            finally:
                self._updating = False
        self.changed.emit()

    def _type_changed(self):
        self.d_type.setToolTip(FILTER_TIPS.get(self.d_type.currentData(), ""))
        self._detail_edited()

    def _gain_edited(self):
        if self._updating:
            return
        g = self.d_gain.value()
        self._gain[self._sel] = g
        self._sliders[self._sel].setValue(int(round(g * 10)))
        self.changed.emit()

    def _detail_edited(self):
        if self._updating:
            return
        i = self._sel
        self._on[i] = self.d_on.isChecked()
        self._type[i] = self.d_type.currentData()
        self._fc[i] = self.d_fc.value()
        self._q[i] = self.d_q.value()
        self._ch[i] = self.d_ch.currentData()
        self._t60[i] = self.d_t60.value()
        self.sel_title.setText(f"{_band_label(self._fc[i])} Hz")
        self._freq_labels[i].setToolTip(f"Fc edited to {self._fc[i]:g} Hz")
        self._sync_enabled()
        self.changed.emit()

    def _reset_band(self, idx: int):
        self._sliders[idx].setValue(0)
        self.select(idx)

    def reset_all(self):
        for s in self._sliders:
            s.setValue(0)

    # ---- data I/O (export + presets) ----
    def bands(self) -> list[PeqBand]:
        return [PeqBand(self._on[i], self._type[i], self._fc[i],
                         self._gain[i], self._q[i], self._t60[i], self._ch[i])
                for i in range(31)]

    def gains(self) -> tuple[list[float], list[float]]:
        return list(self._gain), list(self._gain)

    def set_gains(self, gains_l: list[float], gains_r: list[float] | None = None):
        vals = list(gains_l)[:31] + [0.0] * 31
        for s in self._sliders:
            s.blockSignals(True)
        try:
            for i, s in enumerate(self._sliders):
                self._gain[i] = vals[i]
                s.setValue(int(round(vals[i] * 10)))
                self._val_labels[i].setText(f"{vals[i]:+.1f}")
        finally:
            for s in self._sliders:
                s.blockSignals(False)
        self.select(self._sel)
        self.changed.emit()

    def to_preset(self) -> list[dict]:
        return [{"on": self._on[i], "type": self._type[i], "fc": self._fc[i],
                 "gain": self._gain[i], "q": self._q[i],
                 "t60": self._t60[i], "ch": self._ch[i]} for i in range(31)]

    def load_preset(self, rows: list[dict]):
        for i, d in enumerate(rows[:31]):
            self._on[i] = bool(d.get("on", True))
            t = d.get("type", "PK")
            self._type[i] = t if t in _TYPE else "PK"
            self._fc[i] = float(d.get("fc", ISO31[i]))
            self._gain[i] = float(d.get("gain", 0.0))
            self._q[i] = float(d.get("q", 1.0))
            self._t60[i] = float(d.get("t60", 100.0))
            c = d.get("ch", "all")
            self._ch[i] = c if c in CHANNELS else "all"
        self.set_gains([self._gain[i] for i in range(31)])
