"""Guided measurement core: log-sweep (Farina) + deconvolution + levels.

Original code (MIT). Method: exponential sine sweep, Farina inverse
(time-reversed sweep with +6 dB/oct amplitude correction), spectral
division by convolution. Textbook DSP, implementation our own.
"""
from __future__ import annotations
import math
import numpy as np


def log_sweep(fs: int, dur_s: float = 5.0, f0: float = 20.0,
              f1: float = 20000.0, fade_ms: float = 50.0,
              level: float = 0.5) -> np.ndarray:
    """Exponential sine sweep (Farina). f1 capped below Nyquist."""
    f1 = min(f1, fs / 2.0 * 0.95)
    n = int(dur_s * fs)
    t = np.arange(n) / fs
    k = math.log(f1 / f0)
    phase = 2.0 * math.pi * f0 * dur_s / k * (np.exp(t / dur_s * k) - 1.0)
    x = np.sin(phase)
    nf = max(1, int(fade_ms / 1000.0 * fs))
    fade = 0.5 - 0.5 * np.cos(np.pi * np.arange(nf) / nf)
    x[:nf] *= fade
    x[-nf:] *= fade[::-1]
    return (x * level).astype(np.float64)


def inverse_filter(sweep: np.ndarray, fs: int, f0: float = 20.0,
                   f1: float = 20000.0, dur_s: float = 5.0,
                   floor_db: float = -60.0) -> np.ndarray:
    """Exact inverse by spectral division (zero-forcing with floor).

    Avoids the ±dB/oct envelope lore of time-domain Farina inverses:
    Inv = conj(X)/(|X|^2 + eps). Unused params kept for API stability.
    """
    from numpy.fft import rfft, irfft
    X = rfft(np.asarray(sweep, dtype=np.float64))
    floor = (10.0 ** (floor_db / 20.0) * np.abs(X).max()) ** 2
    inv = irfft(np.conj(X) / (np.abs(X) ** 2 + floor), n=len(sweep))
    return inv.astype(np.float64)


def deconvolve(recorded: np.ndarray, sweep: np.ndarray,
               fs: int, ir_len: int | None = None,
               max_delay_s: float = 0.5) -> np.ndarray:
    """Recover IR from a sweep recording. Returns first `ir_len` samples.

    The pulse is SEARCHED (argmax in [N-1, N-1+max_delay]): real rooms
    have 10–500 ms bulk delay, so a fixed index would decapitate the IR.
    """
    inv = inverse_filter(sweep, fs)
    full = np.convolve(np.asarray(recorded, dtype=np.float64), inv)
    base = len(sweep) - 1
    win = full[base:base + max(1, int(max_delay_s * fs)) + 1]
    start = base + int(np.argmax(np.abs(win)))
    ir = full[start:]
    if ir_len is not None:
        ir = ir[:ir_len]
    peak = np.abs(ir).max()
    if peak <= 0:
        raise ValueError("Deconvolution failed — recording is silent")
    return ir


def level_dbfs(x: np.ndarray) -> tuple[float, float]:
    """(peak_dBFS, rms_dBFS)."""
    a = np.asarray(x, dtype=np.float64)
    peak = float(np.abs(a).max())
    rms = float(np.sqrt(np.mean(a ** 2)))
    conv = lambda v: 20.0 * math.log10(v) if v > 0 else -120.0
    return conv(peak), conv(rms)


def level_verdict(peak_db: float, rms_db: float) -> str:
    if peak_db >= -1.0:
        return "TOO LOUD — clipping risk, lower volume"
    if peak_db >= -24.0:
        return "OK — good level for measurement"
    return "TOO QUIET — raise volume / mic gain"
