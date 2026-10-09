"""APO semantics: understand config the way the engine applies it.

Original code (MIT). Behavior modelled ONLY on the public Configuration
reference — no APO/Peace source used (clean-room, docs-only).

What it models:
- Channel: scoping (filters apply to selected channels until next Channel:)
- Include: inlining with cycle guard (Peace's peace.txt mechanism)
- Preamp summation per channel (dB sum, >= v0.8)
- Device:/Stage:/If: recorded as gates (opaque, reported not assumed)
- GraphicEQ/Filter gain audit (boost + clipping warnings)

Used by Export -> Verify: shows the EFFECTIVE L/R chain before writing.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field

KNOWN = {"preamp", "filter", "graphiceq", "delay", "copy", "convolution",
         "include", "device", "channel", "stage", "if", "elseif", "else",
         "endif", "eval"}


@dataclass
class Step:
    kind: str
    text: str
    channels: tuple[str, ...] = ("L", "R")
    gate: str = ""  # e.g. "sampleRate == 48000" when inside If


@dataclass
class VerifyResult:
    preamp_db: dict[str, float] = field(default_factory=lambda: {"L": 0.0, "R": 0.0})
    steps: dict[str, list[Step]] = field(default_factory=lambda: {"L": [], "R": []})
    warnings: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)


def _split_cmd(line: str) -> tuple[str, str] | None:
    if ":" not in line:
        return None
    cmd, arg = line.split(":", 1)
    cmd = cmd.strip().lower()
    # "Filter 1:" style numbering
    cmd = re.sub(r"\s+\d+$", "", cmd)
    return cmd, arg.strip()


def parse_apo_text(text: str, base_dir: str = "",
                   _depth: int = 0) -> tuple[list[Step], list[str]]:
    """Parse config text into ordered steps. Returns (steps, warnings)."""
    steps: list[Step] = []
    warnings: list[str] = []
    channels: tuple[str, ...] = ("L", "R")
    gates: list[str] = []
    if _depth > 5:
        return steps, ["Include nesting too deep — stopped resolving."]
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = _split_cmd(line)
        if parsed is None:
            warnings.append(f"Ignored (not Command: params): {line[:60]}")
            continue
        cmd, arg = parsed
        if cmd not in KNOWN:
            warnings.append(f"Unknown command '{cmd}' — APO would silently ignore it.")
            steps.append(Step("unknown", line, channels, " / ".join(gates)))
        elif cmd == "channel":
            channels = tuple(a.upper() for a in arg.split())
            steps.append(Step("channel", line, channels, " / ".join(gates)))
        elif cmd == "include":
            fname = arg.strip("\"'")
            steps.append(Step("include", line, channels, " / ".join(gates)))
            fpath = os.path.join(base_dir, fname) if base_dir else fname
            if os.path.isfile(fpath):
                try:
                    with open(fpath, encoding="utf-8-sig", errors="replace") as fh:
                        sub, w = parse_apo_text(fh.read(),
                                                os.path.dirname(fpath), _depth + 1)
                    # included lines inherit the CURRENT channel scope
                    for s in sub:
                        if s.kind == "channel":
                            channels = s.channels
                        else:
                            s.channels = channels
                    steps.extend(sub)
                    warnings.extend(w)
                except OSError as e:
                    warnings.append(f"Cannot read Include '{fname}': {e}")
            else:
                warnings.append(f"Include target not found: {fname}")
        elif cmd in ("if", "elseif"):
            gates.append(arg) if cmd == "if" else gates.__setitem__(-1, arg)
            steps.append(Step("if", line, channels, " / ".join(gates)))
        elif cmd == "else":
            steps.append(Step("else", line, channels, " / ".join(gates)))
        elif cmd == "endif":
            if gates:
                gates.pop()
            steps.append(Step("endif", line, channels, " / ".join(gates)))
        elif cmd in ("device", "stage", "eval"):
            steps.append(Step("gate", line, channels, " / ".join(gates)))
        else:
            steps.append(Step(cmd, line, channels, " / ".join(gates)))
    return steps, warnings


_GAIN = re.compile(r"gain\s+([+-]?\d+(?:\.\d+)?)\s*db", re.I)
_PRE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*db", re.I)


def verify(text: str, base_dir: str = "") -> VerifyResult:
    """Effective per-channel result + audit warnings (boost/clipping/order)."""
    res = VerifyResult()
    steps, warnings = parse_apo_text(text, base_dir)
    res.warnings.extend(warnings)
    for s in steps:
        for ch in s.channels:
            if ch not in res.steps:
                res.steps[ch] = []
                res.preamp_db[ch] = 0.0
            if s.kind == "preamp":
                m = _PRE.search(s.text.split(":", 1)[1])
                if m:
                    res.preamp_db[ch] += float(m.group(1))
            elif s.kind not in ("include", "channel", "unknown"):
                res.steps[ch].append(s)
    # audit: boost + clipping
    for ch in ("L", "R"):
        boost = 0.0
        for s in res.steps.get(ch, []):
            if s.kind in ("filter", "graphiceq"):
                for m in _GAIN.finditer(s.text):
                    boost = max(boost, float(m.group(1)))
                if s.kind == "graphiceq":
                    pairs = re.findall(r"[;\s]([+-]?\d+(?:\.\d+)?)(?:;|$)", s.text)
                    for p in pairs[1::2]:  # every 2nd number is a gain
                        try:
                            boost = max(boost, float(p))
                        except ValueError:
                            pass
        if boost > 6.0:
            res.warnings.append(
                f"Channel {ch}: max boost +{boost:g} dB exceeds safe +6 dB.")
        if res.preamp_db.get(ch, 0.0) + 0 < 0 and boost + res.preamp_db.get(ch, 0.0) > 0.01:
            res.warnings.append(
                f"Channel {ch}: preamp {res.preamp_db[ch]:g} dB may not cover "
                f"+{boost:g} dB boost — clipping risk.")
    # order: our file should come after peace.txt
    texts = [s.text.lower() for s in steps if s.kind == "include"]
    peace_i = next((i for i, t in enumerate(texts) if "peace.txt" in t), None)
    ours_i = next((i for i, t in enumerate(texts) if "speakercorrect" in t), None)
    if peace_i is not None and ours_i is not None and ours_i < peace_i:
        res.warnings.append(
            "Order: speakercorrect is Included BEFORE peace.txt — "
            "Peace filters will apply last. Move ours after peace.txt.")
    return res


def detect_peace(config_text: str) -> dict:
    """Peace coexistence facts (verified: Peace overwrites config.txt when its
    Include line is missing — SourceForge forum, Peace project)."""
    low = config_text.lower()
    return {
        "peace_installed": "peace.txt" in low,
        "ours_present": "speakercorrect" in low,
    }
