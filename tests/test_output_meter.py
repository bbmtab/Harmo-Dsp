"""Output meter tests (pure math + offscreen widget, no audio needed)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_peak_to_db_math():
    from harmo_dsp.ui.monitor import peak_to_db
    assert peak_to_db(None) is None
    assert peak_to_db(0.0) is None
    assert abs(peak_to_db(1.0)) < 0.01
    assert abs(peak_to_db(0.5) - (-6.02)) < 0.01


def test_output_meter_none_and_fake_peak(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.monitor import OutputMeter
    from harmo_dsp.io import meter as M

    QApplication.instance() or QApplication([])
    m = OutputMeter()
    # REGRESSION FIX: no polling (and no loopback stream) until opt-in
    assert not m.timer.isActive()
    monkeypatch.setattr(M, "get_output_peak", lambda: None)
    m._tick()  # manual tick still safe when off
    assert m.db_label.text() == "— dB"
    m.btn.setChecked(True)  # user opts in -> polling starts
    assert m.timer.isActive()
    monkeypatch.setattr(M, "get_output_peak", lambda: 0.0)
    m._tick()
    assert m.db_label.text() == "silent"
    assert m._available_seen
    monkeypatch.setattr(M, "get_output_peak", lambda: 0.5)
    m._tick()
    assert m.db_label.text() == "-6.0 dB"
    assert m.bar.value() == -60
    monkeypatch.setattr(M, "get_output_peak", lambda: 1.0)  # clip
    m._tick()
    assert m.db_label.text() == "0.0 dB"
    m.close()


def test_meter_in_main_toolbar():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow

    QApplication.instance() or QApplication([])
    w = MainWindow()
    assert hasattr(w, "out_meter")
    assert not w.out_meter.timer.isActive()  # launch is audio-silent
    w.out_meter.btn.setChecked(True)
    w.out_meter._tick()
    w.close()
