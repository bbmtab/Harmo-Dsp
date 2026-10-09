"""Parametric table: per-band On/Type/Fc/Gain/Q — the 'detail' Peace has.

Each row = one APO Filter line. Fc fully editable (10–24000 Hz),
not locked to ISO bands. Tooltips on every column header control.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QDoubleSpinBox, QCheckBox, QPushButton, QHeaderView,
    QLabel,
)
from PySide6.QtCore import Signal, Qt
from ..dsp.peq import FILTER_TYPES, PeqBand, default_bands

COLS = ("On", "Type (filter)", "Fc (Hz)", "Gain (dB)", "Q")

TYPE_TIPS = {
    "PK": "Peak: cut/boost around Fc. Q = width (high Q = narrow).",
    "LSC": "Low Shelf: lift/cut everything below Fc (bass).",
    "HSC": "High Shelf: lift/cut everything above Fc (treble).",
    "LP": "Low-Pass: remove everything above Fc.",
    "HP": "High-Pass: remove everything below Fc (rumble/DC).",
    "NO": "Notch: remove a narrow hum at Fc. Q = narrowness.",
    "BP": "Band-Pass: keep only the area around Fc.",
    "AP": "All-Pass: rotate phase only, no loudness change.",
}


class ParametricTable(QWidget):
    changed = Signal()

    def __init__(self, n_rows: int = 10, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        hint = QLabel("👉 Each row = one filter. Tick On, pick Type, set Fc freely (not locked to 31 bands).")
        hint.setWordWrap(True)
        hint.setStyleSheet("opacity: 0.85;")
        lay.addWidget(hint)

        self.table = QTableWidget(n_rows, len(COLS))
        self.table.setHorizontalHeaderLabels(list(COLS))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setToolTip(
            "On = filter active\nType = Peak/Shelf/Pass/Notch/All-Pass\n"
            "Fc = center/cutoff frequency (editable)\nGain = lift/cut in dB\nQ = width (high = narrow)"
        )
        lay.addWidget(self.table, 1)

        for r in range(n_rows):
            self._init_row(r, default_bands(n_rows)[r])

        bar = QHBoxLayout()
        self.btn_add = QPushButton("＋ Add band")
        self.btn_add.setToolTip("Append one more filter row (max 20)")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_del = QPushButton("－ Remove last")
        self.btn_del.setToolTip("Remove the last filter row")
        self.btn_del.clicked.connect(self._del_row)
        bar.addWidget(self.btn_add)
        bar.addWidget(self.btn_del)
        bar.addStretch(1)
        lay.addLayout(bar)

    # ---- row construction ----
    def _init_row(self, r: int, b: PeqBand):
        on = QCheckBox()
        on.setChecked(b.on)
        on.setToolTip("On = this filter is written to the APO file")
        on.toggled.connect(self.changed.emit)
        self.table.setCellWidget(r, 0, self._center(on))

        ty = QComboBox()
        for code, label, _, _ in FILTER_TYPES:
            ty.addItem(f"{code} — {label}", code)
        ty.setCurrentIndex(0)
        ty.setToolTip(TYPE_TIPS["PK"])
        ty.currentIndexChanged.connect(lambda i, c=ty: c.setToolTip(TYPE_TIPS.get(c.currentData(), "")))
        ty.currentIndexChanged.connect(self.changed.emit)
        self.table.setCellWidget(r, 1, ty)

        fc = QDoubleSpinBox()
        fc.setRange(10, 24000)
        fc.setDecimals(1)
        fc.setValue(b.fc)
        fc.setSuffix(" Hz")
        fc.setToolTip("Center/cutoff frequency — type any value 10–24000 Hz")
        fc.valueChanged.connect(self.changed.emit)
        self.table.setCellWidget(r, 2, fc)

        gn = QDoubleSpinBox()
        gn.setRange(-15, 15)
        gn.setDecimals(1)
        gn.setValue(b.gain)
        gn.setSuffix(" dB")
        gn.setToolTip("Lift (+) / cut (−). Cutting peaks is safer than boosting dips.")
        gn.valueChanged.connect(self.changed.emit)
        self.table.setCellWidget(r, 3, gn)

        q = QDoubleSpinBox()
        q.setRange(0.1, 20)
        q.setDecimals(2)
        q.setValue(b.q)
        q.setToolTip("Q = width. High Q narrow (bass peaks), low Q wide (above ~500 Hz).")
        q.valueChanged.connect(self.changed.emit)
        self.table.setCellWidget(r, 4, q)

    @staticmethod
    def _center(w: QWidget) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(w)
        return box

    def _add_row(self):
        if self.table.rowCount() >= 20:
            return
        r = self.table.rowCount()
        self.table.insertRow(r)
        self._init_row(r, PeqBand(True, "PK", 1000.0, 0.0, 1.0))
        self.changed.emit()

    def _del_row(self):
        if self.table.rowCount() <= 1:
            return
        self.table.removeRow(self.table.rowCount() - 1)
        self.changed.emit()

    # ---- read-out ----
    def bands(self) -> list[PeqBand]:
        out = []
        for r in range(self.table.rowCount()):
            on = self.table.cellWidget(r, 0).findChild(QCheckBox).isChecked()
            ty = self.table.cellWidget(r, 1).currentData()
            fc = self.table.cellWidget(r, 2).value()
            gn = self.table.cellWidget(r, 3).value()
            q = self.table.cellWidget(r, 4).value()
            out.append(PeqBand(on, ty, fc, gn, q))
        return out
