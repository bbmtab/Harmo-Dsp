"""Gate-3 harness tests: metrics + foreign FIR loading (synthetic)."""
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.dsp.compare import (
    load_foreign_fir, _cascade_metrics, step_metrics, markdown_table)
from harmo_dsp.dsp.clip_guard import _rbj
from scipy.signal import lfilter

FS, N = 8000, 2048


def _spk():
    x = np.zeros(N)
    x[0] = 1.0
    b, a = _rbj("PK", 100, 8.0, 2.0, FS)
    return lfilter(b, a, x)


def test_foreign_raw_txt_loads_with_explicit_fs(tmp_path):
    p = tmp_path / "impulse.txt"
    p.write_text("0\n0.5\n-0.25\nnot-a-number\n", encoding="utf-8")
    h = load_foreign_fir(str(p), 48000)
    assert list(h) == [0.0, 0.5, -0.25]


def test_foreign_missing_file_errors():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_foreign_fir("no-such-file.wav", 48000)


def test_cascade_metrics_improve_with_good_correction():
    from harmo_dsp.dsp.fir import design_speaker_fir, FirParams
    spk = _spk()
    rep = design_speaker_fir([spk], FS, FirParams(taps=1024, strength=0.0))
    m = _cascade_metrics(spk, rep.taps, FS)
    assert m["mag_rms_after"] < m["mag_rms_before"]
    assert m["latency_ms"] >= 0 and m["pre_ring_db"] < 0


def test_step_metrics_delta_vs_ringing_filter():
    d = np.zeros(512)
    d[0] = 1.0
    s_delta = step_metrics(d, FS)
    assert s_delta["overshoot_pct"] == 0.0 and s_delta["preshoot_pct"] == 0.0
    b, a = _rbj("PK", 200, 12.0, 8.0, FS)  # hot narrow resonance
    ring = lfilter(b, a, np.concatenate([[1.0], np.zeros(511)]))
    s_ring = step_metrics(ring, FS)
    assert s_ring["overshoot_pct"] > s_delta["overshoot_pct"]


def test_markdown_table_renders_rows():
    t = markdown_table([{**{k: 0.0 for k in (
        "mag_before", "mag_after", "gd_before", "gd_after", "pre_ring_db",
        "latency_ms", "overshoot_pct", "preshoot_pct", "rise_ms")},
        "name": "A-ours"}])
    assert "| A-ours |" in t and t.count("\n") == 2
