"""Live mode: debounced auto-write into the APO dir (tmp stand-in)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _pages():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    return w, w.page_tune, w.page_export


def test_live_write_and_silent_without_live(tmp_path):
    w, tune, exp = _pages()
    exp._apo_dir = str(tmp_path)  # stand-in APO dir (writable, no admin)
    ok, _ = exp.live_capable()
    assert ok
    # Live OFF: edits must NOT write
    tune.geq._sliders[17].setValue(60)
    assert not (tmp_path / "speakercorrect.txt").exists()
    # Live ON path without the one-time setup dialogs: flip flag silently
    tune.btn_live.blockSignals(True)
    tune.btn_live.setChecked(True)
    tune.btn_live.blockSignals(False)
    tune._fire_live_write()
    txt = (tmp_path / "speakercorrect.txt").read_text(encoding="utf-8")
    assert "GraphicEQ:" in txt or "Filter:" in txt or "Preamp:" in txt
    w.close()


def test_live_capable_reports_reason(tmp_path):
    w, _, exp = _pages()
    exp._apo_dir = str(tmp_path / "missing")
    ok, reason = exp.live_capable()
    assert not ok and reason
    w.close()


def test_conv_off_clears_field_and_session_fir():
    w, _, exp = _pages()
    exp.conv_edit.setText("C:\\fir.wav")
    w.session["fir"] = {"L": "C:\\fir.wav"}
    exp._clear_conv()
    assert exp.conv_edit.text() == ""
    assert w.session["fir"] == {}
    w.close()


def test_preamp_move_and_bypass_go_live(tmp_path):
    w, tune, exp = _pages()
    exp._apo_dir = str(tmp_path)
    tune.btn_live.blockSignals(True)
    tune.btn_live.setChecked(True)
    tune.btn_live.blockSignals(False)
    # preamp move must schedule a live write (was: sliders only)
    tune.preamp_slider.setValue(-100)
    assert tune._live_timer is not None and tune._live_timer.isActive()
    tune._fire_live_write()
    txt = (tmp_path / "speakercorrect.txt").read_text(encoding="utf-8")
    assert "Preamp: -10 dB" in txt
    assert "synced" in tune.disk_label.text()
    # bypass must render flat through the same live path
    tune.btn_ab.setChecked(True)
    tune._fire_live_write()
    txt2 = (tmp_path / "speakercorrect.txt").read_text(encoding="utf-8")
    assert "Filter:" not in txt2 and "Preamp: 0 dB" in txt2
    w.close()


def test_live_auto_enables_when_wired(tmp_path, monkeypatch):
    w, tune, exp = _pages()
    exp._apo_dir = str(tmp_path)
    (tmp_path / "config.txt").write_text(
        "Include: speakercorrect.txt\n", encoding="utf-8")
    monkeypatch.delenv("HARMO_NO_AUTOLIVE", raising=False)
    tune.auto_enable_live()
    assert tune.btn_live.isChecked()  # silent: Include already present
    w.close()


def test_disk_label_marks_outdated(tmp_path):
    w, tune, exp = _pages()
    exp._apo_dir = str(tmp_path)
    tune.geq._sliders[5].setValue(30)
    assert "outdated" in tune.disk_label.text()
    w.close()


def test_include_idempotent():
    from harmo_dsp.dsp.apo_setup import build_patched_config
    cur = "# Convolution: Agu 31 20_51_21-filters-48k.wav\nInclude: speakercorrect.txt\n"
    new, _ = build_patched_config(cur, "speakercorrect.txt")
    assert new.strip() == cur.strip()  # no dialog needed, nothing changes
