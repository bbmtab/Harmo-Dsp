"""Output peak meter backends (no mic, no disk — level read-back only).

Order: (1) IAudioMeterInformation COM (normal Windows sessions, zero-copy);
(2) PyAudioWPatch WASAPI loopback capture (MIT fork of PyAudio) — the
WORKING path on machines where the COM class is refused (verified on the
author's box: COM 0x80040154, loopback peaks real audio). Loopback opens
the FULL channel count (maxInputChannels) — ch=1 gets PaInvalidDevice.
All processing local; nothing is stored or transmitted.
"""
from __future__ import annotations

_backend = None  # cached _LoopbackMeter (process lifetime)
_com_ok: bool | None = None  # None=untested, True/False after first try

_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE513671B636}"
_IID_IAudioMeterInformation = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"


def _guid(s: str):
    import uuid
    return uuid.UUID(s)


def _com_peak() -> float | None:
    """IAudioMeterInformation::GetPeakValue on the default render device."""
    global _com_ok
    if _com_ok is False:
        return None
    try:
        import ctypes
        ole32 = ctypes.OleDLL("ole32")
        if ole32.CoInitializeEx(None, 0x2) not in (0, 1):
            _com_ok = False
            return None
        B16 = ctypes.c_ubyte * 16

        class _U(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.c_void_p)]

        enum = ctypes.POINTER(_U)()
        if ole32.CoCreateInstance(
                B16.from_buffer_copy(_guid(_CLSID_MMDeviceEnumerator).bytes_le),
                None, 23,
                B16.from_buffer_copy(_guid(_IID_IMMDeviceEnumerator).bytes_le),
                ctypes.byref(enum)) != 0 or not enum:
            _com_ok = False  # e.g. 0x80040154 on restricted sessions
            return None
        vtbl = ctypes.cast(enum.contents.lpVtbl, ctypes.POINTER(ctypes.c_void_p))
        ep = ctypes.c_void_p()
        fn_def = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                                    ctypes.c_int,
                                    ctypes.POINTER(ctypes.c_void_p))(vtbl[4])
        if fn_def(enum, 0, 0, ctypes.byref(ep)) != 0 or not ep:
            return None
        vtbl2 = ctypes.cast(ep, ctypes.POINTER(ctypes.c_void_p))
        fn_act = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.POINTER(B16), ctypes.c_ulong,
                                    ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_void_p))(vtbl2[3])
        iid = B16.from_buffer_copy(_guid(_IID_IAudioMeterInformation).bytes_le)
        meter = ctypes.c_void_p()
        if fn_act(ep, ctypes.byref(iid), 23, None, ctypes.byref(meter)) != 0 \
                or not meter:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl2[2])(ep)
            return None
        try:
            vtbl3 = ctypes.cast(meter, ctypes.POINTER(ctypes.c_void_p))
            fn_peak = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                         ctypes.POINTER(ctypes.c_float))(vtbl3[3])
            peak = ctypes.c_float()
            if fn_peak(meter, ctypes.byref(peak)) != 0:
                return None
            v = max(0.0, min(1.0, float(peak.value)))
            _com_ok = True
            return v
        finally:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl3[2])(meter)
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl2[2])(ep)
    except Exception:
        _com_ok = False
        return None


class _LoopbackMeter:
    """WASAPI loopback of the DEFAULT OUTPUT (PyAudioWPatch, MIT).

    Opens the loopback twin of the default render endpoint with its FULL
    channel count; callback keeps the max |sample|; read() drains it.
    """

    def __init__(self):
        import numpy as np
        import pyaudiowpatch as pw
        self._np = np
        self._pw = pw
        self.pa = pw.PyAudio()
        lb = self.pa.get_default_wasapi_loopback()
        self.peak = 0.0

        def cb(in_data, frame_count, time_info, status):
            x = np.frombuffer(in_data, dtype=np.float32)
            if x.size:
                p = float(np.abs(x).max())
                if p > self.peak:
                    self.peak = p
            return (in_data, pw.paContinue)

        self.stream = self.pa.open(
            format=pw.paFloat32, channels=int(lb["maxInputChannels"]),
            rate=int(lb["defaultSampleRate"]), input=True,
            input_device_index=int(lb["index"]), stream_callback=cb)
        self.stream.start_stream()

    def read(self) -> float:
        p = self.peak
        self.peak = 0.0
        return p

    def close(self):
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception:
            pass
        try:
            self.pa.terminate()
        except Exception:
            pass


def _close_backend():
    global _backend
    if _backend is not None:
        try:
            _backend.close()
        except Exception:
            pass
        _backend = None


def get_output_peak() -> float | None:
    """Peak 0.0..1.0 of the default playback device, or None if unavailable.

    Returns 0.0 when the backend is alive but everything is silent —
    callers can distinguish 'meter working, silence' from 'no meter'.
    """
    global _backend
    v = _com_peak()
    if v is not None:
        _close_backend()  # COM works: no need for the capture fallback
        return v
    try:
        if _backend is None:
            _backend = _LoopbackMeter()
        return _backend.read()
    except Exception:
        _close_backend()  # dead stream (device switch?) — re-init next poll
        return None
