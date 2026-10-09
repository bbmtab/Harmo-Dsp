"""Plugin runner: external programs via subprocess only (never linked).

Each plugin lives in plugins/<name>/plugin.json (manifest) + user-installed
binary. Binaries are NEVER bundled (see plugins/README.md).
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass
class Plugin:
    name: str
    version: str
    license: str
    source_url: str
    exe: str
    args: list[str]
    description: str
    manifest_path: str = ""


def plugins_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(root, "plugins")


def discover(root: str | None = None) -> list[Plugin]:
    """List manifests in plugins/<name>/plugin.json (binary presence separate)."""
    out: list[Plugin] = []
    root = root or plugins_dir()
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        mf = os.path.join(root, name, "plugin.json")
        if not os.path.isfile(mf):
            continue
        try:
            with open(mf, encoding="utf-8") as fh:
                d = json.load(fh)
            out.append(Plugin(d.get("name", name), d.get("version", "?"),
                              d.get("license", "?"), d.get("source_url", ""),
                              d.get("exe", ""), d.get("args", []),
                              d.get("description", ""), mf))
        except (OSError, ValueError):
            continue
    return out


def is_installed(plug: Plugin) -> bool:
    return bool(shutil.which(plug.exe))


def run(plug: Plugin, infile: str, outfile: str,
        timeout_s: int = 300) -> tuple[int, str, str]:
    """Run plugin binary: template {in}/{out} into args. Returns (rc, stdout, stderr).

    Uses a temp working copy; cleans up afterwards. Raises FileNotFoundError
    when the user has not installed the binary (with source_url hint).
    """
    if not is_installed(plug):
        raise FileNotFoundError(
            f"{plug.name} not installed. Get it at {plug.source_url} "
            f"(license: {plug.license}), then point PATH at {plug.exe}.")
    args = [a.replace("{in}", infile).replace("{out}", outfile)
            for a in plug.args]
    with tempfile.TemporaryDirectory(prefix="harmo-plug-") as tmp:
        proc = subprocess.run([plug.exe, *args], capture_output=True,
                              text=True, timeout=timeout_s, cwd=tmp)
    return proc.returncode, proc.stdout[-4000:], proc.stderr[-4000:]
