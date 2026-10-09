"""Importer + GEQ core tests (synthetic data only)."""
from harmo_dsp.io.rew import parse_rew_text
from harmo_dsp.dsp.geq import ISO31, to_apo_graphic_eq


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
