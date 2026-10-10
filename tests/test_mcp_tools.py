"""MCP tool tests: plain functions + in-memory client round-trip."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.mcp_server import tools as T

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _reset():
    T.SESSION.clear()
    T.SESSION.update({"measurements": {}, "irs": {}, "bands": [],
                      "preamp": 0.0})


def test_import_rew_filters_and_freq_response():
    _reset()
    r = json.loads(T.import_measurement(os.path.join(SAMPLES, "rew1.txt")))
    assert r["kind"] == "rew-filters" and r["bands"] == 20
    # now a frequency-response text
    frd = os.path.join(SAMPLES, "impulse.txt")
    if os.path.isfile(frd):
        r2 = json.loads(T.import_measurement(frd, name="raw"))
        assert r2.get("kind") == "freq-response" or "error" in r2


def test_analyze_synthetic_measurement():
    _reset()
    spl = [0.0] * 193
    spl[95:98] = [8.0, 8.0, 8.0]  # ~80 Hz bump, survives smoothing
    T.SESSION["measurements"]["syn"] = type(
        "M", (), {"frequencies": [20 * 2 ** (i / 48) for i in range(193)],
                  "spl": spl, "phase": None})()
    r = json.loads(T.analyze_measurement("syn"))
    assert any(70 <= p["hz"] <= 90 for p in r["top_peaks"])
    assert r["interpretation"]


def test_get_set_eq_roundtrip_and_preview_only():
    _reset()
    r = json.loads(T.set_eq([{"ftype": "PK", "fc": 63, "gain": -5,
                              "q": 2, "on": True, "channel": "all"}],
                            preamp=-2))
    assert r["written"] is False
    assert "Preamp: -2 dB" in r["preview"]
    cur = json.loads(T.get_eq())
    assert cur["bands"][0]["fc"] == 63 and cur["preamp"] == -2


def test_measure_sweep_refuses_without_confirm():
    _reset()
    r = json.loads(T.measure_sweep(output="0: x", input="1: y"))
    assert r["refused"] is True  # never a side effect without consent


def test_backend_and_meter_never_crash():
    r = json.loads(T.check_backend())
    assert "versions" in r and "apo" in r
    m = json.loads(T.get_output_meter())
    assert m["status"] in ("live", "silent", "unavailable", "error")


def test_inmemory_client_lists_and_calls_tools():
    import asyncio

    async def _run():
        from fastmcp import Client
        mcp = __import__("harmo_dsp.mcp_server.server",
                         fromlist=["build_server"]).build_server()
        async with Client(mcp) as c:
            tools = await c.list_tools()
            names = [t.name for t in tools]
            assert "check_backend" in names and "set_eq" in names
            res = await c.call_tool("check_backend", {})
            data = json.loads(res.content[0].text)
            assert "versions" in data

    asyncio.run(_run())
