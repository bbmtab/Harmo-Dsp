"""Importer + GEQ/PEQ core tests (synthetic data only)."""
from harmo_dsp.io.rew import parse_rew_text
from harmo_dsp.dsp.geq import ISO31, to_apo_graphic_eq
from harmo_dsp.dsp.peq import (
    PeqBand, default_bands, to_apo_filter_lines, build_speakercorrect,
)


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
        PeqBand(True, "HS", 8000, 2.5, 1.0),
        PeqBand(True, "HP", 30, 0, 1.0),
        PeqBand(False, "PK", 500, -6, 1.0),   # off -> skipped
        PeqBand(True, "PK", 1000, 0, 1.0),    # flat -> skipped
    ]
    lines = to_apo_filter_lines(bands)
    assert len(lines) == 3
    assert lines[0] == "Filter: ON PK Fc 1234.5 Hz Gain -3 dB Q 2"
    assert lines[1] == "Filter: ON HS Fc 8000 Hz Gain 2.5 dB"
    assert lines[2] == "Filter: ON HP Fc 30 Hz"


def test_apo_official_rules_no_gain_on_bp_no_ap():
    # Configuration reference: BP/NO/AP take NO gain parameter
    assert to_apo_filter_lines([PeqBand(True, "BP", 1000, 5, 1.0)]) == [
        "Filter: ON BP Fc 1000 Hz Q 1"]
    assert to_apo_filter_lines([PeqBand(True, "NO", 800, 5, 2.0)]) == [
        "Filter: ON NO Fc 800 Hz Q 2"]
    assert to_apo_filter_lines([PeqBand(True, "AP", 900, 5, 0.707)]) == [
        "Filter: ON AP Fc 900 Hz Q 0.707"]
    assert to_apo_filter_lines([PeqBand(True, "LS 12dB", 2000, -5, 1.0)]) == [
        "Filter: ON LS 12dB Fc 2000 Hz Gain -5 dB"]
    assert to_apo_filter_lines([PeqBand(True, "Modal", 100, 3, 5.41, 100)]) == [
        "Filter: ON Modal Fc 100 Hz Gain 3 dB Q 5.41 T60 target 100 ms"]


def test_speakercorrect_groups_channels_and_preamp():
    bands = [
        PeqBand(True, "PK", 100, -4, 2.0, 100.0, "L"),
        PeqBand(True, "PK", 100, -2, 2.0, 100.0, "all"),
    ]
    txt = build_speakercorrect(bands, preamp_db=-6.0)
    assert "Preamp: -6 dB" in txt
    assert "Channel: L" in txt and "Channel: R" in txt
    assert txt.count("Gain -4 dB") == 1  # L only
    assert txt.count("Gain -2 dB") == 2  # both blocks


def test_unified_band_detail_offscreen():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.graphic_eq import GraphicEQ

    QApplication.instance() or QApplication([])
    g = GraphicEQ()
    assert len(g.bands()) == 31
    # select band, edit type/Fc/Q below the sliders, read back
    g.select(12)
    g.d_type.setCurrentIndex(g.d_type.findData("NO"))
    g.d_fc.setValue(750.0)
    g.d_q.setValue(3.0)
    b = g.bands()[12]
    assert (b.ftype, b.fc, b.q) == ("NO", 750.0, 3.0)
    # preset round-trip keeps per-band detail
    rows = g.to_preset()
    g2 = GraphicEQ()
    g2.load_preset(rows)
    assert g2.bands()[12].ftype == "NO"
    g.close()
    g2.close()


def test_slider_drag_selects_band_synchronously():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.graphic_eq import GraphicEQ

    QApplication.instance() or QApplication([])
    g = GraphicEQ()
    assert g._sel == 12
    g._sliders[20].setValue(50)  # user drags the 2 kHz slider
    assert g._sel == 20  # detail panel followed immediately
    assert g.d_gain.value() == 5.0
    assert "2000" in g.sel_title.text()
    g.close()
