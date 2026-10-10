"""Plain tool functions + session state (import-safe without fastmcp).

Every heavy import happens INSIDE the function so this module (and its
tests) never pull Qt or audio backends at import time.
"""
from __future__ import annotations
import json

SESSION: dict = {"measurements": {}, "irs": {}, "bands": [], "preamp": 0.0}


def _j(obj) -> str:
    return json.dumps(obj, indent=1, default=str)


def check_backend() -> str:
    versions = {}
    for mod in ("numpy", "scipy", "sounddevice", "pyaudiowpatch"):
        try:
            m = __import__(mod)
            versions[mod] = getattr(m, "__version__", "?")
        except ImportError:
            versions[mod] = "missing"
    try:
        from ..dsp.apo_setup import full_report
        rep = full_report()
        apo = rep["lines"]
    except Exception as e:
        apo = [f"APO check failed: {e}"]
    try:
        from ..io.meter import get_output_peak
        peak = get_output_peak()
        meter = ("off" if peak is None
                 else ("silent" if peak == 0.0 else f"{peak:.4f}"))
    except Exception:
        meter = "off"
    return _j({"versions": versions, "apo": apo, "output_meter": meter,
               "note": "Headless Harmo-Dsp core. All processing local."})


def list_audio_devices() -> str:
    from ..io.audio import available, devices
    if not available():
        return _j({"error": "No audio backend (pip install pyaudiowpatch "
                           "or sounddevice)."})
    outs, ins = devices()
    return _j({"outputs": outs, "inputs": ins,
               "hint": "Labels are 'index: name' — pass them verbatim to "
                       "measure_sweep."})


def get_output_meter() -> str:
    try:
        from ..io.meter import get_output_peak
        import math
        peak = get_output_peak()
        if peak is None:
            return _j({"status": "unavailable"})
        if peak <= 0.0:
            return _j({"status": "silent", "peak": 0.0, "db": None})
        return _j({"status": "live", "peak": round(peak, 5),
                   "db": round(20 * math.log10(peak), 2)})
    except Exception as e:
        return _j({"status": "error", "error": str(e)})


def import_measurement(path: str, name: str = "") -> str:
    """Auto-sniff: REW filter-settings / freq-response txt-frd / Peace
    .peace / impulse .wav. Stores into the session, returns a summary."""
    import os
    label = name or os.path.splitext(os.path.basename(path))[0]
    low = path.lower()
    try:
        if low.endswith(".wav"):
            from ..io.irwav import load_ir_mono
            fs, x = load_ir_mono(path)
            n = len(SESSION["irs"])
            SESSION["irs"][f"{label}#{n}"] = (fs, x)
            return _j({"kind": "impulse", "name": label, "fs": fs,
                       "samples": len(x),
                       "note": "IR stored; time_align/design_fir unlocked."})
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
        # 1) REW filter settings ("Filter  1: ON  PK ...")
        if "filter settings file" in text.lower() or "filter" in text.lower():
            try:
                from ..io.presets import parse_rew_filter_settings
                bands, notes = parse_rew_filter_settings(text)
                SESSION["bands"] = bands
                return _j({"kind": "rew-filters", "name": label,
                            "bands": len(bands), "notes": notes,
                            "note": "Bands loaded into session EQ "
                                    "(get_eq/set_eq)."})
            except ValueError:
                pass
        # 2) Peace preset ([Sections] INI)
        if "[" in text and "]" in text and "Frequency" in text:
            from ..io.presets import parse_peace_preset
            from ..dsp.peq import PeqBand
            data = parse_peace_preset(text)
            SESSION["bands"] = [PeqBand(True, "PK", f, g, q)
                                for f, g, q in data["bands"]]
            SESSION["preamp"] = data["preamp"]
            return _j({"kind": "peace-preset", "name": label,
                        "bands": len(SESSION["bands"]),
                        "preamp": data["preamp"]})
        # 3) frequency response columns
        from ..io.rew import parse_rew_text
        m = parse_rew_text(text, label)
        SESSION["measurements"][label] = m
        return _j({"kind": "freq-response", "name": label,
                    "points": len(m),
                    "range_hz": [m.frequencies[0], m.frequencies[-1]],
                    "spl_min": min(m.spl), "spl_max": max(m.spl),
                    "has_phase": m.phase is not None,
                    "note": "Analyze with analyze_measurement."})
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}",
                   "hint": "Supported: REW filter-settings txt, freq txt/frd, "
                           "Peace .peace, IR .wav (16/24/32/float)."})


