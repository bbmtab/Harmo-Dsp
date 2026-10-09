"""Output peak meter via Windows audio session API (no recording!).

Uses IAudioMeterInformation on the default render endpoint: the OS hands us
peak levels directly (like Peace's meters) — no microphone capture, no
privacy issue, negligible CPU. Returns None when unavailable (headless CI).
"""
from __future__ import annotations


def get_output_peak() -> float | None:
    """Peak 0.0..1.0 of the default playback device, or None."""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid
    except Exception:
        return None
    try:
        ole32 = ctypes.OleDLL("ole32")
        if ole32.CoInitialize(None) not in (0, 1):
            return None
        try:
            clsid = uuid.UUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            iid_enum = uuid.UUID("{A95664D2-9614-4F35-A746-DE513671B636}")
            iid_meter = uuid.UUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
            B16 = ctypes.c_ubyte * 16

            class _U(ctypes.Structure):
                _fields_ = [("lpVtbl", ctypes.c_void_p)]

            enum = ctypes.POINTER(_U)()
            hr = ole32.CoCreateInstance(
                B16.from_buffer_copy(clsid.bytes_le), None, 23,
                B16.from_buffer_copy(iid_enum.bytes_le), ctypes.byref(enum))
            if hr != 0 or not enum:
                return None
            try:
                vtbl = ctypes.cast(enum.contents.lpVtbl,
                                   ctypes.POINTER(ctypes.c_void_p))
                fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_int,
                                        ctypes.POINTER(ctypes.c_void_p))(vtbl[4])
                ep = ctypes.c_void_p()
                if fn(enum, 0, 0, ctypes.byref(ep)) != 0 or not ep:
                    return None
                try:
                    vtbl2 = ctypes.cast(ep, ctypes.POINTER(ctypes.c_void_p))
                    fn2 = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p,
                        ctypes.POINTER(B16),
                        ctypes.c_ulong, ctypes.c_void_p,
                        ctypes.POINTER(ctypes.c_void_p))(vtbl2[3])
                    iidm = B16.from_buffer_copy(iid_meter.bytes_le)
                    meter = ctypes.c_void_p()
                    if fn2(ep, ctypes.byref(iidm), 23, None,
                           ctypes.byref(meter)) != 0 or not meter:
                        return None
                    try:
                        vtbl3 = ctypes.cast(meter,
                                            ctypes.POINTER(ctypes.c_void_p))
                        fn3 = ctypes.WINFUNCTYPE(
                            ctypes.c_long, ctypes.c_void_p,
                            ctypes.POINTER(ctypes.c_float))(vtbl3[3])
                        peak = ctypes.c_float()
                        if fn3(meter, ctypes.byref(peak)) != 0:
                            return None
                        v = float(peak.value)
                        return max(0.0, min(1.0, v))
                    finally:
                        rel = ctypes.WINFUNCTYPE(ctypes.c_ulong,
                                                 ctypes.c_void_p)(vtbl3[2])
                        rel(meter)
                finally:
                    rel = ctypes.WINFUNCTYPE(ctypes.c_ulong,
                                             ctypes.c_void_p)(vtbl2[2])
                    rel(ep)
            finally:
                rel = ctypes.WINFUNCTYPE(ctypes.c_ulong,
                                         ctypes.c_void_p)(
                    ctypes.cast(enum.contents.lpVtbl,
                                ctypes.POINTER(ctypes.c_void_p))[2])
                rel(enum)
        finally:
            ole32.CoUninitialize()
    except Exception:
        return None
    return None
