"""Target curves for RTA overlay + auto-solver (bass shelf corner configurable).

The user's house curve: flat mids/highs, bass rising BELOW the corner
(default 80 Hz per user spec — classic sub-bass lift).
"""
from __future__ import annotations
import numpy as np

PRESETS = {
    "flat": {"bass_db": 0.0, "tilt_db_per_oct": 0.0, "corner_hz": 150.0},
    "bass+3@80": {"bass_db": 3.0, "tilt_db_per_oct": 0.0, "corner_hz": 80.0},
    "bass+6@80": {"bass_db": 6.0, "tilt_db_per_oct": 0.0, "corner_hz": 80.0},
    "bass+3@150": {"bass_db": 3.0, "tilt_db_per_oct": 0.0, "corner_hz": 150.0},
    "bass+6@150": {"bass_db": 6.0, "tilt_db_per_oct": 0.0, "corner_hz": 150.0},
    "tilt-0.5": {"bass_db": 0.0, "tilt_db_per_oct": -0.5, "corner_hz": 150.0},
    "bass+3 tilt-0.5@80": {"bass_db": 3.0, "tilt_db_per_oct": -0.5,
                           "corner_hz": 80.0},
}


def target_curve_db(freqs, bass_db: float = 0.0,
                    tilt_db_per_oct: float = 0.0,
                    corner_hz: float = 80.0) -> np.ndarray:
    """Smooth shelf below `corner_hz` + gentle octave tilt (0 dB @ 1 kHz)."""
    f = np.maximum(np.asarray(freqs, dtype=np.float64), 1e-3)
    y = np.zeros_like(f)
    y += float(bass_db) / (1.0 + (f / corner_hz) ** 4)
    # downward tilt: negative tilt lowers TREBLE (bass ends up hotter)
    y += float(tilt_db_per_oct) * np.log2(f / 1000.0)
    return y


def preset_curve(freqs, name: str, corner_hz: float | None = None) -> np.ndarray:
    p = dict(PRESETS.get(name, PRESETS["flat"]))
    if corner_hz:
        p["corner_hz"] = float(corner_hz)
    return target_curve_db(freqs, **p)