def _smooth(y, k: int = 5):
    import numpy as np
    if len(y) < k * 2:
        return list(y)
    arr = np.convolve(np.asarray(y, dtype=float), np.ones(k) / k, mode="same")
    return list(arr)


def analyze_measurement(name: str) -> str:
    m = SESSION["measurements"].get(name)
    if m is None:
        return _j({"error": "no such measurement; import first",
                   "have": list(SESSION["measurements"])})
    import numpy as np
    f = np.asarray(m.frequencies)
    y = np.asarray(_smooth(m.spl, 5))
    half = 4
    peaks, dips = [], []
    for i in range(half, len(f) - half):
        seg = y[i - half:i + half + 1]
        if y[i] == seg.max() and y[i] > seg.min() + 1.0:
            peaks.append((float(f[i]), float(y[i])))
        if y[i] == seg.min() and seg.max() > y[i] + 1.0:
            dips.append((float(f[i]), float(y[i])))
    peaks = sorted(peaks, key=lambda t: -t[1])[:5]
    dips = sorted(dips, key=lambda t: t[1])[:5]
    hints = []
    for fq, db in peaks:
        if fq < 300 and db > 3:
            hints.append(f"{fq:.0f} Hz +{db:.1f} dB — likely room mode "
                         f"(5th-length mode ≈ {343/(2*fq):.1f} m room dimension)")
    for fq, db in dips:
        if fq < 300 and db < -6:
            hints.append(f"{fq:.0f} Hz {db:.1f} dB — deep null; do NOT boost "
                         "(nulls move with mic position)")
    return _j({"name": name, "points": len(f),
               "range": [float(f[0]), float(f[-1])],
               "avg_spl": round(float(np.mean(m.spl)), 1),
               "top_peaks": [{"hz": h, "db": d} for h, d in peaks],
               "deepest_dips": [{"hz": h, "db": d} for h, d in dips],
               "interpretation": hints})


def get_eq() -> str:
    return _j({"preamp": SESSION["preamp"],
               "bands": [b.__dict__ for b in SESSION["bands"]]})


