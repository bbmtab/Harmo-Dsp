"""Auto PEQ solver: flatten a measured response toward a target curve.

Greedy extremum-hunting (original implementation):
- normalise level (median 200-2000 Hz) -> error vs target
- place a PK at the worst extremum; Q from the bump's half-width
- CUTS always allowed; BOOSTS only when wide+shallow and never on nulls
  (deep dips are room artifacts that move with mic position)
- high Q only below xover; above it only wide, gentle corrections
- subtract the placed biquad (real RBJ response) and repeat
"""
from __future__ import annotations
import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import freqz

from .peq import PeqBand
from .clip_guard import _rbj


@dataclass
class SolverParams:
    max_bands: int = 10
    max_boost: float = 6.0
    max_cut: float = 8.0   # was 15: bad-SNR fits made destructive walls of cuts
    q_min: float = 0.5
    q_max_bass: float = 5.0   # was 8: stacked Q8 cuts rang on transients (noise)
    q_max_treble: float = 1.5
    xover_hz: float = 500.0
    fit_lo: float = 30.0
    fit_hi: float = 8000.0
    stop_db: float = 1.0
    null_guard_db: float = -12.0  # dips deeper than this are NEVER boosted
    smooth_frac_oct: float = 1.0 / 6.0  # 0 = off; tames LF noise spikes


def _biquad_db(b: PeqBand, f: np.ndarray, fs: float) -> np.ndarray:
    coef = _rbj(b.ftype, b.fc, b.gain, b.q, fs)
    if coef is None:
        return np.zeros_like(f)
    _, h = freqz(coef[0], coef[1], worN=f, fs=fs)
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))


def _half_width_oct(f: np.ndarray, err: np.ndarray, i: int,
                    amp: float) -> float:
    """Octave width where |error| stays above half the extremum depth."""
    s = 1.0 if amp > 0 else -1.0
    thr = s * abs(amp) / 2.0
    lo = i
    while lo > 0 and s * err[lo - 1] > thr:
        lo -= 1
    hi = i
    while hi < len(err) - 1 and s * err[hi + 1] > thr:
        hi += 1
    if f[hi] <= max(f[lo], 1e-9):
        return 0.1
    return max(float(np.log2(f[hi] / max(f[lo], 1e-9))), 0.05)


def _bw_oct_to_q(bw: float) -> float:
    return 1.0 / (2.0 * math.sinh(math.log(2.0) / 2.0 * max(bw, 1e-3)))


def _smooth_log(f: np.ndarray, y: np.ndarray, frac_oct: float) -> np.ndarray:
    """Moving average ~frac_oct wide on the log-frequency axis (tames
    narrow measurement noise, especially at LF where SNR is worst)."""
    import numpy as np
    n = len(f)
    if n < 8 or frac_oct <= 0:
        return y
    span_oct = float(np.log2(f[-1] / f[0]))
    pts_per_oct = max(1.0, n / max(span_oct, 1e-6))
    w = max(3, int(round(pts_per_oct * frac_oct)) | 1)
    k = np.ones(w) / w
    pad = w // 2
    padded = np.concatenate([np.full(pad, y[0]), y, np.full(pad, y[-1])])
    return np.convolve(padded, k, mode="valid")


def solve_peq(freqs, db, target=None, p: SolverParams | None = None,
              fs: float = 48000.0) -> tuple[list[PeqBand], dict]:
    """Returns (bands, report). `db` may be any absolute level — it is
    median-normalised (200-2000 Hz) before matching the target."""
    p = p or SolverParams()
    f = np.maximum(np.asarray(freqs, dtype=np.float64), 1e-3)
    y = np.asarray(db, dtype=np.float64)
    if p.smooth_frac_oct > 0:
        y = _smooth_log(f, y, p.smooth_frac_oct)
    lvl_mask = (f >= 200) & (f <= 2000)
    ref = float(np.median(y[lvl_mask])) if lvl_mask.sum() > 3 \
        else float(np.median(y))
    err = y - ref
    if target is not None:
        err = err - np.asarray(target, dtype=np.float64)
    fit = (f >= p.fit_lo) & (f <= p.fit_hi)
    if not fit.any():
        return [], {"rms_before": 0.0, "rms_after": 0.0, "placed": 0}

    def rms(e):
        return float(np.sqrt(np.mean(e[fit] ** 2)))

    rms_before = rms(err)
    bands: list[PeqBand] = []
    for _ in range(p.max_bands):
        e_fit = np.where(fit, err, 0.0)
        i_max = int(np.argmax(e_fit))
        cur_max = float(err[i_max]) if fit[i_max] else 0.0
        i_min = int(np.argmin(np.where(fit, err, np.inf)))
        cur_min = float(err[i_min])
        if max(abs(cur_max), abs(cur_min)) < p.stop_db:
            break
        # boost only wide+shallow dips, never nulls; otherwise cut peaks
        boostable = (cur_min < -p.stop_db
                     and -cur_min <= p.max_boost
                     and cur_min > p.null_guard_db)
        if boostable:
            i, amp = i_min, cur_min
        else:
            i, amp = i_max, cur_max
        bw = _half_width_oct(f, err, i, amp)
        qmax = p.q_max_bass if f[i] < p.xover_hz else p.q_max_treble
        q = float(np.clip(_bw_oct_to_q(bw), p.q_min, qmax))
        gain = float(np.clip(-amp, -p.max_cut, p.max_boost))
        if abs(gain) < p.stop_db * 0.5:
            break
        b = PeqBand(True, "PK", float(f[i]), gain, q, channel="all")
        bands.append(b)
        # applying the filter ADDS its response to the system:
        err = err + _biquad_db(b, f, fs)
    return bands, {"rms_before": rms_before, "rms_after": rms(err),
                   "placed": len(bands)}
