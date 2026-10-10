"""Approved write: measure -> auto_eq(write=true) with FIR."""
import asyncio
import json
import sys

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")


async def main() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(sys.executable,
                               ["-m", "harmo_dsp.mcp_server"])
    async with Client(transport) as c:
        async def call(name, args):
            res = await c.call_tool(name, args)
            return json.loads(res.content[0].text)

        devs = await call("list_audio_devices", {})
        outs = [o for o in devs["outputs"]
                if "digital" in o.lower() and "realtek" in o.lower()]
        ins = [i for i in devs["inputs"] if "umik" in i.lower()]
        out_dev = outs[0]
        in_dev = ins[0]

        sweep = await call("measure_sweep",
                           {"output": out_dev, "input": in_dev,
                            "seconds": 3, "confirm": True})
        print("sweep:", json.dumps({k: sweep[k] for k in
              ("recorded", "rec_peak_dbfs", "ir_samples")
              if k in sweep}))
        if not sweep.get("recorded"):
            print("SWEEP FAILED — nothing written")
            return

        # FIR phase-only first (same session, same measurement)
        fir = await call("design_fir",
                         {"taps": 4096, "strength": 0.3, "below_hz": 300.0,
                          "phase_only": True,
                          "save_wav": r"L:\Temp\opencode\phase_correction.wav"})
        print("fir:", json.dumps({k: fir[k] for k in
              ("taps", "latency_ms", "pre_ring_db") if k in fir}))

        # Combined write: PEQ bass-only + Convolution + Include
        r = await call("auto_eq",
                       {"target": "flat", "fit_lo": 25.0, "fit_hi": 150.0,
                        "max_bands": 6, "max_cut": 12.0, "max_boost": 3.0,
                        "write": True, "listen_approved": True,
                        "fir_wav": fir.get("saved", "")})
        print("auto_eq:", json.dumps({k: v for k, v in r.items()
              if k not in ("preview", "bands")}, indent=1))
        if r.get("bands"):
            for b in r["bands"]:
                print(f"  {b['fc']:7.1f} Hz  {b['gain']:+6.1f} dB  Q {b['q']:.2f}")


asyncio.run(main())
