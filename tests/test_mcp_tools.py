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


def test_check_levels_gate_and_procedure(monkeypatch):
    _reset()
    r = json.loads(T.check_levels("0: x", "1: y"))
    assert r["refused"] is True  # gate first
    # too-quiet mic => sweep must refuse BEFORE playing the sweep
    from harmo_dsp.io import audio as A
    calls = []

    def fake_quiet(sweep, fs, out, inp, seconds):
        calls.append("x")
        import numpy as np
        return np.zeros(int(seconds * fs))

    monkeypatch.setattr(A, "play_rec", fake_quiet)
    r2 = json.loads(T.measure_sweep("0: x", "1: y", confirm=True))
    assert r2["refused"] and "level check FAILED" in r2["refused"]
    assert len(calls) == 1  # burst only — sweep never played


def test_measure_sweep_proceeds_after_good_level(monkeypatch):
    _reset()
    import numpy as np
    from harmo_dsp.io import audio as A

    def fake(sweep, fs, out, inp, seconds):
        return np.asarray(sweep[:int(seconds * fs)]) * 0.5

    monkeypatch.setattr(A, "play_rec", fake)
    r = json.loads(T.measure_sweep("0: x", "1: y", seconds=1.0, confirm=True))
    assert r.get("recorded") is True
    assert r["levels_precheck"]["verdict"].startswith("OK")


def test_save_graph_writes_png(tmp_path):
    _reset()
    png = tmp_path / "fr.png"
    r = json.loads(T.save_graph(str(png)))  # nothing in session yet
    assert "error" in r
    # put a synthetic measurement in session, then draw
    T.SESSION["measurements"]["syn"] = type(
        "M", (), {"frequencies": [20 * 2 ** (i / 48) for i in range(193)],
                  "spl": [0.0] * 96 + [6.0, 6.0, 6.0] + [0.0] * 94,
                  "phase": None})()
    r2 = json.loads(T.save_graph(str(png)))
    assert r2.get("saved") and r2["curves"] == ["syn"]
    assert png.exists() and png.stat().st_size > 1000


def test_ir_freq_response_finds_bump():
    import numpy as np
    from scipy.signal import lfilter
    from harmo_dsp.dsp.measure import ir_freq_response
    from harmo_dsp.dsp.clip_guard import _rbj
    fs = 8000
    b, a = _rbj("PK", 500, 8.0, 2.0, fs)
    ir = lfilter(b, a, np.concatenate([np.ones(1), np.zeros(2047)]))
    f, db = ir_freq_response(ir, fs)
    i = int(np.argmin(np.abs(f - 500)))
    assert abs(f[i] - 500) <= 12  # ~2.2%/step log grid near 500 Hz
    assert db[i] > 6.0  # the +8 dB bump is visible at the grid point


def test_backend_and_meter_never_crash():
    r = json.loads(T.check_backend())
    assert "versions" in r and "apo" in r
    m = json.loads(T.get_output_meter())
    assert m["status"] in ("live", "silent", "unavailable", "error")


def test_export_ir_roundtrip(tmp_path):
    _reset()
    import numpy as np
    T.SESSION["irs"]["sweep#0"] = (48000, np.zeros(512))
    T.SESSION["irs"]["sweep#0"][1][10] = 1.0
    import json
    r = json.loads(T.export_ir(path=str(tmp_path / "out.wav")))
    assert r["exported"].endswith("out.wav") and r["samples"] == 512
    r2 = json.loads(T.export_ir(name="nope"))
    assert "sweep_0" in r2["exported"]  # falls back to latest (# sanitized)
    _reset()
    r3 = json.loads(T.export_ir())
    assert "error" in r3


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
            assert "check_levels" in names  # REW-style pre-procedure
            assert "export_ir" in names and "push_ir_to_rew" in names
            res = await c.call_tool("check_backend", {})
            data = json.loads(res.content[0].text)
            assert "versions" in data

    asyncio.run(_run())


def test_gui_measurement_panel_preselects_rig(monkeypatch):
    import os
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.pages import ImportPage
    from harmo_dsp.io import audio as A

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(A, "available", lambda: True)
    monkeypatch.setattr(
        A, "devices",
        lambda: (["3: Sound Mapper", "4: Realtek Digital Output (Realtek(R) Audio)",
                  "5: Speakers (USB)"],
                 ["0: Sound Mapper In", "1: Microphone (3- USB Audio Device)",
                  "2: DroidCam"]))
    p = ImportPage()
    assert "4: Realtek Digital" in p.m_out.currentText()
    assert "USB Audio" in p.m_in.currentText()
    p.close()
