"""Parametric EQ core, verified against the official Equalizer APO
Configuration reference (SourceForge wiki, by Jonas Thedering).

Verified facts (do not change without re-checking the docs):
- Filter numbers are NOT interpreted and may be omitted.
- BP is a real band-pass: NO gain param (unlike DCX2496 BP).
- NO (notch) takes Fc + optional Q, NO gain.
- AP (all-pass) takes Fc + Q, NO gain.
- Shelf base codes are LS / HS. LSC / HSC variants take an optional
  slope ("LSC x dB") and optional Q. "LS 6dB / 12dB" corner variants
  take Fc + Gain, no Q.
- GraphicEQ gains interpolate linearly on the LOG frequency axis.
- Preamp values on the same channel SUM in dB (>= v0.8).
- Channel identifiers for stereo: L (1), R (2); "all" = every channel.
- APO processes config lines top to bottom (order matters vs Peace).

Only the *syntax* is mirrored here; all code is original (MIT).
Filter DESIGN (which Fc/Gain/Q to use) is our own code.
"""
from __future__ import annotations
from dataclasses import dataclass

# code, human label, has_gain, has_q, extra_field
FILTER_TYPES: list[tuple[str, str, bool, bool, str]] = [
    ("PK", "Peak (potong/dorong area)", True, True, ""),
    ("LP", "Low-Pass (buang treble)", False, False, ""),
    ("LPQ", "Low-Pass + Q (resonansi)", False, True, ""),
    ("HP", "High-Pass (buang bass/rumble)", False, False, ""),
    ("HPQ", "High-Pass + Q (resonansi)", False, True, ""),
    ("BP", "Band-Pass murni (tanpa gain!)", False, True, ""),
    ("LS", "Low Shelf (bass)", True, False, ""),
    ("LS 6dB", "Low Shelf 6dB/okt (corner)", True, False, ""),
    ("LS 12dB", "Low Shelf 12dB/okt (corner)", True, False, ""),
    ("HS", "High Shelf (treble)", True, False, ""),
    ("HS 6dB", "High Shelf 6dB/okt (corner)", True, False, ""),
    ("HS 12dB", "High Shelf 12dB/okt (corner)", True, False, ""),
    ("LSC", "Low Shelf center-freq + Q", True, True, ""),
    ("HSC", "High Shelf center-freq + Q", True, True, ""),
    ("NO", "Notch (buang dengung, tanpa gain!)", False, True, ""),
    ("AP", "All-Pass (putar fase, tanpa gain!)", False, True, ""),
    ("Modal", "Modal (koreksi mode ruang + T60)", True, True, "t60"),
]

_TYPE = {c: (g, q) for c, _, g, q, _ in FILTER_TYPES}
CHANNELS = ("all", "L", "R")


@dataclass
class PeqBand:
    on: bool = True
    ftype: str = "PK"
    fc: float = 1000.0
    gain: float = 0.0
    q: float = 1.0
    t60: float = 100.0  # ms, Modal only
    channel: str = "all"  # all | L | R

    def clipped(self) -> "PeqBand":
        ftype = self.ftype if self.ftype in _TYPE else "PK"
        ch = self.channel if self.channel in CHANNELS else "all"
        # Gain range ±30 dB: APO itself has no ±15 limit; REW auto-EQ
        # legitimately writes cuts like -21.5 dB (see sample_filter/rew1.txt).
        # Sliders stay ±15 (Peace convention); detail editor allows ±30.
        return PeqBand(
            self.on, ftype,
            max(10.0, min(24000.0, float(self.fc))),
            max(-30.0, min(30.0, float(self.gain))),
            max(0.1, min(20.0, float(self.q))),
            max(10.0, min(2000.0, float(self.t60))),
            ch,
        )


def default_bands(n: int = 10) -> list[PeqBand]:
    bands = []
    for i in range(max(1, n)):
        frac = i / max(1, n - 1)
        fc = 30.0 * (20000.0 / 30.0) ** frac
        bands.append(PeqBand(True, "PK", round(fc, 1), 0.0, 1.0))
    return bands


def _fmt(fc: float) -> str:
    return str(int(fc)) if float(fc).is_integer() else f"{fc:g}"


def band_to_line(b: PeqBand) -> str | None:
    """One APO Filter line, or None when the band has no audible effect."""
    b = b.clipped()
    if not b.on:
        return None
    has_gain, has_q = _TYPE[b.ftype]
    if has_gain and b.gain == 0 and b.ftype in ("PK", "LS", "HS", "LSC", "HSC",
                                                "LS 6dB", "LS 12dB",
                                                "HS 6dB", "HS 12dB", "Modal"):
        return None
    s = f"Filter: ON {b.ftype} Fc {_fmt(b.fc)} Hz"
    if has_gain:
        s += f" Gain {b.gain:g} dB"
    if has_q and not (b.ftype in ("LS", "HS") and b.q == 1.0):
        # LS/HS Q is optional; omit default to keep files clean
        if b.ftype in ("LS", "HS") and b.q == 1.0:
            pass
        else:
            s += f" Q {b.q:g}"
    if b.ftype == "Modal":
        s += f" T60 target {b.t60:g} ms"
    return s


def to_apo_filter_lines(bands: list[PeqBand], channel: str = "") -> list[str]:
    """Flat Filter lines for one channel scope (legacy helper)."""
    out = []
    for b in bands:
        if channel and b.channel not in ("all", channel):
            continue
        line = band_to_line(b)
        if line is not None:
            out.append(line)
    return out


def build_speakercorrect(bands: list[PeqBand], preamp_db: float = 0.0,
                         graphic_l: list[float] | None = None,
                         graphic_r: list[float] | None = None) -> str:
    """Full speakercorrect.txt content with per-channel grouping.

    Layout: header -> Preamp -> Channel L block -> Channel R block.
    Bands with channel 'all' are written into BOTH blocks (APO has no
    'apply to all' persistence across Channel switches for filters,
    so duplication is the correct, explicit form).
    """
    from .geq import to_apo_graphic_eq
    L: list[str] = []
    R: list[str] = []

    def blocks(ch: str) -> list[str]:
        return L if ch == "L" else R

    for scope in ("L", "R"):
        g = graphic_l if scope == "L" else graphic_r
        if g and any(v != 0 for v in g):
            blocks(scope).append(to_apo_graphic_eq(g))
        for b in bands:
            if b.channel not in ("all", scope):
                continue
            line = band_to_line(b)
            if line is not None:
                blocks(scope).append(line)

    out = [
        "# speakercorrect.txt — written by Harmo-Dsp (do not hand-edit)",
        "# Order matters: APO processes top to bottom.",
        "# If Peace is also installed, keep this Include AFTER peace.txt",
        "# so speaker correction applies last.",
        f"Preamp: {preamp_db:g} dB",
        "",
        "Channel: L",
    ]
    out.extend(L if L else ["# (no L filters)"])
    out += ["", "Channel: R"]
    out.extend(R if R else ["# (no R filters)"])
    out.append("")
    return "\n".join(out)
