"""Elevated APO config writer (UAC "runas", user consents in the GUI).

Tries direct write first (works when GUI runs elevated); on denial it
re-launches ITSELF elevated. Payloads (bytes) come from the GUI, which
already showed backup + preview + confirm. Prints JSON results.

Usage:  python tools/write_apo.py --write-file <dir> <name>   (stdin bytes)
        python tools/write_apo.py --backup-file <dir> <name>  (prints backup path)
        python tools/write_apo.py --write-config <dir>        (stdin bytes)
        python tools/write_apo.py --restore <dir> <backup-name>
"""
import argparse
import ctypes
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from harmo_dsp.dsp.apo_setup import build_patched_config  # noqa: E402 pure fn


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> "NoReturn":
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join([f'"{a}"' for a in [os.path.abspath(__file__), *sys.argv[1:]]]),
        None, 1)
    sys.exit(0)


def read_payload(args) -> bytes:
    if args.payload_file:
        with open(args.payload_file, "rb") as fh:
            return fh.read()
    return sys.stdin.buffer.read()


def need_admin_for(path: str) -> bool:
    try:
        probe = os.path.join(path, ".harmo-write-test")
        with open(probe, "w") as fh:
            fh.write("x")
        os.remove(probe)
        return False
    except OSError:
        return True


def cmd_write_file(d: str, name: str, payload: bytes):
    if need_admin_for(d) and not is_admin():
        elevate()
    try:
        with open(os.path.join(d, name), "wb") as fh:
            fh.write(payload)
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(3)
    print(json.dumps({"ok": True, "path": os.path.join(d, name),
                      "bytes": len(payload)}))


def cmd_backup_file(d: str, name: str):
    if need_admin_for(d) and not is_admin():
        elevate()
    src = os.path.join(d, name)
    try:
        with open(src, "rb") as fh:
            data = fh.read()
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(3)
    bak = f"{name}.Harmo-Dsp.bak-{datetime.now():%Y%m%d-%H%M%S}"
    with open(os.path.join(d, bak), "wb") as fh:
        fh.write(data)
    print(json.dumps({"ok": True, "backup": bak}))


def cmd_write_config(d: str, payload: bytes):
    if need_admin_for(d) and not is_admin():
        elevate()
    try:
        with open(os.path.join(d, "config.txt"), "wb") as fh:
            fh.write(payload)
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(3)
    print(json.dumps({"ok": True}))


def cmd_restore(d: str, backup: str):
    if need_admin_for(d) and not is_admin():
        elevate()
    try:
        with open(os.path.join(d, backup), "rb") as fh:
            data = fh.read()
        with open(os.path.join(d, "config.txt"), "wb") as fh:
            fh.write(data)
    except OSError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(3)
    print(json.dumps({"ok": True, "restored_from": backup}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write APO config (elevates if needed).")
    ap.add_argument("--write-file", nargs=2, metavar=("DIR", "NAME"))
    ap.add_argument("--backup-file", nargs=2, metavar=("DIR", "NAME"))
    ap.add_argument("--write-config", metavar="DIR")
    ap.add_argument("--restore", nargs=2, metavar=("DIR", "BACKUP"))
    ap.add_argument("--payload-file", metavar="PATH",
                    help="read stdin payload from file (for elevated runs)")
    ap.add_argument("--patch-preview", nargs=2, metavar=("DIR", "INCLUDE"),
                    help="print patched config.txt without writing")
    a = ap.parse_args()
    payload = read_payload(a) if (a.write_file or a.write_config) else b""
    if a.write_file:
        cmd_write_file(*a.write_file, payload)
    elif a.backup_file:
        cmd_backup_file(*a.backup_file)
    elif a.write_config:
        cmd_write_config(a.write_config, payload)
    elif a.restore:
        cmd_restore(*a.restore)
    elif a.patch_preview:
        dd, inc = a.patch_preview
        try:
            with open(os.path.join(dd, "config.txt"), encoding="utf-8-sig",
                      errors="replace") as fh:
                cur = fh.read()
        except OSError:
            cur = ""
        new, after = build_patched_config(cur, inc)
        print(json.dumps({"patched": new, "after_peace": after}))
    else:
        ap.print_help()
