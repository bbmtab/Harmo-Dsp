"""APO device attach: enumerate + plan (read-only). Writes live ONLY in
tools/attach_apo.py (elevated helper, user consents via UAC).

Provenance (interface FACTS from GPL sources, implementation original):
- Equalizer APO repo (SourceForge, Jonas Thedering, GPL-2.0), read-only:
  DeviceAPOInfo.cpp (slots, SFX/EFX procedure, backup, child APOs),
  helpers/RegistryHelper.h (PRE/POST mix GUIDs, APP_REGPATH).
  Observed locally: Configurator backup_*.reg files (slot pattern),
  FxProperties layout, APO install dir.
- Our code never copies GPL source; procedure reimplemented in Python.
- Registry facts used: PKEY slot names {d04e05a6-...},1/2/5/6/7,
  processing-mode {d3993a3f-...},5/6/7 + default {C18E2F7E-...},
  device PKEYs {a45c254e-...},2 (connection) / {b3f8fa53-...},6 (device),
  Child APOs under HKLM\\SOFTWARE\\EqualizerAPO.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# Interface facts (see module docstring for provenance).
PRE_MIX = "{EACD2258-FCAC-4FF4-B36D-419E924A6D79}"
POST_MIX = "{EC1CC9CE-FAED-4822-828A-82A81A6F018F}"
APO_GUIDS = (PRE_MIX, POST_MIX)
SLOTS = {"LFX": 1, "GFX": 2, "SFX": 5, "MFX": 6, "EFX": 7}
SLOT_PKEY = "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d}"
PROC_PKEY = "{d3993a3f-99c2-4402-b5ec-a92a0367664b}"
PROC_DEFAULT = "{C18E2F7E-933D-4965-B7D1-1EEF228D2AF3}"
DISABLE_ENH = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
CHILD_BASE = r"SOFTWARE\EqualizerAPO\Child APOs"


def _slot_name(idx: int) -> str:
    return f"{SLOT_PKEY},{idx}"


@dataclass
class AudioDevice:
    guid: str
    name: str
    attached: bool = False
    is_default: bool = False
    disabled: bool = False
    originals: dict[str, str | None] = field(default_factory=dict)


def _read_reg_str(root, path: str, name: str) -> str | None:
    try:
        import winreg
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, name)
            return str(val)
    except OSError:
        return None


def enumerate_devices() -> list[AudioDevice]:
    """Render endpoints from the registry (read-only, no admin needed)."""
    try:
        import winreg
    except ImportError:
        return []  # non-Windows: guarded by callers
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
    devs: list[AudioDevice] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0,
                             winreg.KEY_READ) as root:
            guids = [winreg.EnumKey(root, i)
                     for i in range(winreg.QueryInfoKey(root)[0])]
    except OSError:
        return []
    for g in guids:
        props = base + "\\" + g + "\\Properties"
        fx = base + "\\" + g + "\\FxProperties"
        conn = _read_reg_str(winreg.HKEY_LOCAL_MACHINE, props,
                             "{a45c254e-df1c-4efd-8020-67d146a850e0},2") or ""
        dev = _read_reg_str(winreg.HKEY_LOCAL_MACHINE, props,
                            "{b3f8fa53-0004-438e-9003-51a46e139bfc},6") or ""
        name = f"{dev} ({conn})" if (dev and conn) else (dev or conn or g)
        originals: dict[str, str | None] = {}
        attached = False
        for slot, idx in SLOTS.items():
            v = _read_reg_str(winreg.HKEY_LOCAL_MACHINE, fx, _slot_name(idx))
            originals[slot] = v
            if v and v.upper() in APO_GUIDS:
                attached = True
        devs.append(AudioDevice(g, name, attached, False, False, originals))
    default = default_device_guid()
    for d in devs:
        d.is_default = (d.guid.upper() == default.upper()) if default else False
    return devs


def default_device_guid() -> str:
    """Default render endpoint via MMDevice API (best effort, ctypes only)."""
    try:
        import ctypes
        from ctypes import wintypes
        ole32 = ctypes.OleDLL("ole32")
        ole32.CoInitialize(None)
        try:
            # CLSID_MMDeviceEnumerator + IMMDeviceEnumerator::GetDefaultAudioEndpoint
            import uuid
            # Documented Microsoft constants (MMDevice API, MSDN).
            clsid = uuid.UUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            iid_enum = uuid.UUID("{A95664D2-9614-4F35-A746-DE513671B636}")
            # Minimal COM:vtbl call GetDefaultAudioEndpoint(eRender=0, eConsole=0)
            class _E(ctypes.Structure):
                _fields_ = [("lpVtbl", ctypes.c_void_p)]
            enum = ctypes.POINTER(_E)()
            hr = ole32.CoCreateInstance(
                (ctypes.c_ubyte * 16).from_buffer_copy(clsid.bytes_le), None, 21,
                (ctypes.c_ubyte * 16).from_buffer_copy(iid_enum.bytes_le),
                ctypes.byref(enum))
            if hr != 0 or not enum:
                return ""
            vtbl = ctypes.cast(enum.contents.lpVtbl, ctypes.POINTER(ctypes.c_void_p))
            fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                    ctypes.c_int, ctypes.c_int,
                                    ctypes.POINTER(ctypes.c_void_p))(vtbl[4])
            ep = ctypes.c_void_p()
            if fn(enum, 0, 0, ctypes.byref(ep)) != 0 or not ep:
                return ""
            # IMMDevice::GetId is vtbl slot 5
            vtbl2 = ctypes.cast(ep, ctypes.POINTER(ctypes.c_void_p))
            fn2 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                     ctypes.POINTER(wintypes.LPWSTR))(vtbl2[5])
            s = wintypes.LPWSTR()
            guid = ""
            if fn2(ep, ctypes.byref(s)) == 0 and s:
                m = __import__("re").search(
                    r"\{[0-9A-Fa-f-]{36}\}", s.value or "")
                guid = m.group(0) if m else ""
                ole32.CoTaskMemFree(s)
            return guid
        finally:
            ole32.CoUninitialize()
    except Exception:
        return ""


def compute_attach_plan(originals: dict[str, str | None],
                        proc_modes: dict[str, list[str]],
                        use_original: bool = True) -> dict:
    """Pure function: SFX/EFX install plan (official default for Win10/11).

    Returns writes/deletes/backup — applied ONLY by the elevated helper.
    Original vendor APOs are preserved as child APOs (keep working).
    """
    def norm(v):
        return (v or "").upper()
    pre_src = originals.get("SFX") or originals.get("LFX")
    post_src = originals.get("EFX") or originals.get("GFX")
    if pre_src and norm(pre_src) in APO_GUIDS:
        pre_src = None
    if post_src and norm(post_src) in APO_GUIDS:
        post_src = None
    plan = {
        "writes_fx": {_slot_name(SLOTS["SFX"]): PRE_MIX,
                      _slot_name(SLOTS["EFX"]): POST_MIX},
        "deletes_fx": [_slot_name(SLOTS["LFX"]), _slot_name(SLOTS["GFX"])],
        "ensure_proc_modes": {},
        "child_backup": {s: (originals.get(s) or "!VALUE") for s in SLOTS},
        "child_pre": pre_src if use_original else "",
        "child_post": post_src if use_original else "",
        "delete_disable_enhancements": True,
        "version": "2",
    }
    for slot, pidx in (("SFX", 5), ("EFX", 7)):
        key = f"{PROC_PKEY},{pidx}"
        if PROC_DEFAULT not in (proc_modes.get(key) or []):
            plan["ensure_proc_modes"][key] = [PROC_DEFAULT]
    return plan


def compute_detach_plan(child_backup: dict[str, str | None]) -> dict:
    """Pure function: restore originals (official uninstall mirror)."""
    writes, deletes = {}, []
    for slot in SLOTS:
        v = child_backup.get(slot)
        if v in (None, "!VALUE"):
            deletes.append(_slot_name(SLOTS[slot]))
        elif v == "!KEY":
            deletes.append(_slot_name(SLOTS[slot]))
        elif v:
            writes[_slot_name(SLOTS[slot])] = v
    return {"writes_fx": writes, "deletes_fx": deletes}


def reg_backup_text(device_guid: str, slots: dict[str, str | None]) -> str:
    """Classic .reg backup of current FxProperties (official-style)."""
    lines = ["Windows Registry Editor Version 5.00", "",
             f"[HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows"
             f"\\CurrentVersion\\MMDevices\\Audio\\Render"
             f"\\{device_guid}\\FxProperties]"]
    for slot in ("LFX", "GFX", "SFX", "MFX", "EFX"):
        v = slots.get(slot)
        if v:
            lines.append(f'"{_slot_name(SLOTS[slot])}"="{v}"')
    return "\r\n".join(lines) + "\r\n"
