"""Time alignment (Dirac-style): onset detection + relative delays.

Original code (MIT). Method: peak-normalised envelope, threshold crossing
scanned back from the main peak. Delays are relative (earliest = 0 ms);
APO `Delay:` accepts fractional ms, so sample accuracy is preserved.
"""
from __future__ import annotations
import numpy as np


def onset_index(ir: np.ndarray, fs: int, thresh_db: float = -40.0) -> int:
    """First sample where |IR| rises past threshold (scanned back from peak)."""
    x = np.abs(np.asarray(ir, dtype=np.float64))
    peak = float(x.max())
    if peak <= 0:
        raise ValueError("Silent IR — cannot find onset")
    thr = peak * 10.0 ** (thresh_db / 20.0)
    pk = int(np.argmax(x))
    i = pk
    while i > 0 and x[i] > thr:
        i -= 1
    return i


def estimate_delays(channels: dict[str, tuple[int, np.ndarray]]) -> dict[str, float]:
    """{channel: delay_ms} relative to the earliest onset (reference = 0.0).

    Raises ValueError on sample-rate mismatch.
    """
    if not channels:
        raise ValueError("No IRs to align")
    fs_set = {fs for fs, _ in channels.values()}
    if len(fs_set) != 1:
        raise ValueError(f"Mixed sample rates {sorted(fs_set)}")
    fs = fs_set.pop()
    onsets = {ch: onset_index(x, fs) for ch, (_, x) in channels.items()}
    ref = min(onsets.values())
    return {ch: (on - ref) / fs * 1000.0 for ch, on in onsets.items()}


def align_delays(channels: dict[str, tuple[int, np.ndarray]]) -> dict[str, float]:
    """APO-ready delays: slow channels get 0, EARLY channels are delayed up
    to the latest onset (APO can only delay, never advance).

    Note (official APO docs): bass is often redirected AFTER APO processing,
    so sub-only filtering/delay may not behave as expected — verify by ear.
    """
    rel = estimate_delays(channels)
    latest = max(rel.values())
    return {ch: latest - d for ch, d in rel.items()}
