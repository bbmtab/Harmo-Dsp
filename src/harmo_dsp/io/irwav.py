"""Impulse-response WAV loading (mono mixdown, float64 in [-1, 1])."""
from __future__ import annotations
import numpy as np


def load_ir_mono(path: str) -> tuple[int, np.ndarray]:
    from scipy.io.wavfile import read as wavread
    fs, data = wavread(path)
    arr = np.asarray(data)
    a = arr.astype(np.float64)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if np.issubdtype(arr.dtype, np.integer):
        a /= float(2 ** (arr.dtype.itemsize * 8 - 1))
    if np.abs(a).max() == 0:
        raise ValueError("IR file is silent")
    return int(fs), a
