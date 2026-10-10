# HANDOVER — Harmo-Dsp (project paused 2026-10-10)

> Read this first if you are the next model continuing this project.
> Language: code/comments English; user speaks Indonesian (simple).

## 0. Goal, verdict, and why Dirac was NOT reached

**Goal (unchanged): Dirac-level PC speaker correction** — measure,
auto-correct magnitude + phase, verify by ear, all open-source.

**Verdict: not reached.** What runs today is an honest, well-tested
*parametric-EQ workbench with Dirac-style tooling around it* — not a
Dirac. The numbered reasons below are all verifiable in this repo;
they are the exact deadlocks to break:

1. **Measurement SNR ceiling.** Every real sweep peaked −9…−38 dBFS
   with TOO QUIET verdicts (UMIK-1 needs louder playback; user never
   raised it enough). All corrections were built on marginal data.
   Dirac's foundation is clean multi-position measurements; ours were
   single-position and noisy. No code fixes bad SNR — fix the LEVELS
   first (`check_levels` must say OK, not "proceed anyway").
2. **FIR never touched the live chain.** `dsp/fir.py` passes synthetic
   acceptance (group-delay −50 %, decay, latency, multi-pos) but was
   only ever previewed, never written + listened. Phase correction =
   ~half the Dirac claim, 0 % verified on hardware.
3. **No multi-position in product.** Brief criterion 3 (nulls that move
   are ignored) exists only as synthetic test e. The guided flow stores
   ONE IR per channel; averaging + consistency weighting never runs
   on real data.
4. **No per-channel correction.** One design drives L+R. `dsp/align.py`
   exists but no UI flow collects L and R IRs separately.
5. **Solver not wired to GUI.** `dsp/solver.py` works (greedy, tested)
   but Step 3 "Calculate" is a dead button (see §9). Auto-EQ lives
   only behind the MCP `auto_eq` tool.
6. **Target page fully dead** (see §9) — no target flows anywhere.
7. **Session tax.** Enormous turns burned on environment, not
   acoustics: hidden-desktop launches, non-admin shell, S/PDIF
   loopback glitches, PowerShell quoting, Unicode cp1252 crashes.
   Budget for this; it will recur on this machine.
8. **Structural gap.** Dirac = years of tuning + controlled protocol
   + MIMO + verification culture. A greedy solver + 1 mic position
   cannot match that by construction. The honest path is narrower:
   ONE good measurement → ONE verified correction → ear-approved.
   Stop adding features until that loop is green end-to-end.

## 9. Label-only UI inventory (dead controls — do not demo these)

Verified by grep for missing signal connections (`pages.py`):

- Step 3 `btn_calc` "Calculate correction" (pages.py:407-409) — NO
  handler. The solver it promises lives in `dsp/solver.py` + MCP
  `auto_eq`; never connected. #1 priority if resuming.
- Step 4 `btn_reopt` "Re-optimize around manual bands" (~:551) — NO
  handler. Lock/respect logic does not exist anywhere.
- Step 2 Target page, entire page: `preset` + `smooth` combos
  (:368-374) are display-only (nothing reads them); graph is a
  placeholder (:365). No target flows anywhere in the GUI.
- Step 3 "Measured vs Predicted vs Target overlay" (:388) —
  placeholder, never drawn.
- Step 1 ImportPage graph: REAL since the graph feature (plots
  imported/measured curves); empty-state text is honest.
