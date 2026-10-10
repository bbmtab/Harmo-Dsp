"""REW RTA capture -> OUR app: decode FR, import, auto-EQ preview."""
import asyncio
import base64
import json
import struct
import sys

import numpy as np

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")


def decode_rew_fr(path):
    # per API docs ("Array encoding"): raw 32-bit float bytes, BIG-endian
    d = json.load(open(path))
    raw = base64.b64decode(d["magnitude"])
    mag = np.array(struct.unpack(f">{len(raw)//4}f", raw), dtype=np.float64)
    f = d["startFreq"] + np.arange(len(mag)) * d["freqStep"]
    # Pink noise has CONSTANT energy per octave: re-bin linear FFT bins
    # into 1/12-oct energy bands. Deviation from flat = the ROOM.
    centers = 20.0 * 2.0 ** (np.arange(0, 120) / 12.0)
    centers = centers[centers <= 20000.0]
    out_f, out_db = [], []
    pw = 10.0 ** (np.asarray(mag, dtype=np.float64) / 10.0)  # dB -> power
    for c in centers:
        lo, hi = c / 2 ** (1 / 24), c * 2 ** (1 / 24)
        m = (f >= lo) & (f < hi)
        if m.sum() < 2:
            continue
        with np.errstate(divide="ignore"):
            out_db.append(10.0 * np.log10(max(pw[m].sum(), 1e-30)))
        out_f.append(c)
    return np.array(out_f), np.array(out_db)


async def main() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    from harmo_dsp.mcp_server import tools as T

    f, db = decode_rew_fr(r"L:\Temp\opencode\rew_fr.json")
    print(f"REW curve: {len(f)} pts, {f[0]:.1f}-{f[-1]:.0f} Hz, "
          f"range {db.min():.1f}..{db.max():.1f} dB", flush=True)
    T.SESSION.clear()
    T.SESSION.update({"measurements": {}, "irs": {}, "bands": [],
                      "preamp": 0.0})
    # our session Measurement: simple namespace object
    T.SESSION["measurements"]["REW-RTA"] = type(
        "M", (), {"frequencies": list(f), "spl": list(db),
                  "phase": None})()

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

        # NOTE: measurement already in T.SESSION of THIS process, but the
        # MCP server is a separate process with its OWN session -> import
        # via a file bridge instead: save REW curve as our txt format
        txt = "\n".join(f"{ff:.2f} {dd:.2f}" for ff, dd in zip(f, db))
        open(r"L:\Temp\opencode\rew_curve.txt", "w").write(
            "* REW RTA L+R 1/12 oct\n" + txt)
        rec("import", await call(
            "import_measurement",
            {"path": r"L:\Temp\opencode\rew_curve.txt",
             "name": "REW-RTA"}))
        rec("analyze", await call("analyze_measurement",
                                  {"name": "REW-RTA"}))
        eq = await call("auto_eq",
                        {"target": "flat", "fit_lo": 25.0, "fit_hi": 150.0,
                         "max_bands": 6, "max_cut": 12.0, "max_boost": 3.0,
                         "write": False})
        short = {k: v for k, v in eq.items() if k not in ("preview",)}
        short["bands"] = [{"fc": round(b["fc"], 1),
                           "gain": round(b["gain"], 1),
                           "q": round(b["q"], 2)} for b in eq["bands"]]
        rec("auto_eq PREVIEW bass-only (nothing written)", short)
        rec("graph", await call(
            "save_graph",
            {"path": r"L:\Temp\opencode\dirac_result.png"}))

    with open(r"L:\Temp\opencode\rew_flow_result.txt", "w",
              encoding="utf-8") as fh:
        fh.write("\n\n".join(out))
    print("rew flow done")


asyncio.run(main())
