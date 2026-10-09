"""31-band graphic EQ core (Peace-style ISO 1/3-octave bands).

Frequencies match Peace / Equalizer APO GraphicEQ expectations.
Gains are per-band dB values, -15..+15 by convention.
"""
from __future__ import annotations

ISO31 = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
    200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000,
]

GAIN_MIN, GAIN_MAX = -15.0, 15.0


def clamp_gains(gains: list[float]) -> list[float]:
    return [max(GAIN_MIN, min(GAIN_MAX, float(g))) for g in gains]


def zero_gains() -> list[float]:
    return [0.0] * len(ISO31)


def _fmt_freq(f: float) -> str:
    return str(int(f)) if float(f).is_integer() else str(f)


def to_apo_graphic_eq(gains: list[float], channel: str = "") -> str:
    """Render an Equalizer APO GraphicEQ line.

    Example: GraphicEQ: 20 0; 25 -1.5; ... ; 20000 0;
    channel: "" (both), "L" or "R" -> prefix 'Channel: L' handled by caller.
    """
    g = clamp_gains(list(gains) + [0.0] * (len(ISO31) - len(gains)))
    pairs = "; ".join(f"{_fmt_freq(f)} {v:g}" for f, v in zip(ISO31, g))
    line = f"GraphicEQ: {pairs};"
    if channel in ("L", "R"):
        line = f"Channel: {channel} {line}"
    return line
