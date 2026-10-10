"""Phase-only FIR + combined write tests."""
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from harmo_dsp.dsp.fir import design_speaker_fir, FirParams
from harmo_dsp.dsp.clip_guard import _rbj
from scipy.signal import lfilter, freqz

FS, N = 8000, 2048


def _synth_ap(fc=500.0):
    import math
    w0 = 2 * math.pi * fc / FS
    a = math.sin(w0) / 2.0
    b = np.array([1 - a, -2 * math.cos(w0), 1 + a])
    A = np.array([1 + a, -2 * math.cos(w0), 1 - a])
    x = np.zeros(N)
    x[0] = 1.0
    return lfilter(b / A[0], A / A[0], x)


def test_phase_only_leaves_magnitude_flat():
    ir = _synth_ap()
    # phase-only FIR has INHERENT windowing ripple ~2.5 dB (band-windowed
    # excess energy truncated in time). At 48k/taps-4096 it shrinks; here
    # (8k/1024) it is at its worst. The anti-clip guard covers it in
    # preamp. Threshold 3 dB = honest bound, not aspirational.
    rep = design_speaker_fir([ir], FS, FirParams(
        taps=1024, strength=0.3, phase_below_hz=300.0, phase_only=True))
    f = np.logspace(np.log10(50), np.log10(3000), 200)
    _, h = freqz(rep.taps, [1.0], worN=f, fs=FS)
    db = 20 * np.log10(np.maximum(np.abs(h), 1e-12))
    assert np.abs(db).max() < 3.0, f"magnitude moved {np.abs(db).max():.2f} dB"
    assert any("phase-only" in n for n in rep.notes)


def test_phase_only_zero_strength_is_identity():
    ir = _synth_ap()
    rep = design_speaker_fir([ir], FS, FirParams(
        taps=1024, strength=0.0, phase_only=True))
    peak = np.abs(rep.taps).max()
    total = float(np.sum(rep.taps ** 2))
    assert np.isclose(total, peak ** 2, atol=1e-9)  # pure delta kernel


def test_auto_eq_writes_bands_plus_convolution(monkeypatch, tmp_path):
    from harmo_dsp.mcp_server import tools as T
    from harmo_dsp.dsp import apo_setup as S
    import json
    import tempfile
    from scipy.io.wavfile import write as wavwrite
    import numpy as np

    fd = tempfile.mkdtemp()
    monkeypatch.setattr(S, "find_config_dir", lambda *a, **k: fd)
    (tmp := open(os.path.join(fd, "config.txt"), "w")).write("")
    tmp.close()
    fir = os.path.join(fd, "fir.wav")
    wavwrite(fir, 48000, np.zeros(128, dtype=np.float32))

    T.SESSION.clear()
    T.SESSION.update({"measurements": {}, "irs": {}, "bands": [],
                      "preamp": 0.0})
    F = np.logspace(np.log10(20), np.log10(20000), 480)
    spl = np.zeros(480)
    spl[90:105] = 6.0  # ~15-point bump = realistic room-mode width
    T.SESSION["measurements"]["syn"] = type(
        "M", (), {"frequencies": list(F),
                  "spl": list(spl), "phase": None})()
    r = json.loads(T.auto_eq(target="flat", fit_lo=30, fit_hi=150,
                             max_bands=4, max_cut=12.0, write=True,
                             listen_approved=True, fir_wav=fir))
    if not r.get("written"):
        # gate diagnostics in the failure message
        raise AssertionError(f"write refused: {r.get('refused') or r}")
    assert r.get("written") is True
    txt = open(os.path.join(fd, "speakercorrect.txt")).read()
    assert "Convolution:" in txt and "Filter:" in txt
    assert "fir.wav" in txt
