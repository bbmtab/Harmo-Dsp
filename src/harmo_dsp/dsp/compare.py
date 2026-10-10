"""Gate-3 comparison harness: identical metrics for every FIR candidate.

Candidates: A = our in-house FIR, B = user's rePhase impulse.txt,
C = DRC-FIR plugin output (when Fase 4 lands). Same code path for all —
the table is the verdict, never adjectives.
"""
from __future__ import annotations
import math

import numpy as np
from scipy.signal import freqz, group_delay


def load_foreign_fir(path: str, fs: int) -> np.ndarray:
    """User-supplied FIR: .wav IR, or raw float-per-line .txt (rePhase
    impulse.txt style). Sample rate ALWAYS from the user, never guessed."""
    import os
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if path.lower().endswith(".wav"):
        from scipy.io.wavfile import read as wavread
        rate, data = wavread(path)
        a = np.asarray(data, dtype=np.float64)
        if a.ndim > 1:
            a = a.mean(axis=1)
        if np.issubdtype(np.asarray(data).dtype, np.integer):
            a /= float(2 ** (np.asarray(data).dtype.itemsize * 8 - 1))
        return a
    vals = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip().replace(",", ".")
            if not line:
                continue
            try:
                vals.append(float(line.split()[0]))
            except ValueError:
                continue
    if not vals:
        raise ValueError(f"no numeric samples in {path}")
    return np.asarray(vals, dtype=np.float64)


def _cascade_metrics(spk: np.ndarray, taps: np.ndarray, fs: float,
                     f_lo: float = 30.0, f_hi: float = 8000.0,
                     gd_lo: float = 100.0, gd_hi: float = 1000.0) -> dict:
    """Before/after metrics of speaker-corrected cascade (truncated)."""
    n = len(spk)
    fixed = np.convolve(np.asarray(spk, dtype=np.float64),
                        np.asarray(taps, dtype=np.float64))[:n]

    def rms_dev(h):
        from numpy.fft import rfft, rfftfreq
        H = np.abs(rfft(h, 8192))
        f = rfftfreq(8192, 1.0 / fs)
        m = (f >= f_lo) & (f <= f_hi)
        db = 20.0 * np.log10(np.maximum(H[m], 1e-12))
        return float(np.sqrt(np.mean((db - db.mean()) ** 2)))

    def gd_dev(h):
        f = np.linspace(gd_lo, gd_hi, 64)
        _, gd = group_delay((h, 1.0), w=f, fs=fs)
        gd = np.asarray(gd, dtype=float)
        gd = gd[np.isfinite(gd)]
        return float(np.sqrt(np.mean((gd - np.median(gd)) ** 2)))

    pk = int(np.argmax(np.abs(taps)))
    total = float(np.sum(np.asarray(taps, dtype=np.float64) ** 2)) + 1e-18)
    pre = float(np.sum(np.asarray(taps)[:max(pk - int(fs * 0.001), 0)]
                       .astype(np.float64) ** 2))
    return {
        "mag_rms_before": rms_dev(spk),
        "mag_rms_after": rms_dev(fixed),
        "gd_rms_before": gd_dev(spk),
        "gd_rms_after": gd_dev(fixed),
        "pre_ring_db": float(10.0 * math.log10(max(pre / total, 1e-12))),
        "latency_ms": pk / fs * 1000.0,
    }


def step_metrics(taps: np.ndarray, fs: float) -> dict:
    """Step response: overshoot %, pre-shoot %, 10-90 % rise (ms)."""
    h = np.asarray(taps, dtype=np.float64)
    if np.abs(h).max() <= 0:
        return {"overshoot_pct": 0.0, "preshoot_pct": 0.0,
                "rise_ms": 0.0}
    s = np.cumsum(h)
    final = s[-1] if abs(s[-1]) > 1e-12 else 1.0
    sn = s / final
    pk = int(np.argmax(np.abs(h)))
    pre = sn[:pk]
    return {
        "overshoot_pct": round(float(max(0.0, sn.max() - 1.0) * 100.0), 2),
        "preshoot_pct": round(float(max(0.0, -pre.min()) * 100.0), 2),
        "rise_ms": round(_rise_time(sn, fs), 3),
    }


def _rise_time(sn: np.ndarray, fs: float) -> float:
    try:
        i10 = int(np.argmax(sn >= 0.1))
        i90 = int(np.argmax(sn >= 0.9))
        return max(0, i90 - i10) / fs * 1000.0
    except ValueError:
        return 0.0


def markdown_table(rows: list[dict]) -> str:
    """rows: [{name, mag_before, mag_after, gd_before, gd_after,
    pre_ring_db, latency_ms, overshoot_pct, preshoot_pct, rise_ms}]."""
    head = ("| FIR | mag RMS before→after (dB) | gd RMS before→after "
            "| pre-ring (dB) | latency (ms) | over / pre-shoot % | rise (ms) |")
    sep = "|---|---|---|---|---|---|---|"
    lines = [head, sep]
    for r in rows:
        lines.append(
            f"| {r['name']} "
            f"| {r['mag_before']:.2f} → {r['mag_after']:.2f} "
            f"| {r['gd_before']:.2f} → {r['gd_after']:.2f} "
            f"| {r['pre_ring_db']:.1f} | {r['latency_ms']:.2f} "
            f"| {r['overshoot_pct']:.1f} / {r['preshoot_pct']:.1f} "
            f"| {r['rise_ms']:.2f} |")
    return "\n".join(lines)
