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


def test_registration_check_against_hkcu_sandbox():
    import winreg
    from harmo_dsp.dsp import apo_attach as A
    root = r"Software\HarmoDspTest\Classes"
    for guid in (A.PRE_MIX.strip("{}"), A.POST_MIX.strip("{}")):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              f"{root}\\AudioEngine\\AudioProcessingObjects\\{{{guid}}}"):
            pass
    try:
        assert S.apo_registration_ok(winreg.HKEY_CURRENT_USER, root) == (True, True)
        assert S.apo_registration_ok(winreg.HKEY_CURRENT_USER,
                                      root + r"\Nope") == (False, False)
    finally:
        import shutil  # best-effort cleanup (registry has no rmtree)
        for guid in (A.PRE_MIX.strip("{}"), A.POST_MIX.strip("{}")):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                 f"{root}\\AudioEngine\\AudioProcessingObjects\\{{{guid}}}")
            except OSError:
                pass


def test_full_report_shape_machine_independent():
    rep = S.full_report()
    assert set(rep) >= {"installed_version", "reg_pre", "reg_post",
                        "devices", "attached", "config_state", "lines"}
    assert isinstance(rep["lines"], list) and len(rep["lines"]) == 4


def test_configurator_candidates_resolve_to_real_exe():
    cands = S.candidate_configurators(S.find_config_dir())
    assert cands and cands[0].endswith("Configurator.exe")
    import os
    assert os.path.isfile(cands[0])  # real machine, no launch performed
