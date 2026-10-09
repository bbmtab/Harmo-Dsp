"""In-house mixed-phase FIR designer (the Dirac/rePhase-chasing path).

Original code (MIT). Method (documented in docs/ASSUMPTIONS.md):
- Split each measured IR into minimum-phase (real cepstrum) and
  excess-phase parts. Magnitude correction is always minimum-phase
  (no latency, no pre-ringing). Excess-phase inverse is applied ONLY
  below `phase_below_hz`, ONLY where positions agree (consistency
  weight), scaled by `strength` (0 = identical to min-phase path).
- Frequency-dependent windowing: excess correction is split into
  bands with band-specific window lengths (long windows for bass,
  short for treble) to bound pre-ringing.
- Null guard: no correction (mag or phase) where the response sits
  >40 dB below its peak.

Requires impulse responses (.wav). Magnitude-only input stays on the
minimum-phase path — phase correction without IR data is refused.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import freqz

# (lo_hz, hi_hz, window_ms): long windows for bass, short for treble
DEFAULT_BAND_WINDOWS = [(10.0, 150.0, 40.0), (150.0, 1200.0, 20.0),
                        (1200.0, 24000.0, 5.0)]
NULL_DEPTH_DB = 40.0


def _next_pow2(n: int) -> int:
    return 1 << max(1, int(math.ceil(math.log2(max(2, n)))))


def minphase_spectrum(mag_pos: np.ndarray) -> np.ndarray:
    """Minimum-phase full spectrum from one-sided linear magnitude (rfft grid).

    Real-cepstrum method: fold negative quefrencies, exp(fft()).
    """
    mag = np.maximum(np.asarray(mag_pos, dtype=np.float64), 1e-12)
    n = (len(mag) - 1) * 2
    logm = np.log(mag)
    full = np.concatenate([logm, logm[-2:0:-1]])  # two-sided, length n
    cep = np.fft.ifft(full).real
    win = np.zeros(n)
    win[0] = cep[0]
    win[1:n // 2] = 2.0 * cep[1:n // 2]
    win[n // 2] = cep[n // 2]
    return np.exp(np.fft.fft(win))


def rfftfreqs(n: int, fs: float) -> np.ndarray:
    return np.fft.rfftfreq(n, 1.0 / fs)


def _raised_cosine_edge(f: np.ndarray, edge: float, width_oct: float = 1 / 6) -> np.ndarray:
    """Smooth 0..1 step centred at `edge` (for band masks / cutoffs)."""
    lo = edge / (2.0 ** (width_oct / 2.0))
    hi = edge * (2.0 ** (width_oct / 2.0))
    x = np.clip((np.log2(np.maximum(f, 1e-9) / lo)) / (width_oct), 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(math.pi * np.clip(x, 0.0, 1.0))


def _band_mask(f: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return _raised_cosine_edge(f, lo) * (1.0 - _raised_cosine_edge(f, hi))


@dataclass
class FirReport:
    taps: np.ndarray
    fs: int
    taps_n: int
    latency_ms: float
    pre_ring_db: float
    peak_db: float = 0.0
    notes: list[str] = field(default_factory=list)


def _truncate_front(h: np.ndarray, taps: int) -> np.ndarray:
    """Causal truncation with short fade (for minimum-phase part)."""
    h = np.asarray(h, dtype=np.float64)[:taps].copy()
    fade = max(8, taps // 20)
    if len(h) > fade:
        ramp = 0.5 + 0.5 * np.cos(np.pi * np.arange(fade) / fade)
        h[-fade:] *= ramp[::-1]
    return h


def _band_windowed_excess(Hexc_full: np.ndarray, n: int, fs: float,
                          bands=DEFAULT_BAND_WINDOWS) -> np.ndarray:
    """Frequency-dependent windowing: each band gets its own window length,
    placed around THAT BAND's own peak (dispersive signals peak at
    different times per band). CIRCULAR extraction/insertion: IFFT output
    wraps, so linear slicing would amputate peaks at the buffer edge."""
    f = np.fft.rfftfreq(n, 1.0 / fs)
    Hpos = Hexc_full[:len(f)]
    out = np.zeros(n)
    for lo, hi, ms in bands:
        win_len = max(32, int(float(ms) / 1000.0 * fs) | 1)
        mask = _band_mask(f, max(lo, f[1]), min(hi, f[-1]))
        Hm = np.zeros(n, dtype=complex)
        Hm[:len(f)] = Hpos * mask
        Hm[len(f):] = np.conj(Hpos[1:-1][::-1] * mask[1:-1][::-1])
        hb = np.fft.ifft(Hm).real
        peak = int(np.argmax(np.abs(hb)))
        half = win_len // 2
        win = np.hanning(win_len)
        idx = (peak - half + np.arange(win_len)) % n
        out[idx] += hb[idx] * win
    # preserve unity: a phase-only correction must average |H| ~= 1
    Hout = np.abs(np.fft.rfft(out))
    mean_mag = float(np.mean(Hout[1:])) if len(Hout) > 1 else 0.0
    if mean_mag > 1e-12:
        out /= mean_mag
    return out


@dataclass
class FirParams:
    taps: int = 4096
    strength: float = 0.3      # 0..1 (UI shows 0..100%)
    phase_below_hz: float = 300.0
    boost_max_db: float = 6.0
    cut_max_db: float = 30.0
    target_db: float = 0.0     # flat target level (tilt = future)


def design_mag_only(avg_mag: np.ndarray, n: int, fs: float,
                    p: FirParams, weight: np.ndarray) -> np.ndarray:
    """Minimum-phase FIR (length `taps`) for the magnitude correction."""
    with np.errstate(divide="ignore"):
        corr_db = (p.target_db - 20.0 * np.log10(np.maximum(avg_mag, 1e-12))) * weight
    corr_db = np.clip(corr_db, -p.cut_max_db, p.boost_max_db)
    Cmag = 10.0 ** (corr_db / 20.0)
    Hmin = minphase_spectrum(Cmag)
    h = np.fft.ifft(Hmin).real
    return _truncate_front(h, p.taps)


def design_speaker_fir(irs: list[np.ndarray], fs: int,
                       p: FirParams) -> FirReport:
    """Full mixed-phase design from 1+ measured IRs (same fs)."""
    notes: list[str] = []
    n = _next_pow2(max(len(r) for r in irs) * 2)
    specs = []
    mags = []
    for r in irs:
        x = np.zeros(n)
        x[:len(r)] = np.asarray(r, dtype=np.float64)
        H = np.fft.rfft(x)
        specs.append(H)
        mags.append(np.abs(H))
    mags = np.array(mags)
    mean_mag = mags.mean(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(mean_mag > 1e-12, mags.std(axis=0) / np.maximum(mean_mag, 1e-12), 0.0)
    f = rfftfreqs(n, fs)
    peak_db = float(20 * np.log10(max(mean_mag.max(), 1e-12)))
    with np.errstate(divide="ignore"):
        mag_db = 20.0 * np.log10(np.maximum(mean_mag, 1e-12))
    consistency = 1.0 / (1.0 + 3.0 * cv)
    null_gate = np.clip((mag_db - (peak_db - NULL_DEPTH_DB)) / 20.0, 0.0, 1.0)
    weight = consistency * null_gate
    if (weight < 0.2).mean() > 0.7:
        notes.append("Low inter-position consistency — correction mostly skipped (safe).")

    h_min = design_mag_only(mean_mag, n, fs, p, weight)

    if p.strength <= 0.0:
        h = h_min  # identical to the minimum-phase path, by construction
        notes.append("strength 0% — pure minimum-phase (no excess-phase).")
    else:
        # excess-phase per position, circular mean, phase-only inverse
        exc_sum = np.zeros(n, dtype=complex)
        for H in specs:
            Hfull = np.concatenate([H, np.conj(H[1:-1][::-1])])
            Hmin = minphase_spectrum(np.abs(H))
            floor = (1e-3 * np.abs(H).max()) ** 2
            E = Hfull * np.conj(Hmin) / (np.abs(Hmin) ** 2 + floor)
            exc_sum += E / np.abs(np.maximum(np.abs(E), 1e-12)) * np.abs(E)
        Emean = exc_sum / max(len(specs), 1)
        gate = _raised_cosine_edge(f, 1.0)  # ignore DC bin noise
        allow = (1.0 - _raised_cosine_edge(f, p.phase_below_hz)) * gate
        ang = np.angle(Emean[:len(f)]) * p.strength * weight * allow
        Cexc_pos = np.exp(-1j * ang)
        Cexc_full = np.concatenate([Cexc_pos, np.conj(Cexc_pos[1:-1][::-1])])
        h_circ = _band_windowed_excess(Cexc_full, n, fs)
        # Linearise: the circular buffer hides pre-response (advance) at its
        # end. Roll the peak to PRE so advance sits linearly in [0..PRE],
        # then truncate causally. A hard crop WITHOUT this step amputates
        # the advance (the bug that broke group-delay correction).
        pre = max(16, p.taps // 4)
        pk_circ = int(np.argmax(np.abs(h_circ)))
        h_shift = np.roll(h_circ, pre - pk_circ)
        h_exc = h_shift[:p.taps].copy()
        h = np.convolve(h_min, h_exc)
        # Final crop: peak back to `pre`, Hann with exact peak compensation.
        # Peak-first placement is REQUIRED: a Hann edge is 0 and would
        # annihilate a peak sitting at index 0.
        pk = int(np.argmax(np.abs(h)))
        desired = pre
        start = pk - desired
        seg = np.zeros(p.taps)
        src_lo, src_hi = max(0, start), min(len(h), start + p.taps)
        dst_lo = src_lo - start
        seg[dst_lo:dst_lo + (src_hi - src_lo)] = h[src_lo:src_hi]
        # Asymmetric window: FLAT over the pre-response (advance must survive
        # exactly — a Hann rising edge would suppress it), fade only the tail.
        # A symmetric Hann here was the bug that re-broke group delay.
        win = np.ones(p.taps)
        fade_from = 3 * p.taps // 4
        k = p.taps - fade_from
        win[fade_from:] = 0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k)
        seg *= win
        h = seg
        notes.append(f"excess-phase below {p.phase_below_hz:g} Hz @ {p.strength * 100:.0f}%.")

    peak_i = int(np.argmax(np.abs(h)))
    total_e = float(np.sum(h.astype(np.float64) ** 2)) + 1e-18
    pre_e = float(np.sum(h[:max(peak_i - int(fs * 0.001), 0)].astype(np.float64) ** 2))
    pre_ring_db = float(10.0 * math.log10(max(pre_e / total_e, 1e-12)))
    return FirReport(taps=h.astype(np.float64), fs=fs, taps_n=len(h),
                     latency_ms=peak_i / fs * 1000.0,
                     pre_ring_db=pre_ring_db, peak_db=peak_db, notes=notes)


def save_fir_wav(path: str, rep: FirReport, normalize: bool = True) -> None:
    """Write Convolution-ready float32 WAV (peak-normalised by default)."""
    from scipy.io.wavfile import write as wavwrite
    x = rep.taps.astype(np.float64)
    if normalize:
        pk = np.abs(x).max()
        if pk > 1e-12:
            x = x / pk * 0.95
    wavwrite(path, rep.fs, x.astype(np.float32))
