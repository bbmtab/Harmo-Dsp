"""Output peak meter via Windows audio session API (no recording!).

IAudioMeterInformation on the default render endpoint: OS hands us the
peak directly (Peace-style meter) — no mic capture, negligible CPU.
COM: the enumerator is cached process-lifetime; CoInitialize is NOT
unbalanced against Qt (we keep it, we never CoUninitialize here).
Returns None when unavailable (headless CI, non-Windows).
"""
from __future__ import annotations

_enum = None  # cached IMMDeviceEnumerator (process lifetime)

_CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
_IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE513671B636}"
_IID_IAudioMeterInformation = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"


def _guid(s: str):
    import uuid
    return uuid.UUID(s)


def _get_enum():
    global _enum
    if _enum is not None:
        return _enum
    import ctypes
    ole32 = ctypes.OleDLL("ole32")
    hr = ole32.CoInitializeEx(None, 0x2)  # APARTMENTFLAG; S_FALSE(1) ok if Qt did it
    if hr not in (0, 1):
        return None
    B16 = ctypes.c_ubyte * 16

    class _U(ctypes.Structure):
        _fields_ = [("lpVtbl", ctypes.c_void_p)]

    enum = ctypes.POINTER(_U)()
    ok = ole32.CoCreateInstance(
        B16.from_buffer_copy(_guid(_CLSID_MMDeviceEnumerator).bytes_le),
        None, 23,
        B16.from_buffer_copy(_guid(_IID_IMMDeviceEnumerator).bytes_le),
        ctypes.byref(enum))
    if ok != 0 or not enum:
        return None
    _enum = enum
    return enum


def get_output_peak() -> float | None:
    """Peak 0.0..1.0 of the default playback device, or None."""
    try:
        import ctypes
        enum = _get_enum()
        if enum is None:
            return None
        B16 = ctypes.c_ubyte * 16

        class _U(ctypes.Structure):
            _fields_ = [("lpVtbl", ctypes.c_void_p)]

        vtbl = ctypes.cast(enum.contents.lpVtbl, ctypes.POINTER(ctypes.c_void_p))
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eConsole=0)
        fn_def = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                                    ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(vtbl[4])
        ep = ctypes.c_void_p()
        if fn_def(enum, 0, 0, ctypes.byref(ep)) != 0 or not ep:
            return None
        vtbl2 = ctypes.cast(ep, ctypes.POINTER(ctypes.c_void_p))
        # IMMDevice::Activate(IID_IAudioMeterInformation, CLSCTX_ALL, None, &m)
        fn_act = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.POINTER(B16), ctypes.c_ulong,
                                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vtbl2[3])
        iid = B16.from_buffer_copy(_guid(_IID_IAudioMeterInformation).bytes_le)
        meter = ctypes.c_void_p()
        if fn_act(ep, ctypes.byref(iid), 23, None, ctypes.byref(meter)) != 0 or not meter:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl2[2])(ep)  # Release ep
            return None
        try:
            vtbl3 = ctypes.cast(meter, ctypes.POINTER(ctypes.c_void_p))
            # IAudioMeterInformation::GetPeakValue(float*)
            fn_peak = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_float))(vtbl3[3])
            peak = ctypes.c_float()
            if fn_peak(meter, ctypes.byref(peak)) != 0:
                return None
            return max(0.0, min(1.0, float(peak.value)))
        finally:
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl3[2])(meter)
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl2[2])(ep)
    except Exception:
        return None
