"""Phase-correction acceptance tests (brief criteria a–e, synthetic only)."""
import math
import numpy as np
from scipy.signal import lfilter, group_delay

from harmo_dsp.dsp.fir import design_speaker_fir, FirParams
from harmo_dsp.dsp.clip_guard import _rbj

FS = 8000
N = 2048


def _synth_allpass(fc: float, q: float, fs: float):
    """RBJ all-pass (analysis _rbj skips AP: magnitude-flat by definition)."""
    w0 = 2.0 * math.pi * fc / fs
    alpha = math.sin(w0) / (2.0 * max(q, 1e-4))
    cw = math.cos(w0)
    b = np.array([1 - alpha, -2 * cw, 1 + alpha])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def synth(sections, delay=0):
    """Cascade second-order sections (each (type, fc, gain, q)) + bulk delay."""
    x = np.zeros(N)
    x[0] = 1.0
    for ftype, fc, g, q in sections:
        coef = _synth_allpass(fc, q, FS) if ftype == "AP" else _rbj(ftype, fc, g, q, FS)
        assert coef is not None
        x = lfilter(coef[0], coef[1], x)
    if delay:
        x = np.concatenate([np.zeros(delay), x])[:N]
    return x


def rms_dev_db(h, f_lo=50.0, f_hi=2000.0):
    from numpy.fft import rfft, rfftfreq
    H = np.abs(rfft(h, 8192))
    f = rfftfreq(8192, 1.0 / FS)
    m = (f >= f_lo) & (f <= f_hi)
    db = 20 * np.log10(np.maximum(H[m], 1e-12))
    return float(np.sqrt(np.mean((db - db.mean()) ** 2)))


def gd_dev(h, f_lo=100.0, f_hi=1000.0):
    f = np.linspace(f_lo, f_hi, 64)
    _, gd = group_delay((h, 1.0), w=f, fs=FS)
    gd = np.asarray(gd, dtype=float)
    gd = gd[np.isfinite(gd)]
    return float(np.sqrt(np.mean((gd - np.median(gd)) ** 2)))


def test_a_group_delay_down_50pct():
    spk = synth([("AP", 500, 0, 1.0)], delay=30)
    before = gd_dev(spk)
    rep = design_speaker_fir([spk], FS, FirParams(taps=1024, strength=1.0,
                                                  phase_below_hz=2000.0))
    fixed = np.convolve(spk, rep.taps)[:N]
    after = gd_dev(fixed)
    assert before > 0, "synthetic must have GD deviation to fix"
    assert (1.0 - after / before) >= 0.5, f"{before=} {after=}"


def test_b_minphase_resonance_decays_faster():
    spk = synth([("PK", 80, 12.0, 4.0)])
    rep = design_speaker_fir([spk], FS, FirParams(taps=1024, strength=0.0))
    fixed = np.convolve(spk, rep.taps)[:N]
    late = slice(int(0.08 * FS), N)
    r_before = np.sum(spk[late] ** 2) / (np.sum(spk ** 2) + 1e-18)
    r_after = np.sum(fixed[late] ** 2) / (np.sum(fixed ** 2) + 1e-18)
    assert r_after < 0.5 * r_before, f"{r_before=} {r_after=}"


def test_c_strength_zero_is_minphase_path():
    from harmo_dsp.dsp.fir import design_mag_only, rfftfreqs, _next_pow2
    spk = synth([("PK", 120, 8.0, 2.0)])
    p = FirParams(taps=1024, strength=0.0)
    rep = design_speaker_fir([spk], FS, p)
    n = _next_pow2(len(spk) * 2)
    x = np.zeros(n)
    x[:len(spk)] = spk
    mag = np.abs(np.fft.rfft(x))
    w = np.ones_like(mag)
    ref = design_mag_only(mag, n, FS, p, w)
    assert np.array_equal(rep.taps, ref)


def test_d_latency_matches_independent_calc():
    spk = synth([("PK", 120, 8.0, 2.0), ("AP", 400, 0, 1.0)], delay=10)
    rep = design_speaker_fir([spk], FS, FirParams(taps=1024, strength=0.5))
    expect = int(np.argmax(np.abs(rep.taps))) / FS * 1000.0
    assert abs(rep.latency_ms - expect) < 1e-9
    assert rep.pre_ring_db < -10.0, f"pre-ring too hot: {rep.pre_ring_db}"


def test_e_multiposition_not_worsened():
    shared = [("PK", 100, 8.0, 2.0)]
    p1 = synth(shared + [("NO", 200, 0, 8.0)])
    p2 = synth(shared + [("NO", 300, 0, 8.0)])
    rep = design_speaker_fir([p1, p2], FS, FirParams(taps=1024, strength=0.5,
                                                     phase_below_hz=250.0))
    for p in (p1, p2):
        before = rms_dev_db(p)
        after = rms_dev_db(np.convolve(p, rep.taps)[:N])
        assert after <= before + 1.0, f"worsened: {before=} {after=}"
    # shared peak region improves on both
    for p in (p1, p2):
        before = rms_dev_db(p, 80.0, 120.0)
        after = rms_dev_db(np.convolve(p, rep.taps)[:N], 80.0, 120.0)
        assert after < before, f"shared peak not fixed: {before=} {after=}"
    print(f"e-report pre-ring {rep.pre_ring_db:.1f} dB latency {rep.latency_ms:.2f} ms")
