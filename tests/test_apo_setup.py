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


def test_commented_include_does_not_count_as_wired(tmp_path):
    # REGRESSION: a commented Include used to re-enable the chain silently
    (tmp_path / "config.txt").write_text(
        "# Include: speakercorrect.txt   <- disabled\n", encoding="utf-8")
    assert not S.include_active(S.read_config(str(tmp_path)))
    state, _ = S.status(str(tmp_path))
    assert state != "wired"
    # real Include counts
    (tmp_path / "config.txt").write_text(
        "Include: speakercorrect.txt\n", encoding="utf-8")
    assert S.include_active(S.read_config(str(tmp_path)))
    assert S.status(str(tmp_path))[0] == "wired"


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


def test_patch_config_after_peace_and_replace():
    new, after = S.build_patched_config(
        "Include: peace.txt\nInclude: speakercorrect.txt\nPreamp: 0 dB\n",
        "speakercorrect.txt")
    assert after is True
    assert new.count("Include: speakercorrect.txt") == 1
    assert new.index("peace.txt") < new.index("speakercorrect.txt")


def test_patch_config_append_and_harmo_variants():
    new, after = S.build_patched_config(
        "# cmt\nInclude: speakercorrect-old.txt\n", "speakercorrect.txt")
    assert after is False
    assert "speakercorrect-old" not in new
    assert new.rstrip().endswith("Include: speakercorrect.txt")


def test_writer_helper_patch_preview_on_tmp(tmp_path):
    import json
    import subprocess
    import sys
    (tmp_path / "config.txt").write_text("Preamp: -6 dB\n", encoding="utf-8")
    import os
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "tools", "write_apo.py")
    p = subprocess.run([sys.executable, helper, "--patch-preview",
                        str(tmp_path), "speakercorrect.txt"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-500:]
    res = json.loads(p.stdout)
    assert "Include: speakercorrect.txt" in res["patched"]
    assert res["after_peace"] is False


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
    import os
    cands = S.candidate_configurators(S.find_config_dir())
    assert cands and cands[0].endswith("Configurator.exe")
    if S.find_config_dir() is None:
        import pytest
        pytest.skip("APO not installed on this machine (e.g. CI runner)")
    assert os.path.isfile(cands[0])  # real machine, no launch performed
