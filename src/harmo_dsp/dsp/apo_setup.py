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


def candidate_configurators(config_dir: str | None) -> list[str]:
    """Configurator.exe candidates (pure, testable — no side effects)."""
    out = []
    if config_dir:
        out.append(os.path.join(os.path.dirname(config_dir),
                                "Configurator.exe"))
    out += [r"C:\Program Files\EqualizerAPO\Configurator.exe",
            r"C:\Program Files (x86)\EqualizerAPO\Configurator.exe"]
    return out


def open_configurator(config_dir: str | None) -> bool:
    """Launch official Configurator.exe (user clicks through, admin+reboot).

    Uses os.startfile (ShellExecute): Popen CANNOT start admin-manifest
    executables (WinError 740) and must not be used here.
    """
    for exe in candidate_configurators(config_dir):
        try:
            if os.path.isfile(exe):
                os.startfile(exe)  # noqa: PYC-related n/a — Windows only
                return True
        except OSError:
            continue
    return False


def _key_exists(hive, path: str) -> bool:
    try:
        import winreg
        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ):
            return True
    except OSError:
        return False


def apo_registration_ok(hive=None, classes_root: str = r"SOFTWARE\Classes") -> tuple[bool, bool]:
    """Engine COM registration present? (pre-mix, post-mix).

    Hive/root injectable so tests use an HKCU sandbox instead of HKLM.
    """
    try:
        import winreg
    except ImportError:
        return False, False
    hive = hive if hive is not None else winreg.HKEY_LOCAL_MACHINE
    from .apo_attach import PRE_MIX, POST_MIX
    ok = []
    for guid in (PRE_MIX.strip("{}"), POST_MIX.strip("{}")):
        present = (
            _key_exists(hive, f"{classes_root}\\AudioEngine\\AudioProcessingObjects\\{{{guid}}}")
            or _key_exists(hive, f"{classes_root}\\CLSID\\{{{guid}}}"))
        ok.append(present)
    return ok[0], ok[1]


def installed_version() -> str | None:
    """DisplayVersion from the Uninstall registry (e.g. '1.2.1')."""
    try:
        import winreg
    except ImportError:
        return None
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0,
                             winreg.KEY_READ) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    sub = winreg.EnumKey(root, i)
                    with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
                        try:
                            name, _ = winreg.QueryValueEx(k, "DisplayName")
                        except OSError:
                            continue
                        if isinstance(name, str) and "equalizer apo" in name.lower():
                            try:
                                ver, _ = winreg.QueryValueEx(k, "DisplayVersion")
                                return str(ver)
                            except OSError:
                                return "?"
                except OSError:
                    continue
    except OSError:
        pass
    return None


def full_report(config_dir: str | None = None) -> dict:
    """4-point machine report: install, engine registration, attach, config."""
    from . import apo_attach as A
    cfg = config_dir or find_config_dir()
    try:
        devs = A.enumerate_devices()
    except Exception:
        devs = []
    attached = [d for d in devs if d.attached]
    pre_ok, post_ok = apo_registration_ok()
    ver = installed_version()
    cfg_state, cfg_msg = status(cfg)
    lines = [
        ("✓ Installed: Equalizer APO " + ver) if ver
        else "✗ Equalizer APO not installed",
        "✓ Engine registered (pre+post mix)" if (pre_ok and post_ok)
        else "✗ Engine registration missing (pre=%s post=%s)" % (pre_ok, post_ok),
        ("✓ Attached: %d of %d device(s)" % (len(attached), len(devs)))
        if attached else ("✗ Attached: 0 of %d device(s)" % len(devs)),
        cfg_msg,
    ]
    return {"installed_version": ver, "reg_pre": pre_ok, "reg_post": post_ok,
            "devices": devs, "attached": attached,
            "config_state": cfg_state, "lines": lines}


def build_patched_config(current: str, include_name: str) -> tuple[str, bool]:
    """Insert/replace our Include line (after peace.txt when present).

    Pure function shared by the GUI and the elevated writer.
    Returns (new_text, placed_after_peace).
    """
    want = f"Include: {include_name}"
    lines = [ln for ln in current.splitlines()
             if ln.strip().lower() != want.lower()
             and "speakercorrect" not in ln.lower()
             and "harmo-dsp" not in ln.lower()]
    placed, after_peace = False, False
    out: list[str] = []
    for ln in lines:
        out.append(ln)
        if (not placed and "peace.txt" in ln.lower()
                and ln.strip().lower().startswith("include")):
            out.append(want)
            placed, after_peace = True, True
    if not placed:
        out.append(want)
    return "\n".join(out) + "\n", after_peace
