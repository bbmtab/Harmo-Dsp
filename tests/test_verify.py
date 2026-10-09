"""Verify audits: stacking, dormant convolutions, include resolution."""
from harmo_dsp.dsp.apo_semantics import verify


def test_stacked_convolutions_warn_same_channel_only():
    stacked = ("Channel: L\nConvolution: old.wav\nConvolution: new.wav\n"
               "Channel: R\nConvolution: new.wav\n")
    res = verify(stacked)
    assert any("2 active Convolutions" in w for w in res.warnings)
    assert not any(w.startswith("Channel R:") and "Convolution" in w
                   for w in res.warnings)


def test_dormant_commented_convolution_noted():
    res = verify("# Convolution: Agu 31 20_51_21-filters-48k.wav\nPreamp: 0 dB\n")
    assert any("Dormant" in i for i in res.infos)
    assert not any("Convolution" in w for w in res.warnings)


def test_include_resolution_sees_stacking(tmp_path):
    (tmp_path / "old.wav").write_bytes(b"RIFF....")
    (tmp_path / "ours.txt").write_text("Convolution: new.wav\n", encoding="utf-8")
    (tmp_path / "config.txt").write_text(
        "Convolution: old.wav\nInclude: ours.txt\n", encoding="utf-8")
    res = verify((tmp_path / "config.txt").read_text(encoding="utf-8"),
                 base_dir=str(tmp_path))
    assert any("2 active Convolutions" in w for w in res.warnings)
