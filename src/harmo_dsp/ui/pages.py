"""Five wizard pages. Each page tells the user exactly what to do."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox,
    QFormLayout, QDoubleSpinBox, QComboBox, QCheckBox, QPlainTextEdit,
    QHBoxLayout, QFileDialog, QLineEdit, QSlider,
)
from PySide6.QtCore import Qt
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
        self._tune = None
        lay = QVBoxLayout(self)
        lay.addWidget(StepHeader(
            1, "import", "Import measurement",
            "👉 What to do: measure with REW outside the app, export to .txt/.frd or .wav, "
            "then drop the files here. L = left speaker, R = right speaker.\n"
            "Shortcut: import REW filter-settings or a Peace preset straight into Step 4.",
            help_keys=["multi_pos", "null"],
        ))
        lay.addWidget(_placeholder("Measured L / R response will appear here"))
        row = QHBoxLayout()
        self.btn_add = QPushButton("📂  Add .txt / .frd / .wav …")
        self.btn_add.setToolTip("Supports REW exports: frequency text (.txt/.frd) or impulse (.wav)")
        self.btn_add.clicked.connect(self._pick_files)
        row.addWidget(self.btn_add)
        self.btn_rew = QPushButton("📥  REW filters → Step 4")
        self.btn_rew.setToolTip("Import REW 'Filter Settings as text' (Generic/FBQ2496) directly as EQ bands")
        self.btn_rew.clicked.connect(self._import_rew_filters)
        row.addWidget(self.btn_rew)
        self.btn_peace = QPushButton("📥  Peace preset → Step 4")
        self.btn_peace.setToolTip("Import YOUR OWN Peace .peace preset (PreAmp + peak bands)")
        self.btn_peace.clicked.connect(self._import_peace)
        row.addWidget(self.btn_peace)
        self.log = QPlainTextEdit()
        self.log.setPlaceholderText("No files yet — add your L and R measurements.")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        lay.addLayout(row)
        lay.addWidget(self.log)

        meas = QGroupBox("🎙 Guided measurement (Dirac-style: sweep → record → IR)")
        mform = QFormLayout(meas)
        self.m_out = QComboBox()
        self.m_in = QComboBox()
        self.m_hint = QLabel("")
        self.m_hint.setWordWrap(True)
        mrow = QHBoxLayout()
        self.m_ch = QComboBox()
        self.m_ch.addItems(["L", "R", "Sub"])
        self.m_ch.setToolTip("Which speaker plays the sweep now")
        self.m_pos = QDoubleSpinBox()
        self.m_pos.setRange(1, 8)
        self.m_pos.setDecimals(0)
        self.m_pos.setToolTip("Mic position number (measure 1–3 per speaker)")
        self.m_dur = QComboBox()
        self.m_dur.addItems(["3 s", "5 s", "8 s"])
        self.m_dur.setCurrentText("5 s")
        mrow.addWidget(QLabel("Speaker:"))
        mrow.addWidget(self.m_ch)
        mrow.addWidget(QLabel("Pos:"))
        mrow.addWidget(self.m_pos)
        mrow.addWidget(QLabel("Sweep:"))
        mrow.addWidget(self.m_dur)
        mform.addRow(mrow)
        mform.addRow("Output:", self.m_out)
        mform.addRow("Input (mic):", self.m_in)
        brow = QHBoxLayout()
        self.btn_level = QPushButton("🔊 Check levels")
        self.btn_level.setToolTip("Record 1 s, report peak/RMS + OK/too loud/too quiet")
        self.btn_level.clicked.connect(self._check_levels)
        self.btn_measure = QPushButton("● Measure now")
        self.btn_measure.setToolTip("Play sweep on the chosen speaker, record mic, store IR")
        self.btn_measure.clicked.connect(self._measure_once)
        brow.addWidget(self.btn_level)
        brow.addWidget(self.btn_measure)
        mform.addRow(brow)
        mform.addRow(self.m_hint)
        lay.addWidget(meas)
        self._refresh_devices()
        from .monitor import LiveSpectrum
        if LiveSpectrum is not None:
            mon = QGroupBox("📊 Live sound monitor (soundcard → spectrum)")
            mlay = QVBoxLayout(mon)
            mlay.addWidget(LiveSpectrum())
            lay.addWidget(mon)

    def _refresh_devices(self):
        from ..io.audio import available, devices
        if not available():
            self.m_hint.setText("⚠ sounddevice not installed → measurement disabled. "
                                "Install: pip install sounddevice (everything else works).")
            self.btn_level.setEnabled(False)
            self.btn_measure.setEnabled(False)
            return
        outs, ins = devices()
        self.m_out.addItems(outs or ["(no output device)"])
        self.m_in.addItems(ins or ["(no input device)"])
        self.m_hint.setText("Quiet room, mic at ear position, one speaker at a time.")

    def _check_levels(self):
        from ..io.audio import record_only
        from ..dsp.measure import level_dbfs, level_verdict
        try:
            x = record_only(48000, self.m_in.currentText(), 1.0)
            pk, rms = level_dbfs(x)
            self.log.appendPlainText(f"Levels: peak {pk:.1f} dBFS, RMS {rms:.1f} — {level_verdict(pk, rms)}")
        except Exception as e:
            self.log.appendPlainText(f"⚠ Level check failed: {e}")

    def _measure_once(self):
        from ..io.audio import play_rec
        from ..dsp.measure import log_sweep, deconvolve, level_dbfs
        dur = int(self.m_dur.currentText().split()[0])
        fs = 48000
        try:
            sweep = log_sweep(fs, dur)
            self.log.appendPlainText(f"● Playing {dur}s sweep on {self.m_ch.currentText()}… stay quiet.")
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            rec = play_rec(sweep, fs, self.m_out.currentText(),
                           self.m_in.currentText(), dur + 2.0)
            ir = deconvolve(rec, sweep, fs, ir_len=fs * 2)
            pk, _ = level_dbfs(rec)
            key = (self.m_ch.currentText(), int(self.m_pos.value()) - 1)
            win = self.window()
            sess = getattr(win, "session", None)
            if sess is not None:
                sess.setdefault("ir", {})[key] = (fs, ir)
            self.log.appendPlainText(
                f"✓ IR {key[0]} pos {key[1] + 1}: {len(ir)} samples @ {fs} Hz "
                f"(rec peak {pk:.1f} dBFS). Step 3 FIR + time-align unlocked.")
        except Exception as e:
            self.log.appendPlainText(f"⚠ Measurement failed: {e}")

    def set_target(self, tune_page):
        self._tune = tune_page

    def _send_to_tune(self, bands, preamp: float | None, label: str):
        if self._tune is None:
            self.log.appendPlainText("⚠ Step 4 not linked yet.")
            return
        self._tune.geq.load_rew_bands(bands)
        if preamp is not None:
            self._tune.preamp.setValue(preamp)
        self.log.appendPlainText(f"✓ {label} → {len(bands)} bands loaded into Step 4.")

    def _import_rew_filters(self):
        from ..io.presets import parse_rew_filter_settings
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import REW filter settings", "",
            "REW filter settings (*.txt);;All files (*)")
        for p in paths:
            try:
                with open(p, encoding="utf-8-sig", errors="replace") as fh:
                    bands, notes = parse_rew_filter_settings(fh.read())
                self._send_to_tune(bands, None, p)
                for n in notes:
                    self.log.appendPlainText(f"ℹ {n}")
            except Exception as e:
                self.log.appendPlainText(f"⚠ {p} — {e}")

    def _import_peace(self):
        from ..dsp.peq import PeqBand
        from ..io.presets import parse_peace_preset
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Peace preset (your own file)", "",
            "Peace presets (*.peace *.txt);;All files (*)")
        for p in paths:
            try:
                with open(p, encoding="utf-8-sig", errors="replace") as fh:
                    data = parse_peace_preset(fh.read())
                bands = [PeqBand(True, "PK", fc, g, q)
                         for fc, g, q in data["bands"]]
                self._send_to_tune(bands, data["preamp"], p)
            except Exception as e:
                self.log.appendPlainText(f"⚠ {p} — {e}")

    def _pick_files(self):
        from ..io.rew import load_rew_file
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add REW measurement",
            "", "REW exports (*.txt *.frd *.wav);;All files (*)",
        )
        for p in paths:
            if p.lower().endswith(".wav"):
                try:
                    from ..io.irwav import load_ir_mono
                    fs, x = load_ir_mono(p)
                    win = self.window()
                    sess = getattr(win, "session", None)
                    if sess is not None:
                        store = sess.setdefault("ir", {})
                        have_l = any(k == "L" or (isinstance(k, tuple) and k[0] == "L")
                                     for k in store)
                        ch = "R" if have_l else "L"
                        n_same = sum(1 for k in store if k == ch or (
                            isinstance(k, tuple) and k[0] == ch))
                        store[(ch, n_same)] = (fs, x)
                        self.log.appendPlainText(
                            f"🎵 {p} → IR {ch} pos {n_same + 1} ({fs} Hz, {len(x)} samples). "
                            f"Phase correction (Step 3 FIR) unlocked.")
                    else:
                        self.log.appendPlainText(f"🎵 {p} — ({fs} Hz, session unavailable)")
                except Exception as e:
                    self.log.appendPlainText(f"⚠ {p} — {e}")
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

        fir = QGroupBox("🌀 Phase correction — FIR (Dirac/rePhase-chasing, experimental)")
        fform = QFormLayout(fir)
        fform.addRow(QLabel("Needs IR (.wav or guided measurement) from Step 1."))
        chrow = QHBoxLayout()
        self.fir_ch = QComboBox()
        self.fir_ch.addItems(["L", "R"])
        self.fir_ch.setToolTip("Design channel: per-speaker FIR (Dirac-style). Run once per channel.")
        self.btn_align = QPushButton("⏱ Auto time-align L/R/Sub")
        self.btn_align.setToolTip("Measure onsets from session IRs, delay early channels up to the latest (APO Delay). Fills Step 5 delays.")
        self.btn_align.clicked.connect(self._auto_align)
        chrow.addWidget(QLabel("Design for:"))
        chrow.addWidget(self.fir_ch)
        chrow.addWidget(self.btn_align)
        fform.addRow(chrow)
        self.fir_taps = QComboBox()
        self.fir_taps.addItems(["1024", "2048", "4096", "8192", "16384"])
        self.fir_taps.setCurrentText("4096")
        self.fir_taps.setToolTip("Filter length. Longer = finer bass + more latency/CPU.")
        fform.addRow("Taps:", self.fir_taps)
        srow = QHBoxLayout()
        self.fir_strength = QDoubleSpinBox()
        self.fir_strength.setRange(0, 100)
        self.fir_strength.setValue(30)
        self.fir_strength.setSuffix(" %")
        self.fir_strength.setToolTip("Phase strength: 0% = pure minimum-phase (safe). Higher = more excess-phase correction, more pre-ringing risk. Default conservative.")
        srow.addWidget(self.fir_strength)
        srow.addWidget(InfoButton("pre_ringing"))
        fform.addRow("Phase strength:", srow)
        self.fir_below = QDoubleSpinBox()
        self.fir_below.setRange(50, 5000)
        self.fir_below.setValue(300)
        self.fir_below.setSuffix(" Hz")
        self.fir_below.setToolTip("Excess-phase correction only below this frequency (single position: keep low).")
        fform.addRow("Correct phase below:", self.fir_below)
        self.btn_fir = QPushButton("🌀  Generate FIR + WAV")
        self.btn_fir.setToolTip("Design mixed-phase FIR, save Convolution WAV, auto-fill Step 5")
        self.btn_fir.clicked.connect(self._gen_fir)
        fform.addRow(self.btn_fir)
        self.fir_metrics = QLabel("No FIR yet — import .wav IR in Step 1 first.")
        self.fir_metrics.setWordWrap(True)
        fform.addRow(self.fir_metrics)
        lay.addWidget(fir)

    def _session_irs(self, ch: str | None = None):
        """Session IRs as {key: (fs, x)}, filtered by channel; legacy plain
        keys ('L') and tuple keys (('L', pos)) both accepted."""
        win = self.window()
        sess = getattr(win, "session", {}) or {}
        store = sess.get("ir", {})
        out = {}
        for k, v in store.items():
            kk = k[0] if isinstance(k, tuple) else k
            if ch is None or kk == ch:
                out[k] = v
        return out, sess

    def _auto_align(self):
        from ..dsp.align import estimate_delays, align_delays
        irs, _ = self._session_irs()
        # one IR per channel: prefer position 0
        per_ch: dict[str, tuple[int, object]] = {}
        for k, v in irs.items():
            ch = k[0] if isinstance(k, tuple) else k
            pos = k[1] if isinstance(k, tuple) else 0
            if ch not in per_ch or pos == 0:
                per_ch[ch] = v
        if len(per_ch) < 2:
            self.fir_metrics.setText("⏱ Need IRs for 2+ channels (measure L and R in Step 1).")
            return
        try:
            rel = estimate_delays(per_ch)
            apo = align_delays(per_ch)
        except ValueError as e:
            self.fir_metrics.setText(f"⏱ Align failed: {e}")
            return
        win = self.window()
        exp = getattr(win, "page_export", None)
        if exp is not None:
            if "L" in apo:
                exp.delay_l.setValue(round(apo["L"], 2))
            if "R" in apo:
                exp.delay_r.setValue(round(apo["R"], 2))
        order = ", ".join(f"{c}: onset {rel[c]:.2f}ms → delay {apo[c]:.2f}ms"
                          for c in sorted(rel))
        sub = f" (Sub offset {apo['Sub']:.2f}ms — verify by ear: bass may redirect after APO)" if "Sub" in apo else ""
        self.fir_metrics.setText(f"⏱ Time-aligned (ref = latest onset). {order}.{sub}")

    def _gen_fir(self):
        from PySide6.QtWidgets import QMessageBox
        from ..dsp.fir import design_speaker_fir, FirParams, save_fir_wav
        win = self.window()
        sess = getattr(win, "session", {}) or {}
        ch = self.fir_ch.currentText()
        irs, _ = self._session_irs(ch)
        if not irs:
            QMessageBox.information(self, "FIR", f"No IR for channel {ch} yet.\nMeasure it in Step 1 (guided or .wav import).")
            return
        fs_set = {fs for fs, _ in irs.values()}
        if len(fs_set) != 1:
            QMessageBox.warning(self, "FIR", f"Mixed sample rates {sorted(fs_set)} — resample outside first.")
            return
        fs = fs_set.pop()
        positions = [v[1] for v in irs.values()]
        p = FirParams(taps=int(self.fir_taps.currentText()),
                      strength=self.fir_strength.value() / 100.0,
                      phase_below_hz=self.fir_below.value(),
                      boost_max_db=self.max_boost.value())
        rep = design_speaker_fir(positions, fs, p)
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save FIR for {ch} Convolution", f"harmo-fir-{ch}-{fs}.wav",
            "WAV (*.wav)")
        if not path:
            return
        save_fir_wav(path, rep, normalize=True)
        sess.setdefault("fir", {})[ch] = path
        self.fir_metrics.setText(
            f"FIR {ch}: taps {rep.taps_n} • latency {rep.latency_ms:.2f} ms • "
            f"pre-ring {rep.pre_ring_db:.1f} dB • peak {rep.peak_db:.1f} dB\n"
            + "\n".join(rep.notes))


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
        from .monitor import PredictedCurve
        self.pred_curve = PredictedCurve() if PredictedCurve is not None else None
        if self.pred_curve is not None:
            self.pred_curve.setToolTip("Green = combined filter response of all 31 bands (real biquad math). Flat line = bypass.")
            form.addRow(self.pred_curve)
        lay.addWidget(box)
        self.geq.changed.connect(self._eq_changed)
        self.btn_ab.toggled.connect(self._refresh_preview)
        prow = QHBoxLayout()
        self.preamp = QDoubleSpinBox()
        self.preamp.setRange(-30, 30)
        self.preamp.setValue(0.0)
        self.preamp.setSuffix(" dB")
        self.preamp.setToolTip("Preamp: lower overall volume so boosts never clip.\nAPO sums multiple preamps in dB.")
        self.preamp.valueChanged.connect(self._preamp_spin_moved)
        prow.addWidget(QLabel("Preamp:"))
        prow.addWidget(self.preamp)
        self.preamp_slider = QSlider(Qt.Horizontal)
        self.preamp_slider.setRange(-300, 300)  # x10: -30.0..+30.0 dB
        self.preamp_slider.setValue(0)
        self.preamp_slider.setSingleStep(5)
        self.preamp_slider.setPageStep(20)
        self.preamp_slider.setMinimumWidth(160)
        self.preamp_slider.setToolTip("Preamp slider −30..+30 dB (Peace-style). Left = safer.")
        self.preamp_slider.valueChanged.connect(self._preamp_slide_moved)
        prow.addWidget(self.preamp_slider, 1)
        self.btn_clip = QPushButton("🛡 Anti-clip: ON")
        self.btn_clip.setCheckable(True)
        self.btn_clip.setToolTip("SWITCH, always guarding while ON: every EQ change recomputes the worst peak\n(filters + GraphicEQ + Convolution) and pins preamp there. Turn OFF for manual preamp.")
        self.btn_clip.toggled.connect(self._clip_toggled)
        self.btn_clip.setChecked(True)  # safe by default (brief: aman secara default)
        prow.addWidget(self.btn_clip)
        self.btn_save_preset = QPushButton("💾 Save preset…")
        self.btn_save_preset.setToolTip("Save full preset as JSON (all types, channels, T60)")
        self.btn_save_preset.clicked.connect(self._save_preset)
        self.btn_save_peace = QPushButton("💾 Save .peace…")
        self.btn_save_peace.setToolTip("Export Peak bands as Peace preset (interchange with Peace; types flatten to PK)")
        self.btn_save_peace.clicked.connect(self._save_peace)
        self.btn_load_preset = QPushButton("📂 Load preset…")
        self.btn_load_preset.setToolTip("Load a JSON preset")
        self.btn_load_preset.clicked.connect(self._load_preset)
        prow.addWidget(self.btn_save_preset)
        prow.addWidget(self.btn_save_peace)
        prow.addWidget(self.btn_load_preset)
        lay.addLayout(prow)
        lrow = QHBoxLayout()
        self.btn_live = QPushButton("⚪ Live to APO: OFF")
        self.btn_live.setCheckable(True)
        self.btn_live.setToolTip("Peace-style: every slider move auto-writes speakercorrect.txt (debounced) and APO reloads it live.\nNeeds the APO folder writable (admin) — otherwise use Write or Restart-as-admin.")
        self.btn_live.toggled.connect(self._live_toggled)
        self.btn_admin = QPushButton("🔑 Restart as admin")
        self.btn_admin.setToolTip("Relaunch this app elevated so Live mode can write into Program Files (like Peace, which requires admin).")
        self.btn_admin.clicked.connect(self._restart_as_admin)
        self.btn_admin.setVisible(False)
        lrow.addWidget(self.btn_live)
        lrow.addWidget(self.btn_admin)
        lrow.addStretch(1)
        lay.addLayout(lrow)
        self._live_timer = None
        self._refresh_preview()

    def _restart_as_admin(self):
        import sys
        from PySide6.QtWidgets import QMessageBox
        try:
            import ctypes
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, "-m harmo_dsp", None, 1)
            if rc <= 32:
                raise OSError(f"elevated relaunch failed (code {rc})")
            QMessageBox.information(self, "Admin",
                                    "Elevated copy is starting — close THIS window and use that one.")
        except Exception as e:
            QMessageBox.warning(self, "Admin", f"Cannot relaunch elevated:\n{e}")

    def _live_toggled(self, on: bool):
        from PySide6.QtWidgets import QMessageBox
        self.btn_live.setText(f"🔴 Live to APO: {'ON' if on else 'OFF'}")
        if not on:
            return
        win = self.window()
        exp = getattr(win, "page_export", None)
        if exp is None or not exp.live_capable()[0]:
            QMessageBox.information(
                self, "Live",
                "Live needs the APO folder WRITABLE.\n\n"
                "Press 🔑 Restart as admin, then enable Live again.\n"
                "(Same requirement as Peace, which must run as admin.)")
            self.btn_admin.setVisible(True)
            self.btn_live.setChecked(False)
            return
        # ensure Include once (with its own backup+confirm), then silent writes
        exp.ensure_included()
        self.schedule_live_write()

    def schedule_live_write(self):
        """Debounced auto-write (called on every EQ change while Live is ON)."""
        from PySide6.QtCore import QTimer
        if not getattr(self, "btn_live", None) or not self.btn_live.isChecked():
            return
        if self._live_timer is None:
            self._live_timer = QTimer(self)
            self._live_timer.setSingleShot(True)
            self._live_timer.setInterval(800)
            self._live_timer.timeout.connect(self._fire_live_write)
        self._live_timer.start()  # restart debounce

    def _fire_live_write(self):
        win = self.window()
        exp = getattr(win, "page_export", None)
        if exp is not None and self.btn_live.isChecked():
            exp.live_write()

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

    def _save_peace(self):
        from ..io.presets import write_peace_preset
        preamp, bands, _, _, _ = self.collect()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Peace preset", "harmo.peace",
            "Peace presets (*.peace)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(write_peace_preset(preamp, bands))

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
        """Anti-clip: worst peak of every APO feature -> preamp. Never boosts.

        Respects the user's hand: only pulls preamp DOWN to cover the peak,
        never pushes it up past a safer manual value.
        """
        from ..dsp.clip_guard import suggest_preamp
        _, bands, _, _, _ = self.collect()
        rep = suggest_preamp(bands)
        target = min(self.preamp.value(), rep["suggest_db"])
        self._syncing_preamp = True
        try:
            self.preamp.setValue(target)
            self.preamp_slider.setValue(int(round(target * 10)))
        finally:
            self._syncing_preamp = False
        note = "; ".join(rep["notes"][:2])
        tip = (f"Worst peak L {rep['peak_l']:+.1f} / R {rep['peak_r']:+.1f} dB "
               f"(filters + GraphicEQ + Convolution). Preamp auto-set {rep['suggest_db']:g} dB."
               + (f"\nNotes: {note}" if note else ""))
        self.preamp.setToolTip(tip)
        self.preamp_slider.setToolTip(tip)

    def _preamp_spin_moved(self):
        if getattr(self, "_syncing_preamp", False):
            return
        self._syncing_preamp = True
        try:
            self.preamp_slider.setValue(int(round(self.preamp.value() * 10)))
        finally:
            self._syncing_preamp = False
        self._refresh_preview()

    def _preamp_slide_moved(self):
        if getattr(self, "_syncing_preamp", False):
            return
        self._syncing_preamp = True
        try:
            self.preamp.setValue(self.preamp_slider.value() / 10.0)
        finally:
            self._syncing_preamp = False
        # spin's valueChanged -> _preamp_spin_moved -> preview (guarded, no loop)

    def _clip_toggled(self, on: bool):
        self.btn_clip.setText(f"🛡 Anti-clip: {'ON' if on else 'OFF'}")
        self.btn_clip.setToolTip(
            "ON: slider + angka SELALU bisa digeser. Anti-clip hanya menurunkan "
            "preamp bila hitungan puncak butuh lebih rendah (tak pernah menaikkan "
            "di atas pilihan manualmu). OFF: manual penuh, cek clipping di Verify.")
        if on:
            self._auto_preamp()  # pin down immediately if needed
        self._refresh_preview()

    def _eq_changed(self):
        """Any EQ edit: re-pin preamp while the switch is ON, then preview."""
        if getattr(self, "btn_clip", None) is not None and self.btn_clip.isChecked():
            self._auto_preamp()
        self._refresh_preview()
        self.schedule_live_write()

    def _refresh_preview(self):
        from ..dsp.peq import build_speakercorrect
        if self.btn_ab.isChecked():
            self.apo_preview.setPlainText("# bypassed — A/B ON, no correction applied")
            if self.pred_curve is not None:
                self.pred_curve.set_bands([])
            return
        _, bands, _, _, _ = self.collect()
        txt = build_speakercorrect(bands, self.preamp.value())
        self.apo_preview.setPlainText(txt)
        self.apo_preview.setToolTip("Full speakercorrect.txt preview (Channel L/R blocks). Export writes this file.")
        if self.pred_curve is not None:
            self.pred_curve.set_bands(bands)


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
        hook = QGroupBox("🔌 Windows sound hook (attach APO to your speaker)")
        hlay = QHBoxLayout(hook)
        self.dev_combo = QComboBox()
        self.dev_combo.setToolTip("Playback devices + APO attach state. Pick your speaker, press Attach.")
        self.dev_combo.setMinimumWidth(320)
        self.btn_dev_refresh = QPushButton("↻")
        self.btn_dev_refresh.setToolTip("Re-scan devices")
        self.btn_dev_refresh.clicked.connect(self._refresh_devices)
        self.btn_attach = QPushButton("🔧 Attach APO…")
        self.btn_attach.setToolTip("Install APO on this device (official SFX/EFX procedure, backup first).\nNeeds admin (UAC prompt) + reboot — like Configurator.")
        self.btn_attach.clicked.connect(self._attach_device)
        hlay.addWidget(self.dev_combo, 1)
        hlay.addWidget(self.btn_dev_refresh)
        hlay.addWidget(self.btn_attach)
        lay.addWidget(hook)
        self._refresh_devices()
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
        self.conv_edit.setPlaceholderText("Optional FIR impulse (.wav) — empty = NO convolution (filters only)")
        self.conv_edit.setToolTip("Active convolution file. APO convolves with this file itself.\nSample rate MUST match the device (else APO skips it).\nOld files (e.g. your Aug-31 wav) stay on disk — only referenced lines matter.\nVerify-live warns if 2+ convolutions would stack.")
        self.btn_conv = QPushButton("…")
        self.btn_conv.setToolTip("Pick impulse response WAV (replaces current)")
        self.btn_conv.clicked.connect(self._pick_conv)
        self.btn_conv_clear = QPushButton("✖ Off")
        self.btn_conv_clear.setToolTip("Turn convolution OFF: clears this field AND forgets generated FIR files (filters keep working)")
        self.btn_conv_clear.clicked.connect(self._clear_conv)
        crow.addWidget(self.conv_edit, 1)
        crow.addWidget(self.btn_conv)
        crow.addWidget(self.btn_conv_clear)
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
        self.btn_verify_live = QPushButton("🔍  Verify live config")
        self.btn_verify_live.setToolTip("Verify the REAL config.txt with includes resolved: stacking, order, Peace, dormant convolutions")
        self.btn_verify_live.clicked.connect(self._verify_live)
        self.btn_reapply = QPushButton("↻  Re-apply Include")
        self.btn_reapply.setToolTip("Peace overwrites config.txt when its Include is missing — this restores ours")
        self.btn_reapply.clicked.connect(lambda: self._write(reapply_only=True))
        self.btn_setup = QPushButton("📥  Install APO…")
        self.btn_setup.setToolTip("APO not found: guide + official download (never bundled: GPL driver)")
        self.btn_setup.clicked.connect(self._show_apo_guide)
        self.btn_configurator = QPushButton("🔧  Open Configurator…")
        self.btn_configurator.setToolTip("Tick your speaker device (admin), then reboot — this attaches APO to Windows sound")
        self.btn_configurator.clicked.connect(self._open_configurator)
        self.btn_repair = QPushButton("🩹  Repair registration…")
        self.btn_repair.setToolTip("Re-register the APO engine (official regsvr32 fix). Needs admin.")
        self.btn_repair.clicked.connect(self._repair_registration)
        self.btn_hooktest = QPushButton("🔊  Hook test (−20 dB)…")
        self.btn_hooktest.setToolTip("Audible end-to-end test: temporarily write Preamp -20 dB (backup first), you confirm it's quiet, one click restores. Proves APO really processes sound.")
        self.btn_hooktest.clicked.connect(self._hook_test)
        brow.addWidget(self.btn_write)
        brow.addWidget(self.btn_verify)
        brow.addWidget(self.btn_verify_live)
        brow.addWidget(self.btn_reapply)
        brow.addWidget(self.btn_setup)
        brow.addWidget(self.btn_configurator)
        brow.addWidget(self.btn_repair)
        brow.addWidget(self.btn_hooktest)
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

    # ---- Live mode (Peace-style auto-apply) ----
    def _apo_target_dir(self) -> str:
        import os
        apo_dir = getattr(self, "_apo_dir", None) or self.APO_DIR
        return apo_dir if os.path.isdir(apo_dir) else ""

    def live_capable(self) -> tuple[bool, str]:
        """(writable, reason). APO auto-reloads files in its config dir."""
        import os
        d = self._apo_target_dir()
        if not d:
            return False, "APO folder not found"
        if not os.access(d, os.W_OK):
            return False, "APO folder not writable (need admin)"
        return True, d

    def ensure_included(self) -> bool:
        """One-time Include setup for Live (backup + confirm inside _write)."""
        self._write(reapply_only=True)
        return True

    def live_write(self) -> bool:
        """Silent debounced write of current EQ (Live mode)."""
        import os
        from datetime import datetime
        from ..dsp.apo_config import render_speakercorrect, OUR_FILENAME
        ok, info = self.live_capable()
        if not ok:
            self.log.appendPlainText(f"• Live skipped: {info}.")
            return False
        target_dir = info
        if self._tune is None:
            return False
        try:
            with open(os.path.join(target_dir, OUR_FILENAME), "w", encoding="utf-8") as fh:
                fh.write(render_speakercorrect(self._collect_output()))
            self.log.appendPlainText(
                f"🔴 Live {datetime.now():%H:%M:%S} — APO reloads automatically.")
            return True
        except OSError as e:
            self.log.appendPlainText(f"⚠ Live write failed: {e}")
            return False

    # ---- Windows sound hook ----
    def _refresh_devices(self):
        from ..dsp import apo_attach as A
        self.dev_combo.clear()
        try:
            devs = A.enumerate_devices()
        except Exception as e:
            self.dev_combo.addItem(f"(scan failed: {e})", "")
            return
        if not devs:
            self.dev_combo.addItem("(no playback devices / non-Windows)", "")
            return
        for d in devs:
            mark = "✓" if d.attached else "✗"
            default = " [default]" if d.is_default else ""
            self.dev_combo.addItem(f"{mark} {d.name}{default}", d.guid)

    def _attach_device(self):
        import os
        import sys
        from PySide6.QtWidgets import QMessageBox
        guid = self.dev_combo.currentData()
        if not guid:
            return
        label = self.dev_combo.currentText()
        if label.startswith("✓"):
            QMessageBox.information(self, "Attach", "APO already attached to this device.")
            return
        ok = QMessageBox.question(
            self, "Attach APO",
            f"Install Equalizer APO on:\n\n{label}\n\n"
            "Official SFX/EFX procedure: original sound-card processing is "
            "backed up first (registry + .reg file) and kept working.\n"
            "Needs ADMIN (UAC prompt) and a REBOOT afterwards.\n\nProceed?",
        )
        from PySide6.QtWidgets import QMessageBox as MB
        if ok != MB.Yes:
            return
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "..", "tools", "attach_apo.py")
        helper = os.path.normpath(helper)
        try:
            import ctypes
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{helper}" --attach "{guid}"',
                None, 1)
            if rc <= 32:
                raise OSError(f"elevated launch failed (code {rc})")
        except Exception as e:
            QMessageBox.warning(self, "Attach",
                                f"Could not start elevated helper:\n{e}\n\n"
                                "Fallback: use 🔧 Open Configurator… instead.")
            return
        QMessageBox.information(
            self, "Attach",
            "If UAC asked and the helper finished: REBOOT now (like the "
            "official tool), then press ↻ to see ✓ attached.")

    # ---- helpers ----
    def _detect_apo(self):
        from ..dsp.apo_setup import find_config_dir, full_report
        found = find_config_dir([self.APO_DIR])
        if found and found != self.APO_DIR:
            self.APO_DIR = found
        self._apo_dir = find_config_dir([self.APO_DIR])
        rep = full_report(self._apo_dir)
        self._apo_state = rep["config_state"]
        self.status.setText("\n".join(rep["lines"]))
        self.status.setWordWrap(True)
        self.btn_setup.setVisible(rep["installed_version"] is None)
        reg_ok = rep["reg_pre"] and rep["reg_post"]
        self.btn_repair.setVisible(rep["installed_version"] is not None and not reg_ok)
        self.btn_configurator.setVisible(rep["config_state"] in ("idle", "peace-idle"))

    def _repair_registration(self):
        import os
        import sys
        from PySide6.QtWidgets import QMessageBox
        helper = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "tools", "attach_apo.py"))
        try:
            import ctypes
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{helper}" --repair',
                None, 1)
            if rc <= 32:
                raise OSError(f"elevated launch failed (code {rc})")
        except Exception as e:
            QMessageBox.warning(self, "Repair", f"Could not start elevated helper:\n{e}")
            return
        QMessageBox.information(self, "Repair",
                                "After the helper finishes, press ↻ — engine lines should turn ✓.")

    def _show_apo_guide(self):
        from PySide6.QtWidgets import QMessageBox
        from ..dsp.apo_setup import OFFICIAL_URL
        box = QMessageBox(self)
        box.setWindowTitle("Install Equalizer APO (once)")
        box.setTextFormat(2)  # rich text
        box.setText(
            "Harmo-Dsp only <b>writes text</b> — the sound engine is Equalizer APO "
            "(free, GPL by Jonas Thedering). It is a <b>driver</b>, so it cannot be "
            "bundled as a plugin: it needs its own installer + admin + reboot.<br><br>"
            "1. Download from the <b>official</b> site (check the license there).<br>"
            "2. Install, run <b>Configurator.exe as admin</b>, tick your speaker.<br>"
            "3. Reboot, come back here, press Write.<br><br>"
            f"Official download:<br>{OFFICIAL_URL}")
        box.addButton("Open official download…", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        if box.exec():
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(OFFICIAL_URL))

    def _open_configurator(self):
        from PySide6.QtWidgets import QMessageBox
        from ..dsp.apo_setup import open_configurator
        if not open_configurator(getattr(self, "_apo_dir", None)):
            QMessageBox.warning(self, "Configurator",
                                "Configurator.exe not found — reinstall Equalizer APO first.")

    def _pick_conv(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Impulse response for Convolution", "",
            "Audio (*.wav *.flac *.ogg);;All files (*)")
        if paths:
            self.conv_edit.setText("; ".join(paths))

    def _clear_conv(self):
        """Convolution OFF: field + session FIR map cleared (filters unaffected)."""
        self.conv_edit.clear()
        sess = getattr(self.window(), "session", {}) or {}
        if isinstance(sess.get("fir"), dict):
            sess["fir"].clear()
        self.log.appendPlainText("• Convolution OFF — next Write has no Convolution line.")

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
        if not raw:
            sess = getattr(self.window(), "session", {}) or {}
            if sess.get("fir_wav"):
                raw = sess["fir_wav"]
        if raw:
            first = raw.split(";")[0].strip()
            try:
                from scipy.io.wavfile import read as _wr
                _fs, _ = _wr(first)
                conv[int(_fs)] = first  # real rate, not assumed
            except Exception:
                conv[48000] = first  # assumed rate; Verify warns if device differs
        conv_per_ch: dict[str, dict[int, str]] = {}
        sess = getattr(self.window(), "session", {}) or {}
        for ch, path in (sess.get("fir", {}) or {}).items():
            if ch in ("L", "R"):
                try:
                    from scipy.io.wavfile import read as _wr2
                    _fs2, _ = _wr2(path)
                    conv_per_ch[ch] = {int(_fs2): path}
                except Exception:
                    conv_per_ch[ch] = {48000: path}
        return ApoOutput(
            preamp_db=preamp, device_pattern=self.device_edit.text().strip(),
            bands=bands, graphic_l=gl, graphic_r=gr,
            delay_ms={"L": self.delay_l.value(), "R": self.delay_r.value()},
            convolution=conv, conv_per_ch=conv_per_ch,
            custom_footer=self.custom.toPlainText())

    # ---- actions ----
    def _verify(self):
        from ..dsp.apo_config import render_speakercorrect
        from ..dsp.apo_semantics import verify
        txt = render_speakercorrect(self._collect_output())
        res = verify(txt)
        lines = [f"L: {len(res.steps.get('L', []))} steps, preamp {res.preamp_db.get('L', 0):g} dB",
                 f"R: {len(res.steps.get('R', []))} steps, preamp {res.preamp_db.get('R', 0):g} dB"]
        lines += [f"⚠ {w}" for w in res.warnings] or ["✓ No warnings — chain looks safe."]
        lines += [f"ℹ {i}" for i in res.infos]
        self.log.setPlainText("\n".join(lines))

    def _verify_live(self):
        """Verify the REAL config.txt (includes resolved): stacking/order/peace."""
        import os
        from ..dsp.apo_semantics import verify
        apo_dir = getattr(self, "_apo_dir", None) or self.APO_DIR
        cfg = os.path.join(apo_dir, "config.txt") if apo_dir else ""
        try:
            with open(cfg, encoding="utf-8-sig", errors="replace") as fh:
                txt = fh.read()
        except OSError:
            self.log.setPlainText("• No live config.txt to verify (APO folder missing?).")
            return
        res = verify(txt, base_dir=os.path.dirname(cfg))
        lines = ["Live config.txt (includes resolved):",
                 f"L: {len(res.steps.get('L', []))} steps, "
                 f"R: {len(res.steps.get('R', []))} steps"]
        lines += [f"⚠ {w}" for w in res.warnings] or ["✓ No warnings."]
        lines += [f"ℹ {i}" for i in res.infos]
        self.log.setPlainText("\n".join(lines))

    def _helper_path(self) -> str:
        import os
        return os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "tools", "write_apo.py"))

    def _run_elevated(self, args: list[str], payload: bytes | None) -> bool:
        """Run writer helper elevated (UAC), verify by re-reading. True = done."""
        import os
        import sys
        import tempfile
        from PySide6.QtWidgets import QMessageBox
        import ctypes
        cmd = [self._helper_path(), *args]
        if payload is not None:
            with tempfile.NamedTemporaryFile(prefix="harmo-apo-",
                                             suffix=".bin",
                                             delete=False) as fh:
                fh.write(payload)
                tmp = fh.name
            cmd += ["--payload-file", tmp]
        else:
            tmp = ""
        try:
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join(f'"{a}"' for a in cmd), None, 1)
            if rc <= 32:
                raise OSError(f"elevated launch failed (code {rc})")
        except Exception as e:
            QMessageBox.warning(self, "Admin needed", f"Could not elevate:\n{e}")
            return False
        finally:
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        QMessageBox.information(
            self, "Admin step",
            "Approve the UAC prompt, wait a moment, then press OK.\n"
            "The result is verified by re-reading the file.")
        return True

    def _hook_test(self):
        """Audible end-to-end proof: -20 dB now, one-click restore after."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtWidgets import QMessageBox as MB
        from ..dsp.apo_setup import find_config_dir
        apo_dir = getattr(self, "_apo_dir", None) or find_config_dir()
        if not apo_dir or not os.path.isdir(apo_dir):
            QMessageBox.information(self, "Hook test",
                                    "Install Equalizer APO first (📥 Install APO…).")
            return
        ok = QMessageBox.question(
            self, "Hook test",
            "Play some music (normal PCM — not DTS/Dolby bitstream), then:\n\n"
            "1. Backup config.txt (automatic)\n"
            "2. Write temporary test: Preamp: -20 dB\n"
            "3. Music should go almost SILENT = APO hook proven ✓\n"
            "4. Press restore = everything back\n\n"
            "⚠ Listen on an ATTACHED device (✓ in the list above).\n"
            "Headphones/Bluetooth without ✓ will NOT change — attach them first.\n\n"
            "Needs admin once (UAC). Proceed?",
        )
        if ok != MB.Yes:
            return
        test_text = ("# Harmo-Dsp hook test (temporary — will be restored)\n"
                     "Preamp: -20 dB\n").encode("utf-8")
        cfg = os.path.join(apo_dir, "config.txt")
        try:
            with open(cfg, encoding="utf-8-sig", errors="replace") as fh:
                original = fh.read()
        except OSError:
            original = ""
        if not self._write_bytes_elevated_ok(
                apo_dir, "config.txt", test_text,
                "Write test config (admin step)"):
            return
        self.log.appendPlainText("🔊 Test live: music should be almost SILENT now.")
        done = QMessageBox.question(
            self, "Hook test",
            "Is the music almost silent?\n\n"
            "YES = hook proven ✓ (then it restores)\n"
            "NO = APO not processing this device (then it still restores).",
            MB.Yes | MB.No)
        if not self._write_bytes_elevated_ok(
                apo_dir, "config.txt", original.encode("utf-8"),
                "Restore original config (admin step)"):
            self.log.appendPlainText("⚠ Restore needs admin — your backup is in the APO folder.")
            return
        self.log.appendPlainText(
            "✓ Restored. Verdict: %s." % (
                "HOOK PROVEN — APO processes this device"
                if done == MB.Yes else
                "NOT processing — check device attach (🔧) + reboot"))
        self._detect_apo()

    def _write_bytes_elevated_ok(self, target_dir: str, name: str,
                                 data: bytes, title: str) -> bool:
        """Direct write, else UAC-elevated helper, then verify bytes match."""
        import os
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtWidgets import QMessageBox as MB
        path = os.path.join(target_dir, name)
        try:
            with open(path, "wb") as fh:
                fh.write(data)
            self.log.appendPlainText(f"✓ Wrote {name} (direct).")
            return True
        except OSError:
            pass
        ok = QMessageBox.question(
            self, title,
            f"Program Files needs admin.\nRetry '{name}' elevated (UAC)?",
        )
        if ok != MB.Yes:
            return False
        if not self._run_elevated(["--write-file", target_dir, name], data):
            return False
        try:
            with open(path, "rb") as fh:
                if fh.read() == data:
                    self.log.appendPlainText(f"✓ Wrote {name} (elevated, verified).")
                    return True
        except OSError:
            pass
        QMessageBox.warning(self, title, "Verification failed — file differs. Nothing assumed.")
        return False

    def _write(self, reapply_only: bool = False):
        import os
        from datetime import datetime
        from PySide6.QtWidgets import QMessageBox
        from ..dsp.apo_config import render_speakercorrect, OUR_FILENAME
        from ..dsp.apo_semantics import detect_peace
        from ..dsp.apo_setup import build_patched_config
        apo_dir = getattr(self, "_apo_dir", None) or self.APO_DIR
        target_dir = apo_dir if os.path.isdir(apo_dir) else ""
        if not target_dir or not os.access(target_dir, os.W_OK):
            picked = QFileDialog.getExistingDirectory(self, "Save folder for speakercorrect.txt")
            if not picked:
                return
            target_dir = picked
        if not reapply_only:
            content = render_speakercorrect(self._collect_output()).encode("utf-8")
            if not self._write_bytes_elevated_ok(target_dir, OUR_FILENAME, content,
                                                 "Write speakercorrect.txt"):
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
        if cur and not self._backup_config(target_dir, cur):
            return
        new_text, _ = build_patched_config(cur, OUR_FILENAME)
        if new_text.strip() == cur.strip():
            self.log.appendPlainText("• Include already present — nothing to confirm.")
            return
        preview_tail = "\n".join(new_text.splitlines()[-4:])
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
        if self._write_bytes_elevated_ok(target_dir, "config.txt",
                                         new_text.encode("utf-8"), "Update config.txt"):
            self.log.appendPlainText("✓ config.txt updated — correction is live.")

    def _backup_config(self, target_dir: str, cur: str) -> bool:
        """Backup config.txt (direct, else elevated). False = abort."""
        import os
        from datetime import datetime
        from PySide6.QtWidgets import QMessageBox
        bak = f"config.Harmo-Dsp.bak-{datetime.now():%Y%m%d-%H%M%S}"
        try:
            with open(os.path.join(target_dir, bak), "w", encoding="utf-8") as fh:
                fh.write(cur)
            self.log.appendPlainText(f"✓ Backup: {bak}")
            return True
        except OSError:
            pass
        QMessageBox.information(self, "Backup",
                                "Backup needs admin once — approve UAC, then continue.")
        import subprocess
        import sys
        helper = self._helper_path()
        try:
            p = subprocess.run([sys.executable, helper, "--backup-file",
                                target_dir, "config.txt"],
                               capture_output=True, text=True, timeout=180)
            import json
            res = json.loads(p.stdout or "{}")
            if res.get("ok"):
                self.log.appendPlainText(f"✓ Backup: {res['backup']}")
                return True
        except Exception:
            pass
        QMessageBox.warning(self, "Backup",
                            "Backup failed AND elevated helper did not finish.\n"
                            "Nothing was changed. Approve UAC and retry, or pick another folder.")
        return False
