"""Live sound visualization: spectrum analyzer fed by the soundcard.

Sources: microphone input OR WASAPI loopback (Windows: pick the input
whose name ends in "(loopback)" to see what the speakers play).
No hardware/backend => hint + disabled controls, never a crash.
"""
import numpy as np

LOG_GRID = np.logspace(np.log10(20.0), np.log10(20000.0), 240)


class SpectrumEngine:
    """Backend-free spectrum math (testable without hardware/Qt)."""

    def __init__(self, fs: int = 48000, n_fft: int = 8192):
        self.fs = fs
        self.n_fft = n_fft
        self.buf = np.zeros(0)
        self.peak_hold: np.ndarray | None = None

    def feed(self, x: np.ndarray) -> None:
        x = np.asarray(x, dtype=np.float64).ravel()
        self.buf = np.concatenate([self.buf, x])[-self.n_fft * 2:]

    def spectrum_db(self) -> tuple[np.ndarray, np.ndarray]:
        """(freqs, dBFS) of the latest window, Hann-weighted."""
        n = min(len(self.buf), self.n_fft)
        if n < 256:
            return LOG_GRID, np.full_like(LOG_GRID, -120.0)
        seg = self.buf[-n:] * np.hanning(n)
        spec = np.abs(np.fft.rfft(seg, self.n_fft))
        f = np.fft.rfftfreq(self.n_fft, 1.0 / self.fs)
        with np.errstate(divide="ignore"):
            db = 20.0 * np.log10(np.maximum(spec, 1e-12))
        db -= 20.0 * np.log10(n / 4.0)  # Hann coherent gain -> dBFS-ish
        out = np.interp(np.log10(LOG_GRID),
                        np.log10(np.maximum(f[1:], 1e-9)), db[1:],
                        left=-120.0, right=-120.0)
        if self.peak_hold is None or len(self.peak_hold) != len(out):
            self.peak_hold = out.copy()
        else:
            self.peak_hold = np.maximum(self.peak_hold * 0.999, out)
        return LOG_GRID, out

    def reset_hold(self) -> None:
        self.peak_hold = None


