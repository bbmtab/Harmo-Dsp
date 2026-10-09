"""Parametric EQ core: per-band type + fully editable Fc/Gain/Q.

APO Filter line reference (Equalizer APO, GPL project by Jonas Thedering):
  Filter: ON PK Fc 1000 Hz Gain -3.5 dB Q 1.2
Only the *syntax* is mirrored here; all code is original (MIT).
"""
from __future__ import annotations
from dataclasses import dataclass, field

# (code used in APO file, human label, needs_gain, needs_q)
FILTER_TYPES: list[tuple[str, str, bool, bool]] = [
    ("PK", "Peak (potong/dorong area)", True, True),
    ("LSC", "Low Shelf (angkat/turun bass)", True, False),
    ("HSC", "High Shelf (angkat/turun treble)", True, False),
    ("LP", "Low-Pass (buang treble)", False, False),
    ("HP", "High-Pass (buang bass/rumble)", False, False),
    ("NO", "Notch (buang dengung sempit)", False, True),
    ("BP", "Band-Pass (hanya lolos area)", False, True),
    ("AP", "All-Pass (putar fase saja)", False, True),
]

_TYPE_CODES = {c for c, _, _, _ in FILTER_TYPES}


@dataclass
class PeqBand:
    on: bool = True
    ftype: str = "PK"
    fc: float = 1000.0
    gain: float = 0.0
    q: float = 1.0

    def clipped(self) -> "PeqBand":
        fc = max(10.0, min(24000.0, float(self.fc)))
        gain = max(-15.0, min(15.0, float(self.gain)))
        q = max(0.1, min(20.0, float(self.q)))
        ftype = self.ftype if self.ftype in _TYPE_CODES else "PK"
        return PeqBand(self.on, ftype, fc, gain, q)


def default_bands(n: int = 10) -> list[PeqBand]:
    """Peace shows ~10 filter rows; default to flat PK at log-spaced Fc."""
    import math
    bands = []
    for i in range(max(1, n)):
        frac = i / max(1, n - 1)
        fc = 30.0 * (20000.0 / 30.0) ** frac
        bands.append(PeqBand(True, "PK", round(fc, 1), 0.0, 1.0))
    return bands


def _fmt(fc: float) -> str:
    return str(int(fc)) if float(fc).is_integer() else f"{fc:g}"


def to_apo_filter_lines(bands: list[PeqBand], channel: str = "") -> list[str]:
    """Render APO 'Filter:' lines, skipping bands that are off or 0-effect PEQ."""
    lines = []
    prefix = f"Channel: {channel} " if channel in ("L", "R") else ""
    for b in (x.clipped() for x in bands):
        if not b.on:
            continue
        if b.ftype in ("PK", "LSC", "HSC") and b.gain == 0:
            continue
        if b.ftype in ("PK", "NO", "BP", "AP"):
            lines.append(f"{prefix}Filter: ON {b.ftype} Fc {_fmt(b.fc)} Hz Gain {b.gain:g} dB Q {b.q:g}")
        elif b.ftype in ("LSC", "HSC"):
            lines.append(f"{prefix}Filter: ON {b.ftype} Fc {_fmt(b.fc)} Hz Gain {b.gain:g} dB")
        else:  # LP / HP
            lines.append(f"{prefix}Filter: ON {b.ftype} Fc {_fmt(b.fc)} Hz")
    return lines
