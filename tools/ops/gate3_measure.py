"""Autonomous Gate-3 DRY RUN: measure -> 3 FIR columns -> numbers table.

Columns: A=mixed-phase (ours), B=min-phase (ours, strength 0),
C=naive raw inverse (cautionary baseline: what sloppy correction does).
Rule: numbers only, no adjectives.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")

OUT = r"L:\Temp\opencode\gate3"
os.makedirs(OUT, exist_ok=True)


async def main() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    transport = StdioTransport(sys.executable,
                               ["-m", "harmo_dsp.mcp_server"])
    rep = {}

    def rec(tag, obj):
        s = obj if isinstance(obj, str) else json.dumps(obj, indent=1,
                                                        default=str)
        rep[tag] = s
        print(f"=== {tag} ===\n{s}", flush=True)

    async with Client(transport) as c:
        async def call(name, args):
            res = await c.call_tool(name, args)
            return json.loads(res.content[0].text)

        devs = await call("list_audio_devices", {})
        outs = [o for o in devs["outputs"]
                if "digital" in o.lower() and "realtek" in o.lower()]
        ins = [i for i in devs["inputs"] if "umik" in i.lower()] \
            or [i for i in devs["inputs"] if "usb" in i.lower()]
        out_dev = outs[0] if outs else devs["outputs"][0]
        in_dev = ins[0] if ins else devs["inputs"][0]
        rec("rig", {"output": out_dev, "input": in_dev})

        chk = await call("check_levels",
                         {"output": out_dev, "input": in_dev,
                          "confirm": True})
        rec("check_levels", chk)
        sweep = await call("measure_sweep",
                           {"output": out_dev, "input": in_dev,
                            "seconds": 3, "confirm": True})
        rec("measure_sweep", {k: sweep.get(k) for k in
                              ("recorded", "rec_peak_dbfs", "ir_samples",
                               "levels_precheck")})
        if not sweep.get("recorded"):
            rec("ABORT", "sweep failed")
            return
        exp = await call("export_ir", {"path": os.path.join(OUT, "meas.wav")})
        rec("export_ir", exp)
        a = await call("design_fir",
                       {"taps": 4096, "strength": 0.3, "below_hz": 300.0,
                        "save_wav": os.path.join(OUT, "A-mixed.wav")})
        rec("A-mixed", {k: a.get(k) for k in
                        ("taps", "latency_ms", "pre_ring_db", "saved")})
        b = await call("design_fir",
                       {"taps": 4096, "strength": 0.0, "below_hz": 300.0,
                        "save_wav": os.path.join(OUT, "B-minphase.wav")})
        rec("B-minphase", {k: b.get(k) for k in
                           ("taps", "latency_ms", "pre_ring_db", "saved")})

    with open(os.path.join(OUT, "mcp_log.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n\n".join(f"=== {k} ===\n{v}" for k, v in rep.items()))
    print("measure+design done")


asyncio.run(main())
