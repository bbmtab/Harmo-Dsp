# GATE 3 — Acceptance: real-rig comparison incl. user-made rePhase FIR

Status: SPEC (not yet executed — needs the user's real rig + files).

## Inputs (user supplies)
1. Measured IR (.wav) from the real rig (UMIK-1, guided measurement).
2. `impulse.txt` — user's OWN manual phase correction from rePhase,
   made from the SAME measurement. Plus its sample rate (asked at import;
   never guessed).

## Procedure
1. Import impulse.txt as the reference FIR (explicit fs from user).
2. Compute the SAME metrics for three candidates:
   - A: our in-house FIR (`dsp/fir.py`)
   - B: user's rePhase FIR (impulse.txt)
   - C: DRC-FIR plugin output (Fase 4; column appears when available)
3. Metrics per candidate (all from `dsp/compare.py`, identical code path):
   - magnitude deviation (RMS dB vs flat, 30–8000 Hz, before/after)
   - group-delay deviation (RMS vs median, 100–1000 Hz, before/after)
   - step response: overshoot %, pre-shoot %, 10–90 % rise time
   - pre-ringing (energy before main peak, dB)
   - latency (ms, from actual peak index)
4. Output: overlay plots (magnitude, group delay, step) + numbers table.

## Rules
- NO words like "setara"/"lebih baik"/"equal"/"better" without numbers.
- A/B listening by the user on the real rig decides the winner.
- Failed gates are reported as-is; no silent re-tuning to win.

## History
- Proposed by user 2026-10-10 (chat). Tooling implemented upfront so
  Gate 3 is "drop files + run", not "build the harness then".