- Channel 2.0/2.1 selector: writes IDENTICAL files in v1 (verified:
  `changed` signal was dead; now connected to an honest `_mode_note`
  in main_window.py — keep that honesty, don't imply 2.1 routing).
- RTA / meter / LiveSpectrum: real but OPT-IN by button press
  (deliberate — auto-opening audio streams caused the S/PDIF noise
  regression; see §2 + ASSUMPTIONS.md).
- Everything else with a `.connect(` in the grep audit IS wired.
  Re-run the audit after any UI change:
  `Select-String pages.py -Pattern '\.connect\('` vs button defs.

## 1. One-paragraph state

Harmo-Dsp = open-source Windows PC speaker correction (MIT core),
REW-measured, APO-executed, Dirac-inspired. **Working today:** manual
31-band + parametric EQ GUI, REW/Peace import, auto PEQ solver (tested),
in-house mixed-phase FIR designer (tested, synthetic), full APO
config read/write/verify/backup, one-click APO attach, MCP server
(11 tools), guided sweep measurement. **NOT reached:** audible
Dirac parity — no verified listening win; FIR never deployed to the
live chain; auto-solver not wired to the GUI button; per-channel,
time-align UI, multi-position, DRC plugin all pending. User paused
the project pending a more capable model.

## 2. Live audio state (2026-10-10, verify before trusting)

- APO 1.2.1 installed; engine COM registered (pre+post mix GUIDs OK).
- `config.txt` = 1 comment line only (APO idle). No Include active.
- No `speakercorrect.txt` (deleted in cleanup). No python processes.
- Playback: Realtek Digital Output (optical S/PDIF) @ **192 kHz**
  (device default rate — any Convolution WAV MUST be 192 kHz or APO
  skips the convolver silently).
- Mic: miniDSP UMIK-1 (+18 dB variant), indices move per boot;
  auto-pick helper: `io/audio.py pick_measurement_mic` (umik > usb).
- Earlier noise saga: repeating noise correlated with (a) aggressive
  Q8-stacked EQ content AND (b) loopback capture streams held open on
  the S/PDIF endpoint. Never auto-open audio streams at launch
  (meter/RTA are opt-in for this reason). Launch must be audio-silent.

## 3. Repo map

```
src/harmo_dsp/
  dsp/  peq.py (17 APO filter types, official syntax) | geq.py (31-band)
        apo_config.py (full file builder) | apo_semantics.py (parser+verify)
        apo_setup.py (install/wire status, Include patcher)
        apo_attach.py (device enum, SFX/EFX plan — READS registry only)
        clip_guard.py (RBJ anti-clip math) | fir.py (mixed-phase designer)
        solver.py (greedy auto PEQ) | target.py (house curves, corner param)
        measure.py (sweep/deconv/levels) | align.py (onsets/delays)
        compare.py (Gate-3 metrics harness)
  io/   rew.py (txt/frd) | presets.py (REW filter-settings, Peace r/w)
        irwav.py | audio.py (PyAudioWPatch primary, sounddevice fallback)
        meter.py (COM meter + loopback fallback + RingBuffer/LoopbackCapture)
  ui/   main_window.py | pages.py (5-step wizard) | graphic_eq.py (unified
        sliders+detail) | parametric.py | monitor.py (LiveSpectrum, RTA,
        PredictedCurve, OutputMeter) | theme.py | icons.py | widgets.py
  plugins/ runner.py (subprocess-only, binaries NEVER bundled)
  mcp_server/ tools.py (11 tools) | server.py (FastMCP) | state in tools.py
tests/  105 tests, all must pass: QT_QPA_PLATFORM=offscreen pytest -q
tools/  attach_apo.py (ELEVATED helper: attach/detach/repair registry)
        write_apo.py (ELEVATED helper: config file writes + backup)
        shots.py (headless screenshots -> docs/screens; HARMO_NO_AUTOLIVE!)
        ops/ (operator runbooks: dirac_flow.py, approve.py, mk_preset.py...)
config/ README + presets/*.json (flat-stereo example; dirac-mcp.json =
        user's live 4-band correction in editable form)
plugins/ drc-fir/, rephase/ manifests ONLY (no binaries, never bundle)
samples/ user-supplied fixtures (rew1.txt/.peace, impulse.*) — TEST DATA
docs/   ASSUMPTIONS.md (verified facts + sources) | GATE3.md (Gate-3 spec)
        HANDOVER.md (this file)
```

## 4. License boundaries (NON-NEGOTIABLE, brief rules)

- Core = MIT, original code only. Never copy GPL source into src/.
- Equalizer APO (GPL): target-output only. Its CONFIG SYNTAX mirrored
  from official docs; attach PROCEDURE reimplemented from GPL source
  (DeviceAPOInfo.cpp, RegistryHelper.h — read-only reference clone
  lived in L:\Temp, never copied). Facts used: slot PKEYs, SFX/EFX
  GUIDs {EACD2258-…}/{EC1CC9CE-…}, backup+child-APO pattern.
- Peace / rePhase: closed freeware. No code taken (none exists
  publicly; GitHub "Peace" repos are unofficial clones — never a
  source). Only user-owned FILE FORMATS parsed for interop
  (observed from user's own files, round-trip tested).
- DRC-FIR: GPL → plugin-only (manifest exists, runner exists,
  binary never bundled, user installs).

## 5. Test + CI discipline (learned the hard way)

- `QT_QPA_PLATFORM=offscreen python -m pytest -q` → must be green.
- NEVER commit+push chained without seeing green first (caused a red
  push once). GHA (windows-latest, PyInstaller onedir) must go green
  per push — poll it, don't assume.
- Qt teardown: conftest.py closes widgets first (kills the
  "Fatal Python error: Aborted" CI flake).
- Tests must not assume APO/hardware present (skip guards for CI).

## 6. Environment quirks (this machine, verified)

- Agent shell = service session, non-admin. GUI windows spawned here
  land on a HIDDEN desktop (MainWindowTitle enumerable, invisible).
  Reliable user-visible launch: `explorer.exe <bat>` worked once;
  otherwise the USER double-clicks Launch-Harmo-Dsp.bat.
- Never `git rm`/`Stop-Process` with sloppy wildcards: `*harmo*`
  once killed the user's own `local_agent\mcp_local` (username match).
- PowerShell 5.1: no `&&`, quoting pain (write .py fixer files instead
  of inline `python -c` with quotes), UTF8-no-BOM for TOML.
- schtasks /IT + /sd + /st 23:59 pattern works for user-session runs.
- REW 5.40 Beta 135 + API on :4735. GETs free; ALL measurement POSTs
  = 401 Pro-gated ("Pro upgrade license required"). Generator/RTA/
  save-capture POSTs are FREE. RTA+generator = the free measurement
  path (pink noise → 20 s average → Save current → FR pull, BE-decoded
  base64 floats, re-binned to 1/12-oct energy).
- UMIK-1 needs its cal file loaded in REW prefs for absolute SPL.
- Optical S/PDIF: keep volumes moderate during tests; full-scale
  digital noise can damage speakers — pre-announce every audible test.

## 7. Open work, prioritized

1. **Wire solver to GUI Calculate button** (Step 3 placeholder) using
   dsp/solver.py — the single biggest missing backend piece.
2. **Deploy FIR safely**: phase-only WAV at 192 kHz + Convolution,
   behind the ear gate (listen_approved) + A/B. Never auto-write.
3. **Per-channel L/R sweeps + time-align UI** (dsp/align.py exists).
4. **Multi-position averaging** (brief criterion 3).
5. **DRC-FIR plugin** (Fase 4): build/run/compare via compare.py.
6. **Gate 3 proper**: user's rePhase impulse.txt + fs → compare table
   (harness ready in dsp/compare.py + docs/GATE3.md).
7. **Measure hygiene**: sweep level must hit OK verdict (-24..-1 dBFS);
   TOO QUIET data must never reach the solver (gate exists in MCP
   measure_sweep; mirror it in the GUI path).

## 8. User facts (don't re-ask)

- Rig: Realtek Digital Output (optical, 192 kHz) + UMIK-1 (+18 dB).
- Small 3" speakers: 100–200 Hz dead zone is the DRIVER, never boost
  or cut toward it (fit ranges must exclude it).
- Policy: cuts ONLY (max_boost=0), bass-only default fit 25–95 Hz,
  house corner 80 Hz, mids/highs untouched (user likes them).
- Room modes confirmed: ~50 Hz (monster), ~78 Hz (also in their old
  REW file: −21.5 dB @ 72 Hz).
- Reports to user in simple Indonesian, short. Numbers over adjectives.
