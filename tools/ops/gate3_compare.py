"""Gate-3 numbers: naive baseline + compare table + overlay PNGs."""
import os
import sys

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from scipy.io.wavfile import read as wavread, write as wavwrite
from scipy.signal import group_delay

from harmo_dsp.dsp.compare import (_cascade_metrics, step_metrics,
                                   markdown_table)

OUT = r"L:\Temp\opencode\gate3"
FS = 48000

_, meas = wavread(os.path.join(OUT, "meas.wav"))
spk = np.asarray(meas, dtype=np.float64)
if spk.ndim > 1:
    spk = spk.mean(axis=1)
spk = spk - np.median(spk)
spk = spk / max(np.abs(spk).max(), 1e-12)

_, fa = wavread(os.path.join(OUT, "A-mixed.wav"))
_, fb = wavread(os.path.join(OUT, "B-minphase.wav"))
ta = np.asarray(fa, dtype=np.float64).ravel()
tb = np.asarray(fb, dtype=np.float64).ravel()


def naive_inverse(x, taps=4096, floor_db=-20.0):
    n = 8192
    X = np.zeros(n)
    X[:min(len(x), n)] = x[:min(len(x), n)]
    H = np.fft.rfft(X)
    fl = (10.0 ** (floor_db / 20.0) * np.abs(H).max()) ** 2
    Hi = np.conj(H) / (np.abs(H) ** 2 + fl)
    h = np.fft.irfft(Hi, n)[:taps]
    h *= np.hanning(taps)
    return h / max(np.abs(h).max(), 1e-12)


tc = naive_inverse(spk)
wavwrite(os.path.join(OUT, "C-naive.wav"), FS, tc.astype(np.float32))

rows = []
for name, taps in (("A-ours-mixed", ta), ("B-ours-minphase", tb),
                   ("C-naive-inverse", tc)):
    m = _cascade_metrics(spk, taps, FS)
    s = step_metrics(taps, FS)
    rows.append({"name": name,
                 "mag_before": m["mag_rms_before"],
                 "mag_after": m["mag_rms_after"],
                 "gd_before": m["gd_rms_before"],
                 "gd_after": m["gd_rms_after"],
                 "pre_ring_db": m["pre_ring_db"],
                 "latency_ms": m["latency_ms"],
                 "overshoot_pct": s["overshoot_pct"],
                 "preshoot_pct": s["preshoot_pct"],
                 "rise_ms": s["rise_ms"]})

table = markdown_table(rows)
print(table, flush=True)
with open(os.path.join(OUT, "TABLE.md"), "w", encoding="utf-8") as fh:
    fh.write("# Gate-3 dry run (measured just now, same IR for all)\n\n"
             + table + "\n")

# --- overlays: mag deviation, group delay, step ---
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

app = QApplication.instance() or QApplication([])
cmap = {"A-ours-mixed": "#00cc66", "B-ours-minphase": "#4da6ff",
        "C-naive-inverse": "#ff6b6b"}


def shot(fname, title, series, ylabel, logx=True):
    plt = pg.PlotWidget()
    if logx:
        plt.setLogMode(x=True, y=False)
    plt.setLabel("left", ylabel)
    plt.setLabel("bottom", "Hz" if logx else "ms")
    plt.addLegend()
    for name, x, y in series:
        plt.plot(x, y, pen=pg.mkPen(cmap.get(name, "#ffffff"), width=2),
                 name=name)
    plt.setTitle(title)
    app.processEvents()
    plt.grab().save(os.path.join(OUT, fname))
    plt.close()


N = 8192
f = np.fft.rfftfreq(N, 1.0 / FS)
H0 = np.abs(np.fft.rfft(spk, N))
db0 = 20 * np.log10(np.maximum(H0, 1e-12))
db0 -= float(np.median(db0[(f >= 200) & (f <= 2000)]))
m = (f >= 20) & (f <= 20000)
series = [("raw", f[m], db0[m])]
for name, taps in (("A-ours-mixed", ta), ("B-ours-minphase", tb),
                   ("C-naive-inverse", tc)):
    fixed = np.convolve(spk, taps)[:len(spk)]
    H = np.abs(np.fft.rfft(fixed, N))
    db = 20 * np.log10(np.maximum(H, 1e-12))
    db -= float(np.median(db[(f >= 200) & (f <= 2000)]))
    series.append((name, f[m], db[m]))
shot("overlay_mag.png", "Magnitude: raw vs corrected (dB, median-norm)",
     series, "dB")

fg = np.linspace(100, 1000, 64)
_, gd0 = group_delay((spk, 1.0), w=fg, fs=FS)
series = [("raw", fg, np.asarray(gd0, float))]
for name, taps in (("A-ours-mixed", ta), ("B-ours-minphase", tb),
                   ("C-naive-inverse", tc)):
    fixed = np.convolve(spk, taps)[:len(spk)]
    _, gd = group_delay((fixed, 1.0), w=fg, fs=FS)
    series.append((name, fg, np.asarray(gd, float)))
shot("overlay_gd.png", "Group delay 100-1000 Hz (samples)", series,
     "samples", logx=False)

t = np.arange(600) / FS * 1000.0
series = []
for name, taps in (("raw-delta", np.concatenate([[1.0], np.zeros(599)])),
                   ("A-ours-mixed", ta[:600] if len(ta) >= 600 else ta),
                   ("B-ours-minphase", tb[:600] if len(tb) >= 600 else tb),
                   ("C-naive-inverse", tc[:600] if len(tc) >= 600 else tc)):
    s = np.cumsum(taps)
    s = s / (s[-1] if abs(s[-1]) > 1e-12 else 1.0)
    series.append((name, t[:len(s)], s))
shot("overlay_step.png", "Step response (normalised)", series, "amp",
     logx=False)
print("overlays saved", flush=True)
