"""Importers for REW filter-settings and Peace preset files.

Legal: both are the USER'S OWN files. Parsers are original code written
from observed files (see docs/ASSUMPTIONS.md). No REW/Peace code used.
"""
from __future__ import annotations
import math
import re

from ..dsp.peq import PeqBand, _TYPE

_FILTER_LINE = re.compile(
    r"filter\s+\d+\s*:\s*(ON|OFF)\s+([A-Z0-9 ]+?)\s+Fc\s+([0-9.,]+)\s*Hz"
    r"(?:\s+Gain\s+([+-]?[0-9.,]+)\s*dB)?"
    r"(?:\s+(?:Q\s+([0-9.,]+)|BW\s*Oct\s+([0-9.,]+)))?",
    re.I)


def _num(tok: str) -> float | None:
    tok = tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return None


def bw_oct_to_q(bw: float) -> float:
    """Constant-Q conversion (standard textbook formula)."""
    return 1.0 / (2.0 * math.sinh(math.log(2.0) / 2.0 * max(bw, 1e-3)))


def parse_rew_filter_settings(text: str) -> tuple[list[PeqBand], list[str]]:
    """Parse REW 'Filter Settings file' (Generic/FBQ2496 EQ types).

    Returns (bands, notes). Unknown types are skipped with a note.
    """
    bands: list[PeqBand] = []
    notes: list[str] = []
    for raw in text.splitlines():
        m = _FILTER_LINE.search(raw)
        if not m:
            continue
        on, ftype, fc_t, gain_t, q_t, bw_t = m.groups()
        ftype = " ".join(ftype.split()).upper()
        if ftype == "PEQ":
            ftype = "PK"
        fc = _num(fc_t)
        if fc is None:
            continue
        gain = _num(gain_t) if gain_t else 0.0
        if q_t:
            q = _num(q_t) or 1.0
        elif bw_t and (bw := _num(bw_t)):
            q = bw_oct_to_q(bw)
            notes.append(f"BW Oct {bw:g} -> Q {q:.2f}")
        else:
            q = 1.0
        if ftype not in _TYPE:
            notes.append(f"Skipped unsupported type {ftype!r} @{fc:g}Hz")
            continue
        bands.append(PeqBand(on.upper() == "ON", ftype, fc, gain or 0.0, q))
    if not bands:
        raise ValueError("No REW filter lines found — export 'Filter Settings as text' from REW")
    return bands, notes


def parse_peace_preset(text: str) -> dict:
    """Parse Peace settings (.peace INI): base [Frequencies]/[Gains]/
    [Qualities] (+[General] PreAmp). All filters are Peak type.

    Returns {"preamp": float, "bands": [(fc, gain, q)], "speakers": {...}}.
    """
    secs: dict[str, dict[str, str]] = {}
    cur = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            secs.setdefault(cur, {})
        elif "=" in line and cur:
            k, v = line.split("=", 1)
            secs[cur][k.strip()] = v.strip()
    preamp = 0.0
    try:
        preamp = float(secs.get("General", {}).get("PreAmp", 0.0))
    except ValueError:
        pass
    freq = secs.get("Frequencies", {})
    gains = secs.get("Gains", {})
    quals = secs.get("Qualities", {})
    n = max([int(re.sub(r"\D", "", k) or 0) for k in
             list(freq) + list(gains) + list(quals)] + [0])
    bands = []
    for i in range(1, n + 1):
        f = freq.get(f"Frequency{i}")
        if f is None:
            continue
        try:
            bands.append((float(f),
                          float(gains.get(f"Gain{i}", 0.0)),
                          float(quals.get(f"Quality{i}", 1.0))))
        except ValueError:
            continue
    speakers = {}
    for k, v in secs.get("Speakers", {}).items():
        m = re.match(r"Speaker(Name|Targets)(\d+)", k)
        if m:
            speakers.setdefault(m.group(2), {})[m.group(1).lower()] = v
    return {"preamp": preamp, "bands": bands, "speakers": speakers}
