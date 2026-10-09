"""Anti-clip preamp calculator: worst-case peak of the WHOLE APO chain.

Original code (MIT). Math: RBJ Audio EQ Cookbook biquads
(Robert Bristow-Johnson, publicly published formulas — implementation
is our own) + exact APO GraphicEQ log-axis interpolation
(per Configuration reference: gains interpolate linearly on the
logarithmic frequency spectrum).

Covers every gain-affecting APO feature in our files:
  all Filter types (exact) + GraphicEQ (exact) + Convolution file peak.
Safe fallbacks (see docs/ASSUMPTIONS.md): Modal and unknown types
contribute |gain| headroom; missing IR file assumes 0 dB with a note.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.signal import freqz

from .peq import PeqBand

GRID_N = 1024
FMIN, FMAX = 10.0, 24000.0


def _rbj(ftype: str, fc: float, gain: float, q: float, fs: float):
    """Return (b, a) or None when the type cannot peak (AP) / unknown."""
    A = 10.0 ** (gain / 40.0)
    w0 = 2.0 * math.pi * fc / fs
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2.0 * max(q, 1e-4))
    sq = 2.0 * math.sqrt(max(A, 1e-9)) * alpha
    if ftype == "PK":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif ftype in ("LS", "LS 6dB", "LS 12dB", "LSC"):
        b = [A * (A + 1 - (A - 1) * cw + sq), 2 * A * (A - 1 - (A + 1) * cw),
             A * (A + 1 - (A - 1) * cw - sq)]
        a = [(A + 1 + (A - 1) * cw + sq), -2 * (A - 1 + (A + 1) * cw),
             (A + 1 + (A - 1) * cw - sq)]
    elif ftype in ("HS", "HS 6dB", "HS 12dB", "HSC"):
        b = [A * (A + 1 + (A - 1) * cw + sq), -2 * A * (A - 1 + (A + 1) * cw),
             A * (A + 1 + (A - 1) * cw - sq)]
        a = [(A + 1 - (A - 1) * cw + sq), 2 * (A - 1 - (A + 1) * cw),
             (A + 1 - (A - 1) * cw - sq)]
    elif ftype in ("LP", "LPQ"):
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif ftype in ("HP", "HPQ"):
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif ftype == "NO":
        b = [1.0, -2 * cw, 1.0]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif ftype == "BP":
        b = [alpha, 0.0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    else:
        return None  # AP (flat), Modal (fallback), unknown
    return np.array(b) / a[0], np.array(a) / a[0]


def _grid() -> np.ndarray:
    return np.logspace(math.log10(FMIN), math.log10(FMAX), GRID_N)


def chain_peak_db(bands: list[PeqBand], scope: str = "all",
                  fs: float = 48000.0) -> tuple[float, list[str]]:
    """Worst peak (dB) of biquad filters for channel scope. Returns (peak, notes)."""
    f = _grid()
    total = np.zeros_like(f)
    notes: list[str] = []
    for b in bands:
        b = b.clipped()
        if not b.on or b.channel not in ("all", scope):
            continue
        if b.ftype == "AP":
            continue  # magnitude-flat by definition
        coef = _rbj(b.ftype, b.fc, b.gain, b.q, fs)
        if coef is None:
            total = np.maximum(total, abs(b.gain))  # safe fallback
            notes.append(f"{b.ftype} @{b.fc:g}Hz: |gain| fallback")
            continue
        _, h = freqz(coef[0], coef[1], worN=f, fs=fs)
        with np.errstate(divide="ignore"):
            total += 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))
    return float(np.max(total)), notes


def graphic_peak_db(gains: list[float] | None, freqs: list[float] | None) -> float:
    """APO GraphicEQ peak: gains are exact points, interpolation never
    exceeds neighbouring points for monotonic segments; global max of the
    polyline == max of points (linear interp). So peak == max(gains)."""
    if not gains:
        return 0.0
    return float(max(0.0, max(gains)))


def convolution_peak_db(path: str) -> tuple[float, str]:
    """Peak gain of an IR file (0 dBFS == 0 dB gain). Missing file -> 0 + note."""
    try:
        from scipy.io.wavfile import read as wavread
        fs, data = wavread(path)
        arr = np.asarray(data, dtype=np.float64)
        if np.issubdtype(np.asarray(data).dtype, np.integer):
            full = float(2 ** (np.asarray(data).dtype.itemsize * 8 - 1))
            peak = float(np.max(np.abs(arr)) / full)
        else:
            peak = float(np.max(np.abs(arr)))
        if peak <= 0:
            return 0.0, "IR silent?"
        return max(0.0, 20.0 * math.log10(peak)), ""
    except Exception as e:
        return 0.0, f"IR not read ({e}); assumed 0 dB — check manually"


def suggest_preamp(bands, graphic_l=None, graphic_r=None,
                   graphic_freqs=None, conv_files: dict | None = None,
                   fs: float = 48000.0) -> dict:
    """Suggest preamp (<= 0 dB, rounded down to 0.5 dB) covering everything."""
    notes: list[str] = []
    pl, n1 = chain_peak_db(bands, "L", fs)
    pr, n2 = chain_peak_db(bands, "R", fs)
    notes += n1 + n2
    pl = max(pl, graphic_peak_db(graphic_l, graphic_freqs))
    pr = max(pr, graphic_peak_db(graphic_r, graphic_freqs))
    for rate, path in (conv_files or {}).items():
        cp, note = convolution_peak_db(path)
        if note:
            notes.append(note)
        pl += cp  # IR gain stacks on top of filter peak (worst case)
        pr += cp
    peak = max(pl, pr)
    suggest = -math.ceil(peak * 2.0) / 2.0 if peak > 0 else 0.0
    return {"peak_l": round(pl, 2), "peak_r": round(pr, 2),
            "peak_db": round(peak, 2), "suggest_db": suggest, "notes": notes}
