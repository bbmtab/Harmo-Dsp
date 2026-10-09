"""APO presence & wiring status (Windows-only paths, guarded elsewhere).

Why APO is NEVER bundled (see docs/ASSUMPTIONS.md):
- License: Equalizer APO is GPL. Shipping its binary = distributing GPL
  software (source + copyleft obligations). Our core stays MIT.
- Technical: APO is a DRIVER, not a library. "Including" it means running
  its installer + Configurator + reboot with admin rights — an install-time
  action by the USER from the official source, never a bundled plugin DLL.
"""
from __future__ import annotations
import os
import subprocess

OFFICIAL_URL = "https://sourceforge.net/projects/equalizerapo/files/"
CANDIDATE_DIRS = [
    r"C:\Program Files\EqualizerAPO\config",
    r"C:\Program Files (x86)\EqualizerAPO\config",
]


def find_config_dir(candidates: list[str] | None = None) -> str | None:
    for d in candidates or CANDIDATE_DIRS:
        try:
            if os.path.isfile(os.path.join(d, "config.txt")):
                return d
        except OSError:
            continue
    # last resort: dir exists but config.txt missing (fresh/broken install)
    for d in candidates or CANDIDATE_DIRS:
        try:
            if os.path.isdir(d):
                return d
        except OSError:
            continue
    return None


def read_config(config_dir: str) -> str:
    try:
        with open(os.path.join(config_dir, "config.txt"),
                  encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def status(config_dir: str | None) -> tuple[str, str]:
    """(state, human message). States: missing | idle | peace-idle | wired."""
    if not config_dir:
        return ("missing",
                "✗ Equalizer APO not found. Install it (once, official), "
                "then attach your speaker in Configurator + reboot.")
    text = read_config(config_dir)
    low = text.lower()
    if "speakercorrect" in low:
        return ("wired", f"✓ Wired: speakercorrect is Included ({config_dir}).")
    if "peace.txt" in low:
        return ("peace-idle",
                f"ℹ Peace drives APO here; ours is not Included yet. "
                f"Write the file, then add our Include AFTER peace.txt.")
    active = [ln for ln in text.splitlines()
              if ln.strip() and not ln.strip().startswith("#")]
    if not active:
        return ("idle",
                f"⚠ APO installed but config.txt does nothing "
                f"(comments only) — and no device may be attached yet. "
                f"Run Configurator, tick your speaker, reboot.")
    return ("idle",
            f"⚠ APO active with other content; ours not Included yet.")


def open_configurator(config_dir: str | None) -> bool:
    """Launch official Configurator.exe (user clicks through, admin+reboot)."""
    candidates = []
    if config_dir:
        candidates.append(os.path.join(os.path.dirname(config_dir),
                                        "Configurator.exe"))
    candidates += [r"C:\Program Files\EqualizerAPO\Configurator.exe",
                   r"C:\Program Files (x86)\EqualizerAPO\Configurator.exe"]
    for exe in candidates:
        try:
            if os.path.isfile(exe):
                subprocess.Popen([exe])
                return True
        except OSError:
            continue
    return False
