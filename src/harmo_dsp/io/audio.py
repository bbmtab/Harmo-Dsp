"""Audio hardware access for guided measurement.

Primary backend: PyAudioWPatch (WASAPI via PortAudio) — PROVEN on the
author's machine where the COM meter class is refused (loopback capture
returned real audio peaks). Fallback: sounddevice (same PortAudio family)
when pyaudiowpatch is absent. Missing both => UI shows an install hint.

All streams open with the device's FULL channel need (mono out, mono in
at 48 kHz; WASAPI shared mode converts rates). Everything stays local.
"""
from __future__ import annotations
import time

import numpy as np


def _has_pw() -> bool:
    try:
        import pyaudiowpatch  # noqa
        return True
    except ImportError:
        return False


def _has_sd() -> bool:
    try:
        import sounddevice  # noqa
        return True
    except ImportError:
        return False


def available() -> bool:
    return _has_pw() or _has_sd()


def devices() -> tuple[list[str], list[str]]:
    """(outputs, inputs) as 'index: name'. Empty when backend missing."""
    if _has_pw():
        import pyaudiowpatch as pw
        pa = pw.PyAudio()
        outs, ins = [], []
        try:
            for i in range(pa.get_device_count()):
                d = pa.get_device_info_by_index(i)
                if d.get("isLoopbackDevice"):
                    continue  # meter twins, not for measurement
                label = f"{i}: {d['name']}"
                if d["maxOutputChannels"] > 0:
                    outs.append(label)
                if d["maxInputChannels"] > 0:
                    ins.append(label)
        finally:
            pa.terminate()
        return outs, ins
    if _has_sd():
        import sounddevice as sd
        outs, ins = [], []
        for i, d in enumerate(sd.query_devices()):
            label = f"{i}: {d['name']}"
            if d["max_output_channels"] > 0:
                outs.append(label)
            if d["max_input_channels"] > 0:
                ins.append(label)
        return outs, ins
    return [], []


def pick_measurement_mic(inputs: list[str]) -> str | None:
    """Best measurement mic heuristic: calibrated UMIK-1 first, then any
    USB mic, then any microphone. Returns the label or None."""
    for kw in (("umik",), ("usb", "microphone"), ("usb",), ("microphone",)):
        for lb in inputs:
            if all(k in lb.lower() for k in kw):
                return lb
    return None


def pick_measurement_out(outputs: list[str]) -> str | None:
    """Best output heuristic: user rig = Realtek Digital, then digital/USB."""
    for kw in (("digital", "realtek"), ("digital",), ("usb", "speakers")):
        for lb in outputs:
            if all(k in lb.lower() for k in kw):
                return lb
    return None


def _idx(label: str) -> int | None:
    try:
        return int(label.split(":", 1)[0])
    except (ValueError, IndexError):
        return None


def play_rec(sweep: np.ndarray, fs: int, out: str, inp: str,
             seconds: float) -> np.ndarray:
    """Play sweep on `out` while recording `inp`. Blocking (v1, GUI pauses)."""
    if _has_pw():
        return _pw_play_rec(sweep, fs, out, inp, seconds)
    return _sd_play_rec(sweep, fs, out, inp, seconds)


def _pw_play_rec(sweep, fs, out, inp, seconds):
    import pyaudiowpatch as pw
    oi, ii = _idx(out), _idx(inp)
    if oi is None or ii is None:
        raise ValueError("Pick output AND input devices first.")
    pa = pw.PyAudio()
    sw = np.ascontiguousarray(np.asarray(sweep, dtype=np.float32))
    pos = [0]
    finished = [False]
    buf: list[np.ndarray] = []

    def out_cb(_in, frames, _t, _st):
        chunk = sw[pos[0]:pos[0] + frames]
        pos[0] += len(chunk)
        if len(chunk) < frames:
            chunk = np.pad(chunk, (0, frames - len(chunk)))
            finished[0] = True
        return (chunk.tobytes(), pw.paContinue)

    def in_cb(in_data, frames, _t, _st):
        buf.append(np.frombuffer(in_data, dtype=np.float32).copy())
        return (in_data, pw.paContinue)

    ostream = pa.open(format=pw.paFloat32, channels=1, rate=fs,
                      output=True, output_device_index=oi,
                      stream_callback=out_cb)
    istream = pa.open(format=pw.paFloat32, channels=1, rate=fs,
                      input=True, input_device_index=ii,
                      stream_callback=in_cb)
    istream.start_stream()
    ostream.start_stream()
    t0 = time.monotonic()
    while not finished[0] and time.monotonic() - t0 < seconds + 10.0:
        time.sleep(0.05)
    time.sleep(0.25)  # capture tail (room decay)
    istream.stop_stream(); istream.close()
    ostream.stop_stream(); ostream.close()
    pa.terminate()
    x = np.concatenate(buf).astype(np.float64) if buf else np.zeros(0)
    want = int(seconds * fs)
    return x[:want] if len(x) >= want else np.pad(x, (0, want - len(x)))


def _sd_play_rec(sweep, fs, out, inp, seconds):
    import sounddevice as sd
    oi, ii = _idx(out), _idx(inp)
    rec = sd.playrec(np.asarray(sweep, dtype=np.float32), samplerate=fs,
                     input_device=ii, output_device=oi, channels=1,
                     blocking=True)
    want = int(seconds * fs)
    x = np.asarray(rec[:, 0], dtype=np.float64)
    return x[:want] if len(x) >= want else np.pad(x, (0, want - len(x)))


def record_only(fs: int, inp: str, seconds: float) -> np.ndarray:
    """Record from `inp` for level checks. Blocking."""
    if _has_pw():
        import pyaudiowpatch as pw
        ii = _idx(inp)
        if ii is None:
            raise ValueError("Pick an input device first.")
        pa = pw.PyAudio()
        buf: list[np.ndarray] = []

        def in_cb(in_data, frames, _t, _st):
            buf.append(np.frombuffer(in_data, dtype=np.float32).copy())
            return (in_data, pw.paContinue)

        st = pa.open(format=pw.paFloat32, channels=1, rate=fs,
                     input=True, input_device_index=ii,
                     stream_callback=in_cb)
        st.start_stream()
        time.sleep(seconds)
        st.stop_stream(); st.close()
        pa.terminate()
        x = np.concatenate(buf).astype(np.float64) if buf else np.zeros(0)
        want = int(seconds * fs)
        return x[:want] if len(x) >= want else np.pad(x, (0, want - len(x)))
    import sounddevice as sd
    rec = sd.rec(int(seconds * fs), samplerate=fs, channels=1,
                 device=_idx(inp), blocking=True)
    return np.asarray(rec[:, 0], dtype=np.float64)
