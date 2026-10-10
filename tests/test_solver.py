"""Auto-solver acceptance tests (brief criteria, synthetic only)."""
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.dsp.solver import solve_peq, SolverParams
from harmo_dsp.dsp.target import target_curve_db, preset_curve
from harmo_dsp.dsp.clip_guard import _rbj
from scipy.signal import freqz

F = np.logspace(np.log10(20), np.log10(20000), 480)


def _pk(fc, gain, q, fs=48000):
    b, a = _rbj("PK", fc, gain, q, fs)
    _, h = freqz(b, a, worN=F, fs=fs)
    return 20 * np.log10(np.maximum(np.abs(h), 1e-12))


def test_smooth_peak_corrected_over_50pct():
    measured = _pk(60, 8.0, 2.0)            # boomy 60 Hz room bump
    bands, rep = solve_peq(F, measured, None)
    assert rep["placed"] >= 1
    after = measured
    from harmo_dsp.dsp.solver import _biquad_db
    for b in bands:
        after = after + _biquad_db(b, F, 48000)  # filters ADD to the chain
    fit = (F >= 30) & (F <= 8000)
    rms_b = float(np.sqrt(np.mean(measured[fit] ** 2)))
    rms_a = float(np.sqrt(np.mean(after[fit] ** 2)))
    assert rms_a <= 0.5 * rms_b, (rms_b, rms_a)
    assert all(b.gain <= 0.01 for b in bands) or max(
        b.gain for b in bands) <= 6.0
    # main action lands near 60 Hz
    fc = min(bands, key=lambda b: abs(b.fc - 60)).fc
    assert abs(fc - 60) < 15


def test_deep_null_not_boosted():
    measured = -_pk(120, 18.0, 8.0)         # deep narrow null at 120 Hz
    bands, rep = solve_peq(F, measured, None)
    near = [b for b in bands if abs(b.fc - 120) < 40]
    assert all(b.gain <= 0.5 for b in near)  # never chase the null
    # and no wasteful boost anywhere: cuts only allowed on flat + null
    assert all(b.gain <= 0.01 for b in bands)


def test_highs_get_wide_q_only():
    measured = _pk(5000, 6.0, 4.0)           # treble bump
    bands, _ = solve_peq(F, measured, None)
    assert bands, "solver must act on the treble bump"
    assert abs(bands[0].fc - 5000) < 300     # main action at the bump
    # every band above the xover must stay WIDE (brief rule)
    assert all(b.q <= 1.51 for b in bands if b.fc >= 500)
    # shoulder cleanups stay in the neighbourhood
    assert all(abs(b.fc - 5000) < 3500 for b in bands)  # shoulder cleanup zone


def test_bass_target_80_corner_gets_boosted_below():
    # measured flat + target bass+3@80 -> solver must LIFT below 80 Hz
    measured = np.zeros_like(F)
    tgt = preset_curve(F, "bass+3@80", corner_hz=80)
    bands, rep = solve_peq(F, measured, tgt)
    assert rep["placed"] >= 1
    lo = [b for b in bands if b.fc < 80]
    assert lo and all(b.gain > 0 for b in lo)
    # shelf shape: the boost centre sits below the corner
    assert max(lo, key=lambda b: b.gain).fc <= 80


def test_corner_semantics_80_vs_150():
    f = np.array([30.0, 40.0, 79.0, 120.0, 400.0])
    t80 = target_curve_db(f, bass_db=3.0, corner_hz=80.0)
    t150 = target_curve_db(f, bass_db=3.0, corner_hz=150.0)
    # 4th-order shelf: full depth ~1 octave below the corner
    assert t80[0] > 2.9                     # 30 Hz: essentially full depth
    assert 2.5 < t80[1] <= 3.0              # 40 Hz: nearly there
    assert t80[3] < 0.5 and t80[4] < 0.01   # above corner: flat again
    assert t150[3] > t80[3]                  # 120 Hz: in the 150 shelf
    assert t150[3] > t80[3] and t150[2] > t80[2]


def test_auto_eq_tool_end_to_end_preview():
    from harmo_dsp.mcp_server import tools as T
    import json
    T.SESSION.clear()
    T.SESSION.update({"measurements": {}, "irs": {}, "bands": [],
                      "preamp": 0.0})
    T.SESSION["measurements"]["syn"] = type(
        "M", (), {"frequencies": list(F),
                  "spl": list(_pk(60, 8.0, 2.0)), "phase": None})()
    r = json.loads(T.auto_eq(target="bass+3@80", write=False))
    assert r["bands_placed"] >= 1
    assert r["improvement_pct"] > 40
    assert r["written"] is False and "Preview" in r["note"]
    cur = json.loads(T.get_eq())
    assert len(cur["bands"]) == r["bands_placed"]
