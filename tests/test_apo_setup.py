"""APO setup states (tmp dirs stand in for the APO config dir)."""
from harmo_dsp.dsp import apo_setup as S


def test_missing_dir():
    assert S.find_config_dir(["/no/such/dir"]) is None
    state, msg = S.status(None)
    assert state == "missing" and "Install" in msg


def test_idle_comment_only_config(tmp_path):
    (tmp_path / "config.txt").write_text(
        "# Convolution: old-filters-48k.wav\n", encoding="utf-8")
    assert S.find_config_dir([str(tmp_path)]) == str(tmp_path)
    state, msg = S.status(str(tmp_path))
    assert state == "idle" and "Configurator" in msg


def test_wired_and_peace_states(tmp_path):
    (tmp_path / "config.txt").write_text(
        "Include: peace.txt\nInclude: speakercorrect.txt\n", encoding="utf-8")
    assert S.status(str(tmp_path))[0] == "wired"
    (tmp_path / "config.txt").write_text("Include: peace.txt\n", encoding="utf-8")
    assert S.status(str(tmp_path))[0] == "peace-idle"
    (tmp_path / "config.txt").write_text("Preamp: -6 dB\n", encoding="utf-8")
    assert S.status(str(tmp_path))[0] == "idle"


def test_official_url_is_sourceforge():
    assert S.OFFICIAL_URL.startswith("https://sourceforge.net/projects/equalizerapo")


def test_configurator_candidates_resolve_to_real_exe():
    cands = S.candidate_configurators(S.find_config_dir())
    assert cands and cands[0].endswith("Configurator.exe")
    import os
    assert os.path.isfile(cands[0])  # real machine, no launch performed
