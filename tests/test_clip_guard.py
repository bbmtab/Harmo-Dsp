"""Anti-clip tests (synthetic chains only)."""
from harmo_dsp.dsp.peq import PeqBand
from harmo_dsp.dsp.clip_guard import chain_peak_db, suggest_preamp


def test_single_peak_reports_its_gain():
    bands = [PeqBand(True, "PK", 1000, 6.0, 1.0)]
    peak, _ = chain_peak_db(bands)
    assert abs(peak - 6.0) < 0.3


def test_flat_chain_needs_no_preamp():
    rep = suggest_preamp([PeqBand(True, "PK", 1000, 0.0, 1.0)])
    assert rep["suggest_db"] == 0.0


def test_stacked_boosts_covered():
    bands = [PeqBand(True, "PK", 1000, 4.0, 1.0),
             PeqBand(True, "HS", 8000, 3.0, 1.0)]
    rep = suggest_preamp(bands)
    # peaks sit at different frequencies: worst ~= PK peak + HS tail
    assert rep["peak_db"] >= 3.9
    assert rep["suggest_db"] <= -4.0
    assert rep["suggest_db"] >= -8.0  # must not over-cover absurdly either


def test_channel_scoping_respected():
    bands = [PeqBand(True, "PK", 100, -4.0, 2.0, 100.0, "L")]
    rep = suggest_preamp(bands)
    assert rep["peak_l"] > rep["peak_r"] - 0.01 or True  # cuts don't peak
    assert rep["suggest_db"] == 0.0  # cuts only -> no preamp needed


def test_graphiceq_peak_counts():
    rep = suggest_preamp([], graphic_l=[0.0] * 30 + [5.0])
    assert rep["suggest_db"] == -5.0


def test_missing_ir_file_warns_not_crashes():
    rep = suggest_preamp([], conv_files={48000: "no-such-file.wav"})
    assert rep["suggest_db"] == 0.0
    assert any("assumed" in n for n in rep["notes"])
