"""Main window: left nav + stacked 5-step wizard + Advanced toggle."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QStackedWidget, QToolBar, QComboBox, QLabel,
    QPushButton, QMessageBox, QCheckBox, QSplitter,
)
from PySide6.QtCore import Qt
from . import icons
from .theme import ThemeManager
from .widgets import ChannelSelector
from .pages import (
    ImportPage, TargetPage, AutoCorrectPage, FineTunePage, ExportPage,
)

STEPS = [
    ("import", "1  📂  Import"),
    ("target", "2  🎯  Target"),
    ("auto", "3  ✨  Auto-correct"),
    ("tune", "4  🎚  Fine-tune"),
    ("export", "5  💾  Export"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Harmo-Dsp — PC speaker correction (Stereo 2.0 / 2.1)")
        self.resize(1080, 680)
        # Shared session: measurements/IRs/FIR paths (all local, in-memory).
        self.session: dict = {}

        self.theme = ThemeManager(self._app())
        self.theme.apply(ThemeManager.DARK)

        # ---- toolbar: channel + theme + advanced + help ----
        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)
        self.channels = ChannelSelector()
        self.channels.changed.connect(self._mode_note)
        bar.addWidget(self.channels)
        from .monitor import OutputMeter
        if OutputMeter is not None:
            self.out_meter = OutputMeter()
            bar.addWidget(self.out_meter)
        bar.addSeparator()
        self.btn_theme = QPushButton("🌗  Dark / Light")
        self.btn_theme.setToolTip("Switch between dark and light theme")
        self.btn_theme.clicked.connect(self._toggle_theme)
        bar.addWidget(self.btn_theme)
        self.adv = QCheckBox("Advanced mode")
        self.adv.setToolTip("Shows extra expert settings. Wizard is enough for most users.")
        bar.addWidget(self.adv)
        self.btn_help = QPushButton("❓  Guide")
        self.btn_help.setToolTip("Open the 5-step guide")
        self.btn_help.clicked.connect(self._guide)
        bar.addWidget(self.btn_help)

        # ---- body: draggable nav + pages (splitter: user can widen nav) ----
        body = QWidget()
        self.setCentralWidget(body)
        lay = QHBoxLayout(body)
        split = QSplitter(Qt.Horizontal)
        self.nav = QListWidget()
        self.nav.setMinimumWidth(150)
        self.nav.setMaximumWidth(320)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for key, label in STEPS:
            item = QListWidgetItem(label, self.nav)
            item.setToolTip(label)
        self.nav.setToolTip("Follow steps 1 → 5 in order. Drag the divider to widen this list.")

        self.stack = QStackedWidget()
        self.page_import = ImportPage()
        self.page_target = TargetPage()
        self.page_auto = AutoCorrectPage()
        self.page_tune = FineTunePage()
        self.page_export = ExportPage()
        for p in (self.page_import, self.page_target, self.page_auto,
                  self.page_tune, self.page_export):
            self.stack.addWidget(p)
        self.page_export.set_source(self.page_tune)
        self.page_import.set_target(self.page_tune)
        split.addWidget(self.nav)
        split.addWidget(self.stack)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([190, 890])
        lay.addWidget(split, 1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # ---- bottom: back / next ----
        bottom = QVBoxLayout()
        lay.addLayout(bottom)
        self.btn_back = QPushButton("◀  Back")
        self.btn_next = QPushButton("Next  ▶")
        self.btn_back.clicked.connect(self._back)
        self.btn_next.clicked.connect(self._next)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_back)
        bottom.addWidget(self.btn_next)
        self._refresh_nav_buttons()

        self.statusBar().showMessage(
            "v1: Stereo 2.0 / 2.1 only  •  5.1 / 7.1 / Headphone = Future (TODO)  •  All processing local, no upload"
        )
        # LAST: parent chain is complete now, so auto_enable_live's
        # self.window() resolves to MainWindow (regression hotfix).
        self.page_tune.auto_enable_live()

    def _app(self):
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()

    def _mode_note(self, key: str):
        """Honest per-mode facts in the status bar (no silent no-ops)."""
        notes = {
            "stereo20":
                "2.0: file = Channel L + R. Your optical setup: leave Delay 0/0.",
            "stereo21":
                "2.1: v1 writes the SAME L/R file. Sub tips: Delay aligns sub "
                "(1 ms ≈ 34 cm); keep bass filters on ALL channels (APO docs: "
                "bass redirect happens AFTER APO).",
        }
        msg = notes.get(key, "Mode: " + key)
        self.statusBar().showMessage(msg, 15000)

    def _toggle_theme(self):
        mode = self.theme.toggle()
        self.statusBar().showMessage(f"Theme: {mode}", 2000)

    def _guide(self):
        QMessageBox.information(
            self, "How to use Harmo-Dsp (2 minutes)",
            "1 📂 Import: add REW .txt/.frd or .wav for L and R\n"
            "2 🎯 Target: pick Flat or a slight tilt\n"
            "3 ✨ Auto-correct: press Calculate\n"
            "4 🎚 Fine-tune: drag bands, lock what you like\n"
            "5 💾 Export: write file for Equalizer APO\n\n"
            "Hover anything for a tooltip. Press ❓ for details.\n"
            "v1 = Stereo 2.0 / 2.1 only.",
        )

    def _back(self):
        self.nav.setCurrentRow(max(0, self.nav.currentRow() - 1))
        self._refresh_nav_buttons()

    def _next(self):
        self.nav.setCurrentRow(min(self.stack.count() - 1, self.nav.currentRow() + 1))
        self._refresh_nav_buttons()

    def _refresh_nav_buttons(self):
        r = self.nav.currentRow()
        self.btn_back.setEnabled(r > 0)
        self.btn_next.setEnabled(r < self.stack.count() - 1)
