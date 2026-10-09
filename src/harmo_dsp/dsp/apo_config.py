"""Full APO output builder: every documented command group we support.

Covers the Configuration reference (Equalizer APO, Jonas Thedering):
  Preamp, Filter (all 17 types), Delay, GraphicEQ, Convolution,
  Include-safe layout, Device gate, Stage, If sampleRate wrapper.

Copy/VST/anything else: via custom_header/custom_footer verbatim lines
(documented escape hatch — APO ignores unknown lines silently, and our
verifier reports them instead of dropping them quietly).

Only documented *syntax* is mirrored; all code is original (MIT).
"""
from __future__ import annotations
from dataclasses import dataclass, field

from .peq import PeqBand, band_to_line
from .geq import to_apo_graphic_eq

OUR_FILENAME = "speakercorrect.txt"


@dataclass
class ApoOutput:
    preamp_db: float = 0.0
    device_pattern: str = ""          # "" = all devices (Peace per-device profiles)
    stage: str = ""                   # "" | "pre-mix" | "post-mix"
    bands: list[PeqBand] = field(default_factory=list)
    graphic_l: list[float] | None = None
    graphic_r: list[float] | None = None
    delay_ms: dict[str, float] = field(default_factory=lambda: {"L": 0.0, "R": 0.0})
    convolution: dict[int, str] = field(default_factory=dict)  # {sampleRate: path}
    convolution_ch: str = "both"  # both | L | R (manual single-file path)
    conv_per_ch: dict[str, dict[int, str]] = field(default_factory=dict)  # per-channel FIR
    custom_header: str = ""
    custom_footer: str = ""


def _conv_block(files: dict[int, str]) -> list[str]:
    """Sample-rate-aware Convolution (APO requires file rate == device rate)."""
    if not files:
        return []
    if len(files) == 1:
        ((_, path),) = files.items()
        return [f"Convolution: {path}"]
    keys = sorted(files)
    lines = [f"If: sampleRate == {keys[0]}"]
    lines.append(f"  Convolution: {files[keys[0]]}")
    for k in keys[1:-1]:
        lines.append(f"ElseIf: sampleRate == {k}")
        lines.append(f"  Convolution: {files[k]}")
    if len(keys) > 1:
        lines.append("Else:")
        lines.append(f"  Convolution: {files[keys[-1]]}")
        lines.append("EndIf:")
    return lines


def render_speakercorrect(o: ApoOutput) -> str:
    """Assemble the complete speakercorrect.txt (per-channel blocks)."""
    out = [
        "# speakercorrect.txt — written by Harmo-Dsp (MIT, original code).",
        "# Syntax follows the Equalizer APO Configuration reference",
        "# (SourceForge wiki, Jonas Thedering). Order matters:",
        "# APO processes lines top to bottom.",
        "# Peace coexistence: keep 'Include: speakercorrect.txt' in",
        "# config.txt AFTER the peace.txt Include line.",
    ]
    if o.custom_header.strip():
        out += ["", "# --- custom header (verbatim, advanced) ---",
                o.custom_header.strip()]
    if o.device_pattern.strip():
        out += ["", f"# Device profile gate (Peace-style per-device)",
                f"Device: {o.device_pattern.strip()}"]
    if o.stage in ("pre-mix", "post-mix"):
        out += ["", f"Stage: {o.stage}"]
    out += ["", f"Preamp: {o.preamp_db:g} dB", ""]

    conv = _conv_block(o.convolution)
    for scope in ("L", "R"):
        out.append(f"Channel: {scope}")
        d = float(o.delay_ms.get(scope, 0.0) or 0.0)
        if d > 0:
            out.append(f"Delay: {d:g} ms  # time-align (1 ms ~= 34 cm)")
        g = o.graphic_l if scope == "L" else o.graphic_r
        if g and any(v != 0 for v in g):
            out.append(to_apo_graphic_eq(g))
        for b in o.bands:
            if b.channel not in ("all", scope):
                continue
            line = band_to_line(b)
            if line is not None:
                out.append(line)
        per_ch = o.conv_per_ch.get(scope)
        if per_ch:
            out.extend(_conv_block(per_ch))  # per-channel FIR wins
        elif o.convolution_ch in ("both", scope):
            out.extend(conv)
        out.append("")
    if o.custom_footer.strip():
        out += ["# --- custom footer (verbatim: Copy/VST/anything) ---",
                o.custom_footer.strip(), ""]
    return "\n".join(out)
