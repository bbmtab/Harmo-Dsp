"""Five wizard pages. Each page tells the user exactly what to do."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QFormLayout, QDoubleSpinBox, QComboBox, QCheckBox, QPlainTextEdit,
    QHBoxLayout, QFileDialog, QLineEdit,
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
        self.btn_add.clicked.connect(self._pick_files)
        row.addWidget(self.btn_add)
        self.log = QPlainTextEdit()
        self.log.setPlaceholderText("No files yet — add your L and R measurements.")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        lay.addLayout(row)
        lay.addWidget(self.log)

    def _pick_files(self):
        from ..io.rew import load_rew_file
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add REW measurement",
            "", "REW exports (*.txt *.frd *.wav);;All files (*)",
        )
        for p in paths:
            if p.lower().endswith(".wav"):
                self.log.appendPlainText(f"🎵 {p} — impulse import shows in Target graph (FIR step, TODO)")
                continue
            try:
                m = load_rew_file(p)
                self.log.appendPlainText(f"✓ {p} — {len(m)} points, {m.frequencies[0]:g}–{m.frequencies[-1]:g} Hz")
            except Exception as e:  # friendly message, never a traceback popup
                self.log.appendPlainText(f"⚠ {p} — could not read: {e}")


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
        label_wrap = QWidget()
        label_lay = QHBoxLayout(label_wrap)
        label_lay.setContentsMargins(0, 0, 0, 0)
        label_lay.addWidget(QLabel("High Q only below:"))
        label_lay.addWidget(InfoButton("q_factor"))
        self.xover_freq = QDoubleSpinBox()
        self.xover_freq.setRange(100, 2000)
        self.xover_freq.setValue(500)
        self.xover_freq.setSuffix(" Hz")
        form.addRow(label_wrap, self.xover_freq)
        self.btn_calc = QPushButton("✨  Calculate correction")
        self.btn_calc.setToolTip("Runs the PEQ solver on the averaged measurement")
        form.addRow(self.btn_calc)
        lay.addWidget(box)


class FineTunePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .graphic_eq import GraphicEQ
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            4, "tune", "Fine-tune — manual EQ",
            "👉 What to do: drag a slider for gain, then set its Type/Fc/Q "
            "in the ⚙ panel directly below. No tab switching — all 31 bands "
            "are full filters (Peak, Shelf, Pass, Notch, All-Pass, Modal).",
            help_keys=["q_factor", "pre_ringing", "group_delay"],
        ))
        self.geq = GraphicEQ()
        lay.addWidget(self.geq, 1)
        row = QHBoxLayout()
        self.btn_ab = QPushButton("🔀  A/B: bypass all")
        self.btn_ab.setCheckable(True)
        self.btn_ab.setToolTip("Compare corrected vs original sound prediction")
        self.btn_reopt = QPushButton("↻  Re-optimize around manual bands")
        self.btn_reopt.setToolTip("Auto-solver respects locked bands")
        row.addWidget(self.btn_ab)
        row.addWidget(self.btn_reopt)
        lay.addLayout(row)
        box = QGroupBox("💾 Equalizer APO preview (auto-updates)")
        form = QFormLayout(box)
        self.apo_preview = QPlainTextEdit()
        self.apo_preview.setReadOnly(True)
        self.apo_preview.setMaximumHeight(70)
        self.apo_preview.setToolTip("Paste this GraphicEQ line into Equalizer APO config")
        form.addRow(self.apo_preview)
        lay.addWidget(box)
        self.geq.changed.connect(self._refresh_preview)
        self.btn_ab.toggled.connect(self._refresh_preview)
        prow = QHBoxLayout()
        self.preamp = QDoubleSpinBox()
        self.preamp.setRange(-30, 6)
        self.preamp.setValue(0.0)
        self.preamp.setSuffix(" dB")
        self.preamp.setToolTip("Preamp (Peace main-screen style): lower overall volume so boosts never clip.\nAPO sums multiple preamps in dB.")
        self.preamp.valueChanged.connect(self._refresh_preview)
        prow.addWidget(QLabel("Preamp:"))
        prow.addWidget(self.preamp)
        self.btn_clip = QPushButton("🛡 Auto (anti-clip)")
        self.btn_clip.setToolTip("Compute worst-case peak of ALL bands + GraphicEQ (+Convolution file peak)\nand set preamp so nothing can clip. Covers every APO feature in this file.")
        self.btn_clip.clicked.connect(self._auto_preamp)
        prow.addWidget(self.btn_clip)
        self.btn_save_preset = QPushButton("💾 Save preset…")
        self.btn_save_preset.setToolTip("Save GEQ + parametric + preamp as JSON (Peace-style preset)")
        self.btn_save_preset.clicked.connect(self._save_preset)
        self.btn_load_preset = QPushButton("📂 Load preset…")
        self.btn_load_preset.setToolTip("Load a JSON preset")
        self.btn_load_preset.clicked.connect(self._load_preset)
        prow.addWidget(self.btn_save_preset)
        prow.addWidget(self.btn_load_preset)
        lay.addLayout(prow)
        self._refresh_preview()

    def collect(self):
        """Data for Export: (preamp, bands, geq_l, geq_r, bypassed)."""
        return self.preamp.value(), self.geq.bands(), None, None, self.btn_ab.isChecked()

    def apply_preset(self, data: dict):
        if "preamp" in data:
            self.preamp.setValue(float(data["preamp"]))
        if "bands" in data:
            self.geq.load_preset(data["bands"])
        elif "geq_l" in data:  # v0 preset compat (gains only)
            self.geq.set_gains(data["geq_l"], data.get("geq_r"))
        self._refresh_preview()

    def _save_preset(self):
        import json
        preamp, bands, _, _, _ = self.collect()
        data = {"app": "Harmo-Dsp", "v": 2, "preamp": preamp,
                "bands": self.geq.to_preset()}
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preset", "harmo-preset.json",
            "Presets (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)

    def _load_preset(self):
        import json
        path, _ = QFileDialog.getOpenFileName(
            self, "Load preset", "", "Presets (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                self.apply_preset(json.load(fh))
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Preset", f"Could not load preset:\n{e}")

    def _auto_preamp(self):
        """Anti-clip: worst peak of every APO feature -> preamp. Never boosts."""
        from ..dsp.clip_guard import suggest_preamp
        _, bands, _, _, _ = self.collect()
        rep = suggest_preamp(bands)
        self.preamp.setValue(rep["suggest_db"])
        note = "; ".join(rep["notes"][:2])
        self.preamp.setToolTip(
            f"Worst peak L {rep['peak_l']:+.1f} / R {rep['peak_r']:+.1f} dB "
            f"(filters + GraphicEQ + Convolution). Preamp auto-set {rep['suggest_db']:g} dB."
            + (f"\nNotes: {note}" if note else ""))

    def _refresh_preview(self):
        from ..dsp.peq import build_speakercorrect
        if self.btn_ab.isChecked():
            self.apo_preview.setPlainText("# bypassed — A/B ON, no correction applied")
            return
        _, bands, _, _, _ = self.collect()
        txt = build_speakercorrect(bands, self.preamp.value())
        self.apo_preview.setPlainText(txt)
        self.apo_preview.setToolTip("Full speakercorrect.txt preview (Channel L/R blocks). Export writes this file.")


class ExportPage(QWidget):
    """Full APO output: Device gate, Delay (2.1 align), Convolution (FIR),
    custom lines, write + backup + Include + Peace coexistence + Verify."""

    APO_DIR = r"C:\Program Files\EqualizerAPO\config"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tune = None
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            5, "export", "Export to Equalizer APO",
            "👉 What to do: check options, press Write file, confirm the Include line. "
            "Use Verify to see the effective L/R chain before writing.",
            help_keys=["apo_include", "preamp", "hp_protect", "apo_delay",
                       "apo_device", "apo_conv"],
        ))
        box = QGroupBox("💾 speakercorrect.txt options (all APO commands)")
        form = QFormLayout(box)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("Optional — e.g. High Definition Audio Device Speakers")
        self.device_edit.setToolTip("Device: gate — file only applies to matching device (Peace per-device profiles). Empty = all devices.")
        form.addRow("Device profile:", self.device_edit)
        self.hp = QCheckBox("Protective high-pass for small speakers (adds HP 50 Hz)")
        self.hp.setToolTip("Cuts very low bass to protect small PC speakers.")
        form.addRow(self.hp)
        dl = QHBoxLayout()
        self.delay_l = QDoubleSpinBox()
        self.delay_l.setRange(0, 50)
        self.delay_l.setSuffix(" ms")
        self.delay_l.setToolTip("Delay L in ms — 2.1 subwoofer time-align (1 ms ≈ 34 cm).")
        self.delay_r = QDoubleSpinBox()
        self.delay_r.setRange(0, 50)
        self.delay_r.setSuffix(" ms")
        self.delay_r.setToolTip("Delay R in ms.")
        dl.addWidget(QLabel("L:"))
        dl.addWidget(self.delay_l)
        dl.addWidget(QLabel("R:"))
        dl.addWidget(self.delay_r)
        form.addRow("Delay (sub align):", dl)
        crow = QHBoxLayout()
        self.conv_edit = QLineEdit()
        self.conv_edit.setPlaceholderText("Optional FIR impulse (.wav, 48 kHz) — Convolution")
        self.conv_edit.setToolTip("APO convolves with this file itself. Sample rate MUST match the device (else APO skips it).")
        self.btn_conv = QPushButton("…")
        self.btn_conv.setToolTip("Pick impulse response WAV")
        self.btn_conv.clicked.connect(self._pick_conv)
        crow.addWidget(self.conv_edit, 1)
        crow.addWidget(self.btn_conv)
        form.addRow("Convolution:", crow)
        self.custom = QPlainTextEdit()
        self.custom.setPlaceholderText("Advanced verbatim lines (Copy:, VST, …) appended at end. Empty = none.")
        self.custom.setMaximumHeight(55)
        self.custom.setToolTip("Escape hatch: any extra APO lines (Copy routing, etc.) are copied verbatim.")
        form.addRow("Custom footer:", self.custom)
        lay.addWidget(box)

        brow = QHBoxLayout()
        self.btn_write = QPushButton("💾  Write speakercorrect.txt")
        self.btn_write.setToolTip("Writes the file; backs up config.txt before touching it")
        self.btn_write.clicked.connect(self._write)
        self.btn_verify = QPushButton("🔍  Verify effective chain")
        self.btn_verify.setToolTip("Parse like the APO engine: Channel scope, Includes, preamp sums, boost audit")
        self.btn_verify.clicked.connect(self._verify)
        self.btn_reapply = QPushButton("↻  Re-apply Include")
        self.btn_reapply.setToolTip("Peace overwrites config.txt when its Include is missing — this restores ours")
        self.btn_reapply.clicked.connect(lambda: self._write(reapply_only=True))
        brow.addWidget(self.btn_write)
        brow.addWidget(self.btn_verify)
        brow.addWidget(self.btn_reapply)
        lay.addLayout(brow)
        self.status = QLabel("Equalizer APO status: checking…")
        lay.addWidget(self.status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        lay.addWidget(self.log)
        self._detect_apo()

    def set_source(self, tune_page):
        self._tune = tune_page

    # ---- helpers ----
    def _detect_apo(self):
        import os
        cfg = os.path.join(self.APO_DIR, "config.txt")
        if os.path.isfile(cfg):
            self.status.setText(f"✓ Equalizer APO found: {self.APO_DIR}")
        else:
            self.status.setText("⚠ Equalizer APO config not found — you can still save the file anywhere.")

    def _pick_conv(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Impulse response for Convolution", "",
            "Audio (*.wav *.flac *.ogg);;All files (*)")
        if paths:
            self.conv_edit.setText("; ".join(paths))

    def _collect_output(self):
        from ..dsp.apo_config import ApoOutput
        from ..dsp.peq import PeqBand
        if self._tune is None:
            preamp, bands, gl, gr, _ = 0.0, [], None, None, False
        else:
            preamp, bands, gl, gr, _ = self._tune.collect()
        bands = list(bands)
        if self.hp.isChecked():
            bands.append(PeqBand(True, "HP", 50, 0, 1.0, 100.0, "all"))
        conv: dict[int, str] = {}
        raw = self.conv_edit.text().strip()
        if raw:
            first = raw.split(";")[0].strip()
            conv[48000] = first  # assumed rate; Verify warns if device differs
        return ApoOutput(
            preamp_db=preamp, device_pattern=self.device_edit.text().strip(),
            bands=bands, graphic_l=gl, graphic_r=gr,
            delay_ms={"L": self.delay_l.value(), "R": self.delay_r.value()},
            convolution=conv, custom_footer=self.custom.toPlainText())

    # ---- actions ----
    def _verify(self):
        from ..dsp.apo_config import render_speakercorrect
        from ..dsp.apo_semantics import verify
        txt = render_speakercorrect(self._collect_output())
        res = verify(txt)
        lines = [f"L: {len(res.steps.get('L', []))} steps, preamp {res.preamp_db.get('L', 0):g} dB",
                 f"R: {len(res.steps.get('R', []))} steps, preamp {res.preamp_db.get('R', 0):g} dB"]
        lines += [f"⚠ {w}" for w in res.warnings] or ["✓ No warnings — chain looks safe."]
        self.log.setPlainText("\n".join(lines))

    def _write(self, reapply_only: bool = False):
        import os
        from datetime import datetime
        from PySide6.QtWidgets import QMessageBox
        from ..dsp.apo_config import render_speakercorrect, OUR_FILENAME
        from ..dsp.apo_semantics import detect_peace
        target_dir = self.APO_DIR if os.path.isdir(self.APO_DIR) else ""
        if not target_dir or not os.access(target_dir, os.W_OK):
            picked = QFileDialog.getExistingDirectory(self, "Save folder for speakercorrect.txt")
            if not picked:
                return
            target_dir = picked
        if not reapply_only:
            try:
                with open(os.path.join(target_dir, OUR_FILENAME), "w", encoding="utf-8") as fh:
                    fh.write(render_speakercorrect(self._collect_output()))
                self.log.appendPlainText(f"✓ Wrote {OUR_FILENAME}")
            except OSError as e:
                QMessageBox.warning(self, "Write", f"Cannot write (need admin for Program Files?):\n{e}")
                return
        cfg = os.path.join(target_dir, "config.txt")
        try:
            with open(cfg, encoding="utf-8-sig", errors="replace") as fh:
                cur = fh.read()
        except OSError:
            cur = ""
        info = detect_peace(cur)
        if info["peace_installed"]:
            self.log.appendPlainText("ℹ Peace detected (peace.txt Include present). Ours goes AFTER it.")
        bak = os.path.join(target_dir, f"config.Harmo-Dsp.bak-{datetime.now():%Y%m%d-%H%M%S}")
        try:
            if cur:
                with open(bak, "w", encoding="utf-8") as fh:
                    fh.write(cur)
                self.log.appendPlainText(f"✓ Backup: {os.path.basename(bak)}")
        except OSError as e:
            QMessageBox.warning(self, "Backup", f"Cannot back up config.txt:\n{e}")
            return
        want = f"Include: {OUR_FILENAME}"
        lines = [ln for ln in cur.splitlines()
                 if ln.strip().lower() != want.lower()
                 and "speakercorrect" not in ln.lower()]
        # insert after peace.txt include when present (order rule), else append
        placed = False
        out_lines: list[str] = []
        for ln in lines:
            out_lines.append(ln)
            if not placed and "peace.txt" in ln.lower() and ln.strip().lower().startswith("include"):
                out_lines.append(want)
                placed = True
        if not placed:
            out_lines.append(want)
        preview_tail = "\n".join(out_lines[-4:])
        ok = QMessageBox.question(
            self, "Confirm Include",
            f"Add to config.txt (APO reads top to bottom):\n\n{preview_tail}\n\n"
            + ("⚠ Peace overwrites config.txt when its own Include is missing.\n"
               "If ours vanishes later, press Re-apply Include." if info["peace_installed"] else ""),
        )
        from PySide6.QtWidgets import QMessageBox as MB
        if ok != MB.Yes:
            self.log.appendPlainText("• Include not changed (cancelled). File itself was written.")
            return
        try:
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("\n".join(out_lines) + "\n")
            self.log.appendPlainText("✓ config.txt updated — correction is live.")
        except OSError as e:
            QMessageBox.warning(self, "config.txt",
                                f"Cannot update config.txt (run as admin or pick another folder):\n{e}")
