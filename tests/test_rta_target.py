"""RTA + target + conv-switch tests (offscreen, no audio device)."""
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.dsp.target import target_curve_db, preset_curve, PRESETS


def test_target_flat_and_bass_shelf():
    f = np.array([20.0, 60.0, 150.0, 1000.0, 8000.0])
    flat = target_curve_db(f)
    assert np.abs(flat).max() < 1e-9
    bass = target_curve_db(f, bass_db=6.0, corner_hz=150.0)
    assert abs(bass[0] - 6.0) < 0.01      # well below corner
    assert abs(bass[4]) < 0.01            # well above corner
    assert bass[2] < 3.1                  # at corner: half-ish


def test_target_tilt_rises_toward_bass():
    f = np.array([40.0, 1000.0, 8000.0])
    y = target_curve_db(f, tilt_db_per_oct=-0.5)
    assert abs(y[1]) < 1e-9               # 0 dB @ 1 kHz anchor
    assert y[0] > 2.0                     # ~+3.7 dB at 40 Hz
    assert y[2] < -1.0                    # treble below anchor


def test_preset_lookup_all_shapes():
    f = np.logspace(1, 4, 60)
    for name in PRESETS:
        y = preset_curve(f, name)
        assert len(y) == len(f)
    assert "bass+3@80" in PRESETS and "bass+3 tilt-0.5@80" in PRESETS


def test_ring_buffer_wraparound():
    from harmo_dsp.io.meter import RingBuffer
    r = RingBuffer(100)
    r.write(np.arange(250, dtype=np.float32))  # long write -> tail kept
    out = r.recent(10)
    assert out[0] == 240 and out[-1] == 249
    r.write(np.array([1.0, 2.0, 3.0]))
    out = r.recent(3)
    assert list(out) == [1.0, 2.0, 3.0]
    r.write(np.arange(99, dtype=np.float32))    # exact fill, wraps to 0
    out = r.recent(2)
    assert list(out) == [97.0, 98.0]


def test_rta_panel_constructs_and_set_chain():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.monitor import RtaPanel
    from harmo_dsp.dsp.peq import PeqBand

    QApplication.instance() or QApplication([])
    p = RtaPanel()
    p.set_chain([PeqBand(True, "PK", 55, -4, 2.0)], preamp=-2.0)
    p.set_chain([], 0.0)
    p._redraw_target()  # preset switch redraws guide
    p.close()


def test_conv_switch_mutes_line_but_keeps_path():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow
    from harmo_dsp.dsp.apo_config import render_speakercorrect

    QApplication.instance() or QApplication([])
    import numpy as np
    import tempfile
    from scipy.io.wavfile import write as wavwrite
    fd = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavwrite(fd.name, 48000, np.zeros(256, dtype=np.float32))
    fd.close()
    try:
        w = MainWindow()
        w.page_export.conv_edit.setText(fd.name)
        assert w.page_export.conv_on.isChecked()
        txt_on = render_speakercorrect(w.page_export._collect_output())
        assert "Convolution:" in txt_on
        w.page_export.conv_on.setChecked(False)  # A/B the rePhase file
        txt_off = render_speakercorrect(w.page_export._collect_output())
        assert "Convolution:" not in txt_off
        assert w.page_export.conv_edit.text() == fd.name  # path kept
        w.close()
    finally:
        os.unlink(fd.name)
