"""Response-curve math + monitor widgets + preamp switch (offscreen)."""
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.dsp.clip_guard import chain_response_db, graphic_curve_db
from harmo_dsp.dsp.peq import PeqBand
from harmo_dsp.ui.monitor import SpectrumEngine, LiveSpectrum, PredictedCurve

GRID = np.logspace(np.log10(20.0), np.log10(20000.0), 200)


def test_chain_response_matches_biquad():
    y = chain_response_db([PeqBand(True, "PK", 1000, 6.0, 1.0)], GRID)
    i = int(np.argmin(np.abs(GRID - 1000)))
    assert abs(y[i] - 6.0) < 0.3
    assert abs(y[0]) < 1.0 and abs(y[-1]) < 1.0  # peak shape, flat far away


def test_chain_response_flat_and_channel_scope():
    assert np.abs(chain_response_db([], GRID)).max() == 0.0
    y = chain_response_db([PeqBand(True, "PK", 1000, 6.0, 1.0, 100.0, "L")],
                          GRID, scope="R")
    assert np.abs(y).max() < 0.01  # L-only band invisible on R


def test_graphic_curve_exact_points_and_log_interp():
    g = [0.0] * 31
    g[17] = 6.0  # 1000 Hz band
    y = graphic_curve_db(g, np.array([1000.0, 20.0, 20000.0]))
    assert abs(y[0] - 6.0) < 1e-9
    assert y[1] == 0.0 and y[2] == 0.0  # flat outside outer bands


def test_spectrum_engine_finds_tone():
    eng = SpectrumEngine(fs=48000)
    t = np.arange(48000) / 48000.0
    eng.feed((0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float64))
    f, db = eng.spectrum_db()
    peak_f = f[int(np.argmax(db))]
    assert abs(peak_f - 1000) / 1000 < 0.05


def test_monitor_widgets_construct_offscreen():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    mon = LiveSpectrum()
    assert mon is not None
    pc = PredictedCurve()
    pc.set_bands([PeqBand(True, "PK", 1000, 6.0, 1.0)])
    mon.close()
    pc.close()


def test_preamp_slider_and_switch():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.pages import FineTunePage
    QApplication.instance() or QApplication([])
    p = FineTunePage()
    assert p.btn_clip.isChecked()  # safe by default
    assert p.preamp.isEnabled() and p.preamp_slider.isEnabled()  # never locked
    p.preamp_slider.setValue(-1)  # programmatic nudge allowed
    p.btn_clip.setChecked(False)
    p.preamp_slider.setValue(-100)
    assert abs(p.preamp.value() - (-10.0)) < 1e-9  # slider <-> spin sync
    p.btn_clip.setChecked(True)
    assert p.preamp.value() == -10.0  # flat needs 0, safer manual -10 kept
    # anti-clip only pulls DOWN, never pushes up past a safer manual value
    p.preamp_slider.setValue(-120)  # user pins -12 dB manually
    p.geq._sliders[17].setValue(60)  # +6 dB boost needs only -6
    assert p.preamp.value() == -12.0  # manual safer value respected
    p.close()


def test_predicted_curve_includes_preamp():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.monitor import PredictedCurve, LOG_GRID
    QApplication.instance() or QApplication([])
    pc = PredictedCurve()
    pc.set_bands([], preamp_db=-10.0)
    import numpy as np
    _, y = pc.curve.getData()
    assert abs(float(np.mean(y)) - (-10.0)) < 0.5
    pc.close()


def test_guard_pull_is_announced():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.pages import FineTunePage
    QApplication.instance() or QApplication([])
    p = FineTunePage()
    p.preamp_slider.setValue(-50)  # real manual move
    assert p.preamp_note.text() == "manual"
    p.preamp_slider.setValue(0)  # back to 0 dB by hand
    p.geq._sliders[17].setValue(120)  # +12 dB boost -> guard must pull
    assert p.preamp.value() <= -11.9
    assert "guard pulled" in p.preamp_note.text()
    p.close()


def test_bypass_renders_bit_transparent():
    from PySide6.QtWidgets import QApplication
    from harmo_dsp.ui.main_window import MainWindow
    from harmo_dsp.dsp.apo_config import render_speakercorrect
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.page_tune.geq._sliders[17].setValue(60)
    w.page_tune.btn_ab.setChecked(True)
    txt = render_speakercorrect(w.page_export._collect_output())
    assert "Filter:" not in txt and "GraphicEQ:" not in txt
    assert "Preamp: 0 dB" in txt
    w.page_tune.btn_ab.setChecked(False)
    txt2 = render_speakercorrect(w.page_export._collect_output())
    assert "Filter:" in txt2 or "GraphicEQ:" in txt2  # session kept, restored
    w.close()
