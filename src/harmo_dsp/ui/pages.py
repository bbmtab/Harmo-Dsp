"""Five wizard pages. Each page tells the user exactly what to do."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QFormLayout, QDoubleSpinBox, QComboBox, QCheckBox, QPlainTextEdit,
    QHBoxLayout,
)
from .widgets import StepHeader, InfoButton


def _placeholder(graph_text: str) -> QLabel:
    lab = QLabel(f"📈  {graph_text}\n(Graph view — connects to DSP core in next step)")
    lab.setMinimumHeight(140)
    lab.setStyleSheet(
        "border: 1px dashed palette(mid); border-radius: 8px; padding: 16px;"
    )
    return lab


class ImportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            1, "import", "Import measurement",
            "👉 What to do: measure with REW outside the app, export to .txt/.frd or .wav, "
            "then drop the files here. L = left speaker, R = right speaker.",
            help_keys=["multi_pos", "null"],
        ))
        lay.addWidget(_placeholder("Measured L / R response will appear here"))
        row = QHBoxLayout()
        self.btn_add = QPushButton("📂  Add .txt / .frd / .wav …")
        self.btn_add.setToolTip("Supports REW exports: frequency text (.txt/.frd) or impulse (.wav)")
        row.addWidget(self.btn_add)
        self.log = QPlainTextEdit()
        self.log.setPlaceholderText("No files yet — add your L and R measurements.")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        lay.addLayout(row)
        lay.addWidget(self.log)


class TargetPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            2, "target", "Target curve",
            "👉 What to do: pick the sound you want. Flat = neutral. Slight tilt = warmer. "
            "The app will correct toward this line.",
            help_keys=["tilt", "smoothing"],
        ))
        lay.addWidget(_placeholder("Target line (flat / tilt / custom) preview"))
        box = QGroupBox("🎯 Target settings")
        form = QFormLayout(box)
        self.preset = QComboBox()
        self.preset.addItems(["Flat", "Tilt -0.5 dB/oct", "Tilt -1.0 dB/oct", "Bass shelf +3 dB", "Import from file…"])
        form.addRow("Preset:", self.preset)
        self.smooth = QComboBox()
        self.smooth.addItems(["1/3 octave", "1/6 octave", "1/12 octave", "No smoothing"])
        self.smooth.setToolTip("Display smoothing only — does not change the filter.")
        form.addRow("Graph smoothing:", self.smooth)
        lay.addWidget(box)


class AutoCorrectPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            3, "auto", "Auto-correct",
            "👉 What to do: press Calculate, then look at Predicted vs Target. "
            "Green = good. The app cuts peaks and never boosts room nulls.",
            help_keys=["boost_limit", "q_factor", "preamp"],
        ))
        lay.addWidget(_placeholder("Measured vs Predicted vs Target overlay"))
        box = QGroupBox("✨ Auto-correct settings (safe defaults)")
        form = QFormLayout(box)
        self.max_boost = QDoubleSpinBox()
        self.max_boost.setRange(0, 12)
        self.max_boost.setValue(6.0)
        self.max_boost.setSuffix(" dB")
        self.max_boost.setToolTip("Max allowed lift. Deep dips (nulls) are never boosted.")
        form.addRow("Max boost:", self.max_boost)
        hl = QHBoxLayout()
        hb = QLabel("High Q only below:")
        hl.addWidget(hb)
        hl.addWidget(InfoButton("q_factor"))
        self.xover_freq = QDoubleSpinBox()
        self.xover_freq.setRange(100, 2000)
        self.xover_freq.setValue(500)
        self.xover_freq.setSuffix(" Hz")
        form.addRow(hl, self.xover_freq)
        self.btn_calc = QPushButton("✨  Calculate correction")
        self.btn_calc.setToolTip("Runs the PEQ solver on the averaged measurement")
        form.addRow(self.btn_calc)
        lay.addWidget(box)


class FineTunePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            4, "tune", "Fine-tune (manual)",
            "👉 What to do: drag points on the graph, or edit the table below. "
            "Lock a band to keep it. A/B button bypasses everything for comparison.",
            help_keys=["q_factor", "pre_ringing", "group_delay"],
        ))
        lay.addWidget(_placeholder("Draggable EQ bands: Fc / Gain (drag), Q (wheel)"))
        row = QHBoxLayout()
        self.btn_ab = QPushButton("🔀  A/B: bypass all")
        self.btn_ab.setCheckable(True)
        self.btn_ab.setToolTip("Compare corrected vs original sound prediction")
        self.btn_reopt = QPushButton("↻  Re-optimize around manual bands")
        self.btn_reopt.setToolTip("Auto-solver respects locked bands")
        row.addWidget(self.btn_ab)
        row.addWidget(self.btn_reopt)
        lay.addLayout(row)
        box = QGroupBox("🎚 Bands  (PK = peak, LS/HS = shelf, LP/HP = filter)")
        form = QFormLayout(box)
        self.lock_note = QLabel("Table editor connects to DSP core next. Locked bands are never auto-changed.")
        self.lock_note.setWordWrap(True)
        form.addRow(self.lock_note)
        lay.addWidget(box)


class ExportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            5, "export", "Export to Equalizer APO",
            "👉 What to do: press Write file, then confirm adding the Include line. "
            "After that all Windows sound passes through your correction.",
            help_keys=["apo_include", "preamp", "hp_protect"],
        ))
        lay.addWidget(_placeholder("Export preview: Preamp + Filters + Convolution"))
        box = QGroupBox("💾 Export settings")
        form = QFormLayout(box)
        self.hp = QCheckBox("Protective high-pass for small speakers (default OFF)")
        self.hp.setToolTip("Cuts very low bass to protect small PC speakers.")
        form.addRow(self.hp)
        self.btn_write = QPushButton("💾  Write speakercorrect.txt")
        self.btn_write.setToolTip("Writes a separate file; backs up config.txt before touching it")
        form.addRow(self.btn_write)
        self.status = QLabel("Equalizer APO status: unknown (detection runs on Windows).")
        form.addRow(self.status)
        lay.addWidget(box)
