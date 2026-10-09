"""Tolerant REW frequency-response text importer (.txt / .frd).

Handles: space/tab/comma/semicolon separators, dot or comma decimals,
header/comment lines, optional phase column. Never guesses binary formats.
"""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class Measurement:
    frequencies: list[float]
    spl: list[float]
    phase: list[float] | None
    name: str

    def __len__(self) -> int:
        return len(self.frequencies)


_WS_SEP = re.compile(r"[;\t\s]+")


def _split_row(line: str) -> list[str]:
    """Split a data row, tolerating decimal commas ('20,5' -> '20.5')."""
    chunks = [c for c in _WS_SEP.split(line) if c != ""]
    out: list[str] = []
    for ch in chunks:
        if "," not in ch:
            out.append(ch)
            continue
        # single comma, no dot, digits both sides -> decimal comma
        if ch.count(",") == 1 and "." not in ch:
            left, right = ch.split(",", 1)
            if left.strip("-+").isdigit() and right.isdigit():
                out.append(f"{left}.{right}")
                continue
        # otherwise comma is a separator
        out.extend(p for p in ch.split(",") if p != "")
    return out


def _to_float(tok: str) -> float | None:
    tok = tok.strip()
    if not tok:
        return None
    # tolerate decimal comma: "12,5" -> 12.5, but not thousand separators
    if "," in tok and "." not in tok:
        tok = tok.replace(",", ".")
    else:
        tok = tok.replace(",", "")
    try:
        return float(tok)
    except ValueError:
        return None


def parse_rew_text(text: str, name: str = "meas") -> Measurement:
    freqs: list[float] = []
    spl: list[float] = []
    phase: list[float] = []
    has_phase = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("*", "#", '"', "'")):
            continue
        # skip lines starting with a letter (headers like "Freq SPL Phase")
        if line[0].isalpha():
            continue
        parts = _split_row(line)
        if len(parts) < 2:
            continue
        f = _to_float(parts[0])
        s = _to_float(parts[1])
        if f is None or s is None or f <= 0:
            continue
        freqs.append(f)
        spl.append(s)
        if len(parts) >= 3:
            ph = _to_float(parts[2])
            if ph is not None:
                phase.append(ph)
                has_phase = True
                continue
        phase.append(0.0)
    if not freqs:
        raise ValueError(f"No data rows found in {name!r} — export REW as .txt/.frd first")
    return Measurement(freqs, spl, phase if has_phase else None, name)


def load_rew_file(path: str) -> Measurement:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        return parse_rew_text(fh.read(), name=path)