def set_eq(bands: list[dict], preamp: float = 0.0,
           write: bool = False) -> str:
    from ..dsp.peq import PeqBand
    parsed = []
    for d in bands:
        b = PeqBand(**{k: d.get(k, v) for k, v in
                       PeqBand().__dict__.items()}).clipped()
        parsed.append(b)
    SESSION["bands"] = parsed
    SESSION["preamp"] = max(-30.0, min(30.0, float(preamp)))
    from ..dsp.peq import build_speakercorrect
    preview = build_speakercorrect(parsed, SESSION["preamp"])
    if not write:
        return _j({"written": False, "preview": preview,
                   "note": "Pass write=true to apply to Equalizer APO."})
    import os
    from ..dsp.apo_setup import find_config_dir, build_patched_config
    d = find_config_dir()
    if not d:
        return _j({"error": "APO config dir not found",
                   "preview": preview})
    try:
        with open(os.path.join(d, "speakercorrect.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(preview)
        cfg = os.path.join(d, "config.txt")
        cur = open(cfg, encoding="utf-8-sig", errors="replace").read() \
            if os.path.isfile(cfg) else ""
        new, _ = build_patched_config(cur, "speakercorrect.txt")
        if new.strip() != cur.strip():
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write(new)
        return _j({"written": True, "target": d,
                   "include": "speakercorrect.txt",
                   "preview": preview})
    except OSError as e:
        return _j({"error": f"write failed ({e}); run app as admin or copy "
                            f"preview manually", "preview": preview})


def verify_config() -> str:
    from ..dsp.apo_setup import find_config_dir
    from ..dsp.apo_semantics import verify
    import os
    d = find_config_dir()
    if not d:
        return _j({"error": "APO not installed"})
    cfg = os.path.join(d, "config.txt")
    text = open(cfg, encoding="utf-8-sig", errors="replace").read() \
        if os.path.isfile(cfg) else ""
    res = verify(text, base_dir=d)
    return _j({"preamp_db": res.preamp_db, "steps_L": len(res.steps.get("L", [])),
               "steps_R": len(res.steps.get("R", [])),
               "warnings": res.warnings, "infos": res.infos})


def _noise_burst(fs: int, seconds: float, level: float = 0.25):
    import numpy as np
    rng = np.random.default_rng(20261010)
    n = int(fs * seconds)
    x = rng.standard_normal(n) * level * 0.5
    fade = max(1, int(0.05 * fs))
    ramp = np.hanning(fade * 2)[:fade]
    x[:fade] *= ramp
    x[-fade:] *= ramp[::-1]
    return x


def check_levels(output: str, input: str, seconds: float = 1.0,
                 confirm: bool = False) -> str:
    """SIDE EFFECT: plays a short noise burst and reports mic levels.

    The REW-style procedure BEFORE any sweep: verify the mic hears the
    speaker at a sane level. Refuses unless confirm=true.
    """
    if not confirm:
        return _j({"refused": True,
                   "note": "Plays a short noise burst. Re-call with "
                           "confirm=true after asking the user."})
    try:
        from ..io.audio import play_rec
        from ..dsp.measure import level_dbfs, level_verdict
        fs = 48000
        rec = play_rec(_noise_burst(fs, float(seconds)), fs,
                       output, input, float(seconds) + 0.5)
        pk, rms = level_dbfs(rec)
        return _j({"played": True, "peak_dbfs": round(pk, 1),
                   "rms_dbfs": round(rms, 1),
                   "verdict": level_verdict(pk, rms),
                   "thresholds": {"too_quiet_below": -50,
                                   "clip_risk_above": -1}})
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}"})


def measure_sweep(output: str, input: str, seconds: float = 5.0,
                  confirm: bool = False,
                  skip_level_check: bool = False) -> str:
    """SIDE EFFECT: level-check burst, then a sweep (REW-style procedure).

    1) noise burst -> mic must hear it (-50..-1 dBFS, else REFUSE)
    2) log sweep -> deconvolved IR stored in session.
    Refuses unless confirm=true (AI must ask the human first).
    """
    if not confirm:
        return _j({"refused": True,
                   "note": "This plays sound through your speakers. "
                           "Re-call with confirm=true after asking the user."})
    try:
        import numpy as np
        from ..io.audio import play_rec
        from ..dsp.measure import (log_sweep, deconvolve, level_dbfs,
                                   level_verdict)
        fs = 48000
        levels = None
        if not skip_level_check:
            rec = play_rec(_noise_burst(fs, 1.0), fs, output, input, 1.5)
            pk, rms = level_dbfs(rec)
            levels = {"peak_dbfs": round(pk, 1), "rms_dbfs": round(rms, 1),
                      "verdict": level_verdict(pk, rms)}
            if pk < -50:
                return _j({"refused": "level check FAILED: mic hears nothing "
                           "(peak <-50 dBFS). Check devices/wiring/gain.",
                           "levels": levels})
            if pk >= -1.0:
                return _j({"refused": "level check FAILED: clipping risk "
                           "(peak >= -1 dBFS). Lower volume first.",
                           "levels": levels})
        sweep = log_sweep(fs, float(seconds))
        rec = play_rec(sweep, fs, output, input, float(seconds) + 2.0)
        ir = deconvolve(rec, sweep, fs, ir_len=fs * 2)
        n = len(SESSION["irs"])
        SESSION["irs"][f"sweep#{n}"] = (fs, ir)
        pk, rms = level_dbfs(rec)
        return _j({"recorded": True,
                   "levels_precheck": levels,
                   "rec_peak_dbfs": round(pk, 1),
                   "rec_rms_dbfs": round(rms, 1), "ir_samples": len(ir),
                   "note": "IR stored; time_align/design_fir unlocked."})
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}"})