try:
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QPushButton, QComboBox, QCheckBox,
                                   QProgressBar)
    from PySide6.QtCore import QTimer, Qt
    import pyqtgraph as pg

    class LiveSpectrum(QWidget):
        """Spectrum analyzer widget (needs sounddevice + a real device)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.eng = SpectrumEngine()
            self.stream = None
            lay = QVBoxLayout(self)
            top = QHBoxLayout()
            self.dev = QComboBox()
            self.dev.setToolTip("Mic for room, or a '(loopback)' device to see speaker output")
            self.btn_go = QPushButton("▶ Start monitor")
            self.btn_go.clicked.connect(self._toggle)
            self.hold = QCheckBox("Peak hold")
            self.hold.setToolTip("Keep maximum trace (find resonances)")
            self.hold.toggled.connect(lambda _on: self.eng.reset_hold())
            top.addWidget(QLabel("📊 Source:"))
            top.addWidget(self.dev, 1)
            top.addWidget(self.btn_go)
            top.addWidget(self.hold)
            lay.addLayout(top)
            self.plot = pg.PlotWidget()
            self.plot.setLogMode(x=True, y=False)
            self.plot.setYRange(-100, 0)
            self.plot.setLabel("left", "dBFS")
            self.plot.setLabel("bottom", "Hz")
            self.plot.setMinimumHeight(170)
            self.curve = self.plot.plot(pen=pg.mkPen("#4da6ff", width=2))
            self.peak = self.plot.plot(pen=pg.mkPen("#ff6b6b", width=1,
                                                   style=Qt.DashLine))
            lay.addWidget(self.plot)
            self.note = QLabel("")
            self.note.setWordWrap(True)
            lay.addWidget(self.note)
            self.timer = QTimer(self)
            self.timer.setInterval(120)
            self.timer.timeout.connect(self._tick)
            self._refresh_devices()

        def _refresh_devices(self):
            from ..io.audio import available, devices
            if not available():
                self.note.setText("⚠ sounddevice missing → monitor off (pip install sounddevice).")
                self.btn_go.setEnabled(False)
                return
            _, ins = devices()
            self.dev.addItems(ins or ["(no input device)"])
            self.note.setText("Tip: on Windows choose the input ending in '(loopback)' to watch speaker output.")

        def _toggle(self):
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
                self.stream = None
                self.timer.stop()
                self.btn_go.setText("▶ Start monitor")
                return
            from ..io.audio import _idx
            import sounddevice as sd
            try:
                self.stream = sd.InputStream(device=_idx(self.dev.currentText()),
                                             channels=1, samplerate=48000,
                                             callback=self._cb, blocksize=2048)
                self.eng.fs = 48000
                self.stream.start()
                self.timer.start()
                self.btn_go.setText("■ Stop")
                self.note.setText("Monitoring… play music to see the live spectrum.")
            except Exception as e:
                self.note.setText(f"⚠ Cannot open device: {e}")

        def _cb(self, indata, frames, time_info, status):
            self.eng.feed(np.asarray(indata[:, 0], dtype=np.float64))

        def _tick(self):
            f, db = self.eng.spectrum_db()
            self.curve.setData(f, db)
            if self.hold.isChecked() and self.eng.peak_hold is not None:
                self.peak.setData(f, self.eng.peak_hold)
            else:
                self.peak.clear()

    class PredictedCurve(QWidget):
        """Filter response curve from current bands (real biquad math)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.plot = pg.PlotWidget()
            self.plot.setLogMode(x=True, y=False)
            self.plot.setYRange(-32, 8)
            self.plot.setLabel("left", "dB")
            self.plot.setLabel("bottom", "Hz")
            self.plot.setMinimumHeight(150)
            self.plot.addLine(y=0, pen=pg.mkPen("#666666", width=1))
            self.curve = self.plot.plot(pen=pg.mkPen("#00cc66", width=2))
            lay.addWidget(self.plot)

        def set_bands(self, bands, preamp_db: float = 0.0) -> None:
            from ..dsp.clip_guard import chain_response_db
            try:
                y = chain_response_db(bands, LOG_GRID) + float(preamp_db)
                self.curve.setData(LOG_GRID, y)
            except Exception:
                pass

    def peak_to_db(peak: float | None) -> float | None:
        """Pure: OS peak 0..1 -> dBFS (None for silence/unavailable)."""
        if peak is None or peak <= 0.0:
            return None
        import math
        return 20.0 * math.log10(min(max(peak, 1e-9), 1.0))

    class OutputMeter(QWidget):
        """Always-on Peace-style output meter (no mic, OS session API).

        Unavailable backend => dimmed bar + hint, never a crash
        (service/headless sessions have no audio endpoint)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(6, 0, 6, 0)
            icon = QLabel("🔊")
            icon.setToolTip("Windows output level (all apps). Red = near clip.")
            lay.addWidget(icon)
            self.bar = QProgressBar()
            self.bar.setRange(-600, 0)  # x10 dB: -60.0..0.0
            self.bar.setValue(-600)
            self.bar.setTextVisible(False)
            self.bar.setFixedWidth(140)
            self.bar.setFixedHeight(12)
            lay.addWidget(self.bar)
            self.db_label = QLabel("— dB")
            self.db_label.setMinimumWidth(52)
            lay.addWidget(self.db_label)
            self._clip_until_ms = 0
            self._available_seen = False
            self.timer = QTimer(self)
            self.timer.setInterval(120)
            self.timer.timeout.connect(self._tick)
            self.timer.start()
            self.setToolTip("Output peak of the default playback device (like Peace's meter).")

        def _tick(self):
            import time
            from ..io.meter import get_output_peak
            peak = get_output_peak()
            if peak is None:
                if not self._available_seen:
                    self.db_label.setText("— dB")
                    self.bar.setValue(-600)
                return
            self._available_seen = True
            db = peak_to_db(peak)
            if db is None:  # alive but silence
                self.db_label.setText("silent")
                self.bar.setValue(-600)
                self.bar.setStyleSheet(
                    "QProgressBar::chunk { background: #3a5a3a; }")
                return
            self.db_label.setText(f"{db:.1f} dB")
            self.bar.setValue(int(max(-600.0, db * 10.0)))
            now = time.monotonic() * 1000.0
            if db > -0.1:
                self._clip_until_ms = now + 2000.0
            color = "#ff4d4d" if now < self._clip_until_ms else (
                "#4da6ff" if db > -30 else "#3aa06a")
            self.bar.setStyleSheet(
                f"QProgressBar::chunk {{ background: {color}; }}")

except ImportError:  # pyqtgraph/PySide missing (docs builds etc.)
    LiveSpectrum = None  # type: ignore
    PredictedCurve = None  # type: ignore
    OutputMeter = None  # type: ignore
