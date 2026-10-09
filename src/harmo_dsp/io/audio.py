"""Audio hardware access (optional). sounddevice missing => guided
measurement UI shows an install hint; everything else keeps working."""
from __future__ import annotations
import numpy as np


def available() -> bool:
    try:
        import sounddevice  # noqa
        return True
    except ImportError:
        return False


def devices() -> tuple[list[str], list[str]]:
    """(outputs, inputs) as 'index: name'. Empty when backend missing."""
    if not available():
        return [], []
    import sounddevice as sd
    outs, ins = [], []
    for i, d in enumerate(sd.query_devices()):
        label = f"{i}: {d['name']}"
        if d["max_output_channels"] > 0:
            outs.append(label)
        if d["max_input_channels"] > 0:
            ins.append(label)
    return outs, ins


def _idx(label: str) -> int | None:
    try:
        return int(label.split(":", 1)[0])
    except (ValueError, IndexError):
        return None


def play_rec(sweep: np.ndarray, fs: int, out: str, inp: str,
             seconds: float) -> np.ndarray:
    """Play sweep on `out` while recording `inp`. Blocking (v1)."""
    import sounddevice as sd
    oi, ii = _idx(out), _idx(inp)
    rec = sd.playrec(sweep.astype(np.float32), samplerate=fs,
                     input_device=ii, output_device=oi, channels=1,
                     blocking=True)
    want = int(seconds * fs)
    x = np.asarray(rec[:, 0], dtype=np.float64)
    return x[:want] if len(x) >= want else np.pad(x, (0, want - len(x)))


def record_only(fs: int, inp: str, seconds: float) -> np.ndarray:
    import sounddevice as sd
    rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1,
                 device=_idx(inp), blocking=True)
    return np.asarray(rec[:, 0], dtype=np.float64)
