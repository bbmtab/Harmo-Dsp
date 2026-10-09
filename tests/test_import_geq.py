"""Importer + GEQ/PEQ core tests (synthetic data only)."""
from harmo_dsp.io.rew import parse_rew_text
from harmo_dsp.dsp.geq import ISO31, to_apo_graphic_eq
from harmo_dsp.dsp.peq import PeqBand, default_bands, to_apo_filter_lines


def test_parse_space_separated_with_header():
    txt = "* REW export\nFreq SPL\n20 78.5\n100 80.1\n1000 75.0\n"
    m = parse_rew_text(txt, "syn")
    assert len(m) == 3
    assert m.frequencies[0] == 20
    assert m.phase is None


def test_parse_comma_decimal_and_phase():
    txt = "20,5; 78,2; -12,0\n100; 80,1; 5,5\n"
    m = parse_rew_text(txt, "syn")
    assert abs(m.frequencies[0] - 20.5) < 1e-9
    assert m.phase is not None
    assert len(m.phase) == 2


def test_geq_has_31_iso_bands_and_apo_line():
    assert len(ISO31) == 31
    assert ISO31[0] == 20 and ISO31[-1] == 20000
    line = to_apo_graphic_eq([0.0] * 31)
    assert line.startswith("GraphicEQ:")
    assert "1000 0" in line
    line_l = to_apo_graphic_eq([0.0] * 31, channel="L")
    assert line_l.startswith("Channel: L GraphicEQ:")


def test_peq_filter_lines_with_types_and_free_fc():
    bands = [
        PeqBand(True, "PK", 1234.5, -3.0, 2.0),
        PeqBand(True, "HSC", 8000, 2.5, 1.0),
        PeqBand(True, "HP", 30, 0, 1.0),
        PeqBand(False, "PK", 500, -6, 1.0),   # off -> skipped
        PeqBand(True, "PK", 1000, 0, 1.0),    # flat -> skipped
    ]
    lines = to_apo_filter_lines(bands)
    assert len(lines) == 3
    assert lines[0] == "Filter: ON PK Fc 1234.5 Hz Gain -3 dB Q 2"
    assert "HSC" in lines[1] and "8000" in lines[1]
    assert lines[2] == "Filter: ON HP Fc 30 Hz"


def test_parametric_table_roundtrip_offscreen():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.parametric import ParametricTable

    QApplication.instance() or QApplication([])
    t = ParametricTable(n_rows=3)
    assert len(t.bands()) == 3
    assert len(default_bands(10)) == 10
