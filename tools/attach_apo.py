"""Elevated APO attach/detach helper (run via UAC "runas", user consents).

Registry WRITES happen ONLY here — never in the MIT GUI core. Procedure mirrors
the official Configurator (GPL, SourceForge; facts documented in
docs/ASSUMPTIONS.md + dsp/apo_attach.py docstring). Original vendor APOs are
backed up first (registry Child APOs + .reg file, official-style).
After attach: REBOOT (like the official tool).

Usage (admin):  python tools/attach_apo.py --list
                python tools/attach_apo.py --attach {device-guid}
                python tools/attach_apo.py --detach {device-guid}
"""
import argparse
import ctypes
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from harmo_dsp.dsp import apo_attach as A  # noqa: E402 (pure stdlib part only)

try:
    import winreg
except ImportError:
    print(json.dumps({"ok": False, "error": "Windows only"}))
    sys.exit(2)

RENDER = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> None:
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join([f'"{a}"' for a in [os.path.abspath(__file__), *sys.argv[1:]]]),
        None, 1)
    sys.exit(0)


def _open_fx(guid, write=False):
    access = winreg.KEY_WRITE if write else winreg.KEY_READ
    return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                          f"{RENDER}\\{guid}\\FxProperties", 0, access)


def read_state(guid):
    try:
        with _open_fx(guid) as k:
            vals = {}
            i = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                    vals[name] = val if isinstance(val, str) else list(val)
                    i += 1
                except OSError:
                    break
    except OSError:
        vals = {}
    slots = {s: (vals.get(f"{A.SLOT_PKEY},{idx}")
                 if isinstance(vals.get(f"{A.SLOT_PKEY},{idx}"), str) else None)
             for s, idx in A.SLOTS.items()}
    proc = {f"{A.PROC_PKEY},{p}": (vals.get(f"{A.PROC_PKEY},{p}") or [])
            for p in (5, 6, 7)}
    return slots, proc


def cmd_list():
    print(json.dumps([{"guid": d.guid, "name": d.name,
                       "attached": d.attached, "default": d.is_default}
                      for d in A.enumerate_devices()], indent=1))


def cmd_attach(guid, use_original=True):
    if not is_admin():
        elevate()
    from harmo_dsp.dsp import apo_attach as A2
    slots, proc = read_state(guid)
    plan = A2.compute_attach_plan(slots, proc, use_original)
    try:
        with _open_fx(guid, write=True) as k:
            for name, val in plan["writes_fx"].items():
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            for name in plan["deletes_fx"]:
                try:
                    winreg.DeleteValue(k, name)
                except OSError:
                    pass
            for name, modes in plan["ensure_proc_modes"].items():
                winreg.SetValueEx(k, name, 0, winreg.REG_MULTI_SZ, modes)
            try:
                winreg.DeleteValue(k, A2.DISABLE_ENH)
            except OSError:
                pass
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                              f"{A2.CHILD_BASE}\\{guid}") as ck:
            for s, v in plan["child_backup"].items():
                winreg.SetValueEx(ck, f"{A2.SLOT_PKEY},{A2.SLOTS[s]}", 0,
                                  winreg.REG_SZ, v or "!VALUE")
            winreg.SetValueEx(ck, "PreMixChild", 0, winreg.REG_SZ,
                              plan["child_pre"] or "")
            winreg.SetValueEx(ck, "PostMixChild", 0, winreg.REG_SZ,
                              plan["child_post"] or "")
            winreg.SetValueEx(ck, "Version", 0, winreg.REG_SZ, "2")
    except PermissionError:
        print(json.dumps({"ok": False, "error": "Access denied even as admin — "
                          "use official Configurator (it takes ownership)."}))
        sys.exit(3)
    # official-style .reg backup next to APO config
    try:
        from harmo_dsp.dsp.apo_setup import find_config_dir
        d = find_config_dir()
        if d:
            devs = {x.guid: x.name for x in A2.enumerate_devices()}
            safe = re.sub(r"[^\w\- ]+", "", devs.get(guid, guid))[:60]
            with open(os.path.join(d, f"backup_Harmo-Dsp_{safe}.reg"),
                      "w", encoding="utf-8") as fh:
                fh.write(A2.reg_backup_text(guid, slots))
    except OSError:
        pass
    print(json.dumps({"ok": True, "attached": guid,
                      "reboot_required": True,
                      "note": "Reboot like the official tool, then verify sound."}))


def cmd_detach(guid):
    if not is_admin():
        elevate()
    from harmo_dsp.dsp.apo_attach import compute_detach_plan, CHILD_BASE, SLOT_PKEY, SLOTS
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             f"{CHILD_BASE}\\{guid}", 0,
                             winreg.KEY_READ) as ck:
            backup = {}
            for s in SLOTS:
                try:
                    v, _ = winreg.QueryValueEx(ck, f"{SLOT_PKEY},{SLOTS[s]}")
                    backup[s] = str(v)
                except OSError:
                    backup[s] = None
        plan = compute_detach_plan(backup)
        with _open_fx(guid, write=True) as k:
            for name, val in plan["writes_fx"].items():
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            for name in plan["deletes_fx"]:
                try:
                    winreg.DeleteValue(k, name)
                except OSError:
                    pass
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, f"{CHILD_BASE}\\{guid}")
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"{e}. Nothing changed."}))
        sys.exit(3)
    print(json.dumps({"ok": True, "detached": guid, "reboot_required": True}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Attach/detach Equalizer APO (elevated).")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--attach", metavar="DEVICE-GUID")
    ap.add_argument("--detach", metavar="DEVICE-GUID")
    ap.add_argument("--no-original", action="store_true",
                    help="do not chain original vendor APO (not recommended)")
    a = ap.parse_args()
    if a.list:
        cmd_list()
    elif a.attach:
        cmd_attach(a.attach, use_original=not a.no_original)
    elif a.detach:
        cmd_detach(a.detach)
    else:
        ap.print_help()
