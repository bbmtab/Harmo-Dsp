"""Full assistant-driven flow: measure (UMIK-1) -> auto-EQ preview.

Nothing is written to APO. The user LISTENS next, then approves.
"""
import asyncio
import json
import sys

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")


async def main() -> None:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    out = []

    def rec(tag, obj):
        s = obj if isinstance(obj, str) else json.dumps(obj, indent=1,
                                                        default=str)
        out.append(f"=== {tag} ===\n{s}")
        print(f"=== {tag} ===\n{s}", flush=True)

    transport = StdioTransport(sys.executable,
                               ["-m", "harmo_dsp.mcp_server"])
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

        lvl = await call("check_levels",
                         {"output": out_dev, "input": in_dev,
                          "confirm": True})
        rec("check_levels", lvl)

        sweep = await call("measure_sweep",
                           {"output": out_dev, "input": in_dev,
                            "seconds": 3, "confirm": True})
        rec("measure_sweep", sweep)
        if not sweep.get("recorded"):
            rec("ABORT", "sweep failed")
        else:
            # 1) PEQ preview: very-low bass ONLY, cuts ONLY.
            # 100-200 Hz is the 3" driver's own dead zone -> excluded.
            eq = await call("auto_eq",
                            {"target": "flat", "fit_lo": 25.0, "fit_hi": 95.0,
                             "max_bands": 6, "max_cut": 12.0, "max_boost": 0.0,
                             "write": False})
            short = {k: v for k, v in eq.items() if k not in ("preview",)}
            short["bands"] = [{"fc": round(b["fc"], 1),
                               "gain": round(b["gain"], 1),
                               "q": round(b["q"], 2)} for b in eq["bands"]]
            rec("EQ PREVIEW (bass-only)", short)

            # 2) Phase-only FIR (rePhase-equivalent)
            fir = await call("design_fir",
                             {"taps": 4096, "strength": 0.3,
                              "below_hz": 300.0, "phase_only": True,
                              "save_wav": r"L:\Temp\opencode\phase_correction.wav"})
            rec("FIR PREVIEW (phase-only)", fir)
            rec("graph", await call(
                "save_graph",
                {"path": r"L:\Temp\opencode\dirac_result.png"}))

    with open(r"L:\Temp\opencode\flow_result.txt", "w",
              encoding="utf-8") as fh:
        fh.write("\n\n".join(out))
    print("flow done")


asyncio.run(main())
