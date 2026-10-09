"""Guided-measurement + time-alignment tests (synthetic only, no hardware)."""
import numpy as np

from harmo_dsp.dsp.measure import log_sweep, deconvolve, level_dbfs, level_verdict
from harmo_dsp.dsp.align import onset_index, estimate_delays, align_delays
from harmo_dsp.io.audio import available


def test_sweep_roundtrip_recovers_ir():
    from scipy.signal import lfilter
    from numpy.fft import rfft, rfftfreq
    from harmo_dsp.dsp.clip_guard import _rbj
    fs = 8000
    sw = log_sweep(fs, 1.0)
    b, a = _rbj("PK", 500, 6.0, 2.0, fs)
    ir_true = lfilter(b, a, np.concatenate([np.ones(1), np.zeros(511)]))
    rec = np.convolve(sw, ir_true)
    ir = deconvolve(rec, sw, fs, ir_len=512)
    # in-band (the sweep band) complex response must match; out-of-band
    # content legitimately differs (band-limited measurement physics)
    f = rfftfreq(4096, 1.0 / fs)
    H = rfft(ir, 4096)
    T = rfft(ir_true, 4096)
    m = (f >= 100) & (f <= 3000)
    num = np.abs(np.vdot(H[m], T[m]))
    assert num / (np.linalg.norm(H[m]) * np.linalg.norm(T[m])) > 0.999
    db = 20 * np.log10(np.abs(H[m]) / np.maximum(np.abs(T[m]), 1e-12))
    assert float(np.sqrt(np.mean((db - db.mean()) ** 2))) < 0.5


def test_levels_and_verdict():
    x = np.zeros(1000)
    x[0] = 0.5
    pk, rms = level_dbfs(x)
    assert abs(pk - (-6.02)) < 0.05
    assert "OK" in level_verdict(pk, rms)
    assert "LOUD" in level_verdict(-0.5, -3.0)
    assert "QUIET" in level_verdict(-30.0, -40.0)


def test_onset_and_align():
    fs = 8000
    base = np.zeros(2000)
    base[100] = 1.0
    base[101] = 0.5
    late = np.concatenate([np.zeros(40), base])[:2000]
    assert onset_index(base, fs) <= 100
    assert onset_index(late, fs) == onset_index(base, fs) + 40
    rel = estimate_delays({"L": (fs, base), "R": (fs, late)})
    assert rel["L"] == 0.0
    assert abs(rel["R"] - 5.0) < 0.01  # 40 samples @8k = 5 ms
    apo = align_delays({"L": (fs, base), "R": (fs, late)})
    assert apo == {"L": 5.0, "R": 0.0}  # early channel delayed to latest
    try:
        estimate_delays({"L": (fs, base), "R": (44100, base)})
        raise SystemExit("should have raised")
    except ValueError:
        pass


def test_audio_backend_optional():
    assert isinstance(available(), bool)  # must not raise without hardware
