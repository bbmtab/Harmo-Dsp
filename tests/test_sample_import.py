"""Import fidelity tests on the USER'S OWN sample files (fixtures)."""
import os

from harmo_dsp.io.presets import parse_rew_filter_settings, parse_peace_preset
from harmo_dsp.dsp.peq import band_to_line

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_filter")


def _read(name: str) -> str:
    with open(os.path.join(SAMPLE, name), encoding="utf-8-sig",
              errors="replace") as fh:
        return fh.read()


def test_rew_sample_parses_20_filters():
    bands, _ = parse_rew_filter_settings(_read("rew1.txt"))
    assert len(bands) == 20
    b = bands[0]
    assert (b.ftype, b.fc, b.gain, b.q) == ("PK", 72.1, -21.5, 2.0)
    # deep REW cuts survive (no ±15 clipping of data)
    assert band_to_line(b) == "Filter: ON PK Fc 72.1 Hz Gain -21.5 dB Q 2"


def test_peace_sample_parses_preamp_and_bands():
    data = parse_peace_preset(_read("rew1.peace"))
    assert data["preamp"] == -2.0
    assert len(data["bands"]) >= 20
    assert data["bands"][0] == (72.0, -21.5, 2.0)
    assert data["speakers"]["1"]["name"] == "Left"


def test_bw_oct_variant_converts():
    bands, notes = parse_rew_filter_settings(
        "Filter 1: ON PEQ Fc 100 Hz Gain 1.0 dB BW Oct 0.167\n")
    assert len(bands) == 1 and bands[0].ftype == "PK"
    assert abs(bands[0].q - 8.65) < 0.05
    assert any("BW Oct" in n for n in notes)
