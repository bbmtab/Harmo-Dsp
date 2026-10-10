"""User's REW manual sweep -> OUR Dirac pipeline (no re-sweep needed).

Reads the already-downloaded FR+IR, imports to session, analyzes,
auto-EQ previews with the user's recipe (bass-only 25-95, cuts-only,
soft caps). Preview only — ear gate before any write.
"""
import asyncio
import base64
import json
import struct
import sys

import numpy as np

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")


def deb64(s):
    raw = base64.b64decode(s)
    return np.array(struct.unpack(f">{len(raw)//4}f", raw),
                    dtype=np.float64)


async def main() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    from harmo_dsp.mcp_server import tools as T

    fr = json.load(open(r"L:\Temp\opencode\rew_sweep_fr.json"))
    mag = deb64(fr["magnitude"])
    ph = deb64(fr["phase"]) if fr.get("phase") else None
    if fr.get("freqStep"):
        f = fr["startFreq"] + np.arange(len(mag)) * fr["freqStep"]
    else:
        ppo = fr.get("ppo", 96)
        f = fr["startFreq"] * 2.0 ** (np.arange(len(mag)) / ppo)
    m = (f >= 20) & np.isfinite(mag)
    f, mag = f[m], mag[m]
    print(f"REW sweep: {len(f)} pts {f[0]:.1f}-{f[-1]:.0f} Hz "
          f"phase={'yes' if ph is not None else 'no'}", flush=True)

    irj = json.load(open(r"L:\Temp\opencode\rew_sweep_ir.json"))
    ird = deb64(irj["data"])
    fs_ir = float(irj.get("sampleRate", 6000.0))
    print(f"REW IR: {len(ird)} samples @ {fs_ir:.0f} Hz", flush=True)

    T.SESSION.clear()
    T.SESSION.update({"measurements": {}, "irs": {}, "bands": [],
                      "preamp": 0.0})
    # NOTE: this T.SESSION is CLIENT-side only. The server subprocess has
    # its own empty session -> bridge the curve through a FILE + tool.
    txt = "\n".join(f"{ff:.2f} {dd:.2f}" for ff, dd in zip(f, mag))
    open(r"L:\Temp\opencode\rew_curve.txt", "w").write(
        "* REW manual sweep 30-500Hz UMIK-1+cal\n" + txt)
    _ = T  # silence unused warning; session filled server-side below

    transport = StdioTransport(sys.executable,
                               ["-m", "harmo_dsp.mcp_server"])
    out = []

    def rec(tag, obj):
        s = obj if isinstance(obj, str) else json.dumps(obj, indent=1,
                                                        default=str)
        out.append(f"=== {tag} ===\n{s}")
        print(f"=== {tag} ===\n{s}", flush=True)

    async with Client(transport) as c:
        async def call(name, args):
            res = await c.call_tool(name, args)
            return json.loads(res.content[0].text)

        rec("import", await call(
            "import_measurement",
            {"path": r"L:\Temp\opencode\rew_curve.txt",
             "name": "REW-manual"}))
        rec("analyze", await call("analyze_measurement",
                                  {"name": "REW-manual"}))
        eq = await call("auto_eq",
                        {"target": "flat", "fit_lo": 25.0, "fit_hi": 95.0,
                         "max_bands": 6, "max_cut": 12.0, "max_boost": 0.0,
                         "write": False, "name": "REW-manual"})
        short = {k: v for k, v in eq.items() if k not in ("preview",)}
        short["bands"] = [{"fc": round(b["fc"], 1),
                           "gain": round(b["gain"], 1),
                           "q": round(b["q"], 2)} for b in eq["bands"]]
        rec("auto_eq PREVIEW bass-only cuts-only (nothing written)", short)
        rec("graph", await call(
            "save_graph",
            {"path": r"L:\Temp\opencode\dirac_result.png",
             "name": "REW-manual"}))

    with open(r"L:\Temp\opencode\rew_manual_result.txt", "w",
              encoding="utf-8") as fh:
        fh.write("\n\n".join(out))
    print("done")


asyncio.run(main())