def save_graph(path: str, name: str = "") -> str:
    """Render session measurements (FR curves + IR-derived) to a PNG.

    No sound, no config writes — pure picture for the human to look at.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if not SESSION["measurements"] and not SESSION["irs"]:
        return _j({"error": "nothing to draw; import_measurement or "
                           "measure_sweep first"})
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        import numpy as np
        import pyqtgraph as pg
        curves = {}
        for k, m in SESSION["measurements"].items():
            if name and name != k:
                continue
            curves[k] = (np.asarray(m.frequencies, dtype=np.float64),
                         np.asarray(m.spl, dtype=np.float64))
        from ..dsp.measure import ir_freq_response
        for k, (fs, x) in SESSION["irs"].items():
            if name and name != k:
                continue
            curves[f"IR {k}"] = ir_freq_response(x, int(fs))
        if not curves:
            return _j({"error": f"no curve named {name!r}",
                       "have": list(SESSION["measurements"])
                               + list(SESSION["irs"])})
        plt = pg.PlotWidget()
        plt.setLogMode(x=True, y=False)
        plt.setLabel("left", "dB (rel. median)")
        plt.setLabel("bottom", "Hz")
        plt.addLine(y=0, pen=pg.mkPen("#666666", width=1))
        for k, (f, db) in curves.items():
            db = np.asarray(db, dtype=np.float64)
            plt.plot(np.asarray(f), db - float(np.median(db)),
                     pen=pg.mkPen(width=2))
        app.processEvents()
        img = plt.grab()
        img.save(path)
        plt.close()
        return _j({"saved": os.path.abspath(path),
                   "curves": list(curves)})
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}"})


def auto_eq(target: str = "bass+3@80", corner_hz: float = 80.0,
            max_bands: int = 10, max_boost: float = 0.0,
            max_cut: float = 8.0, fit_lo: float = 30.0,
            fit_hi: float = 8000.0,
            write: bool = False, listen_approved: bool = False,
            fir_wav: str = "", name: str = "") -> str:
    """Dirac-style auto-correction: PEQ toward target + optional phase-only FIR
    (fir_wav from design_fir) in ONE write (bands + Convolution + Include).
    fit_lo/fit_hi restrict WHERE it corrects. CUTS ONLY by policy
    (max_boost=0): never lift anything — dips/nulls are room artifacts,
    boosting them wastes power and risks clipping. Write requires >=15%
    improvement AND listen_approved=true.
    """
    import numpy as np
    # 1) pick the curve: named measurement, latest measurement, or last IR
    f = db = None
    if SESSION["measurements"]:
        key = name if name and name in SESSION["measurements"] \
            else list(SESSION["measurements"])[-1]
        m = SESSION["measurements"][key]
        f, db = (np.asarray(m.frequencies, dtype=np.float64),
                 np.asarray(m.spl, dtype=np.float64))
    elif SESSION["irs"]:
        from ..dsp.measure import ir_freq_response
        last = list(SESSION["irs"].values())[-1]
        f, db = ir_freq_response(last[1], int(last[0]))
    if f is None:
        return _j({"error": "no measurement in session — import_measurement "
                           "or measure_sweep first"})
    # 2) solve toward the target
    from ..dsp.target import preset_curve
    from ..dsp.solver import solve_peq, SolverParams
    from ..dsp.peq import build_speakercorrect
    tgt = preset_curve(f, target, corner_hz=corner_hz)
    bands, rep = solve_peq(f, db, tgt, SolverParams(
        max_bands=int(max_bands), max_boost=float(max_boost),
        max_cut=float(max_cut), fit_lo=float(fit_lo),
        fit_hi=float(fit_hi)), fs=48000.0)
    SESSION["bands"] = bands
    worst_boost = max((b.gain for b in bands), default=0.0)
    SESSION["preamp"] = -worst_boost if worst_boost > 0 else 0.0
    preview = build_speakercorrect(bands, SESSION["preamp"])
    imp = (1.0 - rep["rms_after"] / rep["rms_before"]) \
        if rep["rms_before"] > 1e-9 else 0.0
    out = {"target": target, "corner_hz": corner_hz,
           "bands_placed": rep["placed"],
           "rms_before_db": round(rep["rms_before"], 2),
           "rms_after_db": round(rep["rms_after"], 2),
           "improvement_pct": round(imp * 100.0, 1),
           "worst_boost_db": round(worst_boost, 1),
           "preamp_set": SESSION["preamp"],
           "bands": [b.__dict__ for b in bands],
           "preview": preview}
    if write and imp < 0.15:
        # quality gate: a correction that does not clearly help is
        # measurement noise (low mic level / bad SNR), NOT a room curve.
        out["written"] = False
        out["refused"] = (f"improvement {imp*100:.1f}% < 15% — measurement "
                          f"SNR too low. Raise speaker volume / mic gain, "
                          f"re-measure, retry. Nothing was written.")
        return _j(out)
    if write and not listen_approved:
        # EAR GATE (regression fix): numbers can lie when SNR is bad —
        # nothing goes live until a human has LISTENED and approved.
        out["written"] = False
        out["refused"] = ("ear gate: re-call with listen_approved=true "
                          "AFTER the user heard the preview and approved "
                          "it (set_eq preview / GUI A/B). Nothing written.")
        return _j(out)
    if not write:
        out["written"] = False
        out["note"] = "Preview only — re-call with write=true to apply."
        return _j(out)
    import os
    from ..dsp.apo_config import ApoOutput, render_speakercorrect
    from ..dsp.apo_setup import find_config_dir, build_patched_config
    d = find_config_dir()
    if not d:
        out["error"] = "APO config dir not found"
        return _j(out)
    conv = {}
    if fir_wav:
        try:
            from scipy.io.wavfile import read as _wr
            _fs, _ = _wr(fir_wav)
            conv[int(_fs)] = os.path.abspath(fir_wav)
            out["convolution"] = conv
        except Exception as e:
            out["convolution_error"] = f"{type(e).__name__}: {e}"
    full = render_speakercorrect(ApoOutput(
        preamp_db=SESSION["preamp"], bands=bands, convolution=conv))
    try:
        with open(os.path.join(d, "speakercorrect.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(full)
        cfg = os.path.join(d, "config.txt")
        cur = open(cfg, encoding="utf-8-sig", errors="replace").read() \
            if os.path.isfile(cfg) else ""
        new, _ = build_patched_config(cur, "speakercorrect.txt")
        if new.strip() != cur.strip():
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write(new)
        out["written"] = True
        out["target_dir"] = d
        return _j(out)
    except OSError as e:
        out["error"] = f"write failed ({e})"
        return _j(out)


def push_ir_to_rew(name: str = "", save_dir: str = "") -> str:
    """Push OUR measured IR into REW's GUI via its import API (free
    endpoint). After this the sweep IS visible in REW: analyse it there,
    or let our auto_eq process it. Bridges both worlds."""
    irs = SESSION["irs"]
    if not irs:
        return _j({"error": "no IR in session — measure_sweep first"})
    key = name if name and name in irs else list(irs)[-1]
    fs, x = irs[key]
    import os
    import tempfile
    import urllib.request
    import urllib.error
    import numpy as np
    from scipy.io.wavfile import write as wavwrite
    d = save_dir or tempfile.gettempdir()
    path = os.path.join(d, f"harmo-{key.replace('#', '_')}.wav")
    wavwrite(path, int(fs), np.asarray(x, dtype=np.float32))
    body = json.dumps({"path": path.replace("\\", "/"),
                       "channels": "All"}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:4735/import/impulse-response", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        return _j({"error": f"REW refused ({e.code}): "
                            f"{e.read(200)!r}. Is REW 5.40+ running with API?",
                   "wav": path})
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}. Is REW running?",
                   "wav": path})
    return _j({"pushed": True, "wav": path, "rew_status": status,
               "note": "Look at REW: the IR is now a measurement there. "
                       "REW sees OUR sweep."})


def time_align() -> str:
    """Estimate inter-channel delays from session IR onsets (needs >=2)."""
    if len(SESSION["irs"]) < 2:
        return _j({"error": "need >=2 IRs (import .wav files or measure)",
                   "have": list(SESSION["irs"])})
    try:
        from ..dsp.align import estimate_delays, align_delays
        rel = estimate_delays(SESSION["irs"])
        apo = align_delays(SESSION["irs"])
        return _j({"relative_ms": {k: round(v, 3) for k, v in rel.items()},
                   "apo_delay_ms": {k: round(v, 3) for k, v in apo.items()},
                   "note": "earliest onset = 0 ms; APO delays the EARLY "
                           "channel(s) up to the latest."})
    except ValueError as e:
        return _j({"error": str(e)})


def design_fir(taps: int = 4096, strength: float = 0.3,
               below_hz: float = 300.0, save_wav: str = "",
               phase_only: bool = False) -> str:
    """Design the phase-correction FIR (rePhase-equivalent, in-house).

    phase_only=true when PEQ already handles magnitude: the FIR then
    corrects ONLY excess phase (below below_hz, scaled by strength).
    """
    if not SESSION["irs"]:
        return _j({"error": "no IRs in session; import or measure first"})
    try:
        from ..dsp.fir import design_speaker_fir, FirParams, save_fir_wav
        irs = list(SESSION["irs"].values())
        fs_set = {fs for fs, _ in irs}
        if len(fs_set) != 1:
            return _j({"error": f"mixed sample rates {sorted(fs_set)}"})
        p = FirParams(taps=int(taps), strength=max(0.0, min(1.0, strength)),
                      phase_below_hz=float(below_hz),
                      phase_only=bool(phase_only))
        rep = design_speaker_fir([x for _, x in irs], fs_set.pop(), p)
        out = {"taps": rep.taps_n,
               "latency_ms": round(rep.latency_ms, 2),
               "pre_ring_db": round(rep.pre_ring_db, 1),
               "peak_db": round(rep.peak_db, 1), "notes": rep.notes}
        if save_wav:
            save_fir_wav(save_wav, rep)
            out["saved"] = save_wav
        return _j(out)
    except Exception as e:
        return _j({"error": f"{type(e).__name__}: {e}"})
