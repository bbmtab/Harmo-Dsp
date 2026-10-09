# ASSUMPTIONS (verified where noted, guesses marked TODO)

Date: 2026-10-09. Rule: no guessing file formats or syntax — verify or record.

## VERIFIED (against official Equalizer APO Configuration reference,
## SourceForge wiki by Jonas Thedering, fetched 2026-10-09)
- Filter numbers not interpreted, may be omitted.
- BP = real band-pass, NO gain param. NO takes Fc + optional Q, no gain.
  AP takes Fc + Q, no gain. (Our first table version was wrong — fixed.)
- Shelf base codes LS/HS; LSC/HSC take optional slope + Q;
  LS/HS 6dB/12dB corner variants take Fc + Gain, no Q.
- GraphicEQ gains interpolate linearly on the LOG frequency axis.
- Preamp values on one channel SUM in dB (>= v0.8).
- Stereo channel ids: L=1, R=2; "all" selects all.
- APO processes lines top to bottom (order vs Peace matters).
- Convolution file rate MUST equal device rate or convolver is skipped.

## VERIFIED (Peace forum, SourceForge, Peace project)
- Peace checks `Include: peace.txt` on startup; if missing it OVERWRITES
  config.txt. Our app therefore offers Re-apply Include + backup.
- Peace itself is closed freeware (Peter Verbeek). No Peace code, text, or
  assets are used here. Only APO's documented config SYNTAX is mirrored.

## MATH SOURCES (formulas public, implementation original)
- RBJ Audio EQ Cookbook biquads (Robert Bristow-Johnson) for clip_guard.
- Shelf peak never exceeds |gain| (monotonic) — so plain-shelf math safely
  covers LS/HS 6dB/12dB/LSC/HSC peak estimates.

## OBSERVED (from user's own files in samples/, parsers original)
- REW "Filter Settings file" (Room EQ V5.18): header + `Equaliser: Generic`
  + `Filter N: ON|OFF PK Fc X Hz Gain Y dB Q Z` lines; FBQ2496 variant uses
  `BW Oct W` (converted via Q=1/(2·sinh(ln2/2·W))). Gains exceed ±15
  (e.g. -21.5 dB) → core range is ±30 dB; sliders stay ±15 (Peace convention).
- Peace .peace preset (INI): [General] PreAmp; base [Frequencies]/[Gains]/
  [Qualities] as FrequencyN/GainN/QualityN (all Peak); [Speakers] maps
  SpeakerId/Targets/Name (0=all,1=L,2=R,3=C,4=SUB); [FrequenciesN] per-speaker
  ISO slider freqs. Parsed read-only for import (interoperability).
- impulse.txt: raw float-per-line IR (offer WAV conversion for Convolution).
- impulse.rephase: rePhase settings blob (base64) — NOT decoded (rePhase is
  third-party; its export WAV is the interchange path, not its settings).

## FIR / PHASE (in-house mixed-phase designer, src/harmo_dsp/dsp/fir.py)
- Split via real cepstrum (fold negative quefrencies). Standard method,
  implementation original. Verified on synthetics only (criteria a–e green).
- Excess-phase inverse is PHASE-ONLY, gated by: frequency (below
  phase_below_hz), inter-position consistency, 40 dB null gate.
- Frequency-dependent windowing (40/20/5 ms bands) with per-band own-peak
  placement + circular extraction (IFFT wraps). Shared-centre placement was
  tried and FAILED on dispersive signals (measured, not assumed).
- Advance (non-causal part) linearised with explicit pre-room taps//4;
  final window asymmetric (flat pre-response, faded tail) — a symmetric
  Hann was tried and re-broke group delay (measured).
- Honest metrics reported: taps, latency from ACTUAL argmax, pre-ring
  energy ratio. No parity claim vs Dirac: Dirac adds guided measurement,
  MIMO/time alignment and years of tuning. Parity needs Gate 3 (real rig).

## MEASUREMENT + TIME-ALIGN (dsp/measure.py, dsp/align.py, io/audio.py)
- Log sweep (Farina-style) 20 Hz–20 kHz; inverse by EXACT spectral division
  (zero-forcing + -60 dB floor). A +6 dB/oct time-domain envelope was tried
  and measured 2x too hot (correct shape is +3 dB/oct); division avoids lore.
- Onset is SEARCHED (argmax in N-1..N-1+0.5s): fixed-index decapitates real
  rooms (10–500 ms bulk delay). Found via off-by-one in tests.
- align_delays() targets the LATEST onset (APO can delay, never advance).
  Sub caveat from official docs: bass may redirect AFTER APO — verify by ear.
- sounddevice optional (pip install sounddevice); import/hardware failures
  degrade to hints, never crashes. GHA installs it (import-only is safe).
- Honest scope vs Dirac: guided sweep+multiposition+align here; Dirac adds
  MIMO, per-seat optimisation and room-model fitting (Fase 6+).

## TODO / GUESSES
- REW menu names differ per version — parser is tolerant, verify with real exports.
- .mdat format undocumented — NOT supported, message directs to .txt/.wav.
- Sample rate for response math assumed 48 kHz (peak estimate is robust to this).
- Modal filter internal shape unknown — |gain| fallback (safe side).
- Convolution libsndfile formats per APO docs (wav/flac/ogg) — not re-verified here.
