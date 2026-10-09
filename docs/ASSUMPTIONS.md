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

## TODO / GUESSES
- REW menu names differ per version — parser is tolerant, verify with real exports.
- .mdat format undocumented — NOT supported, message directs to .txt/.wav.
- Sample rate for response math assumed 48 kHz (peak estimate is robust to this).
- Modal filter internal shape unknown — |gain| fallback (safe side).
- Convolution libsndfile formats per APO docs (wav/flac/ogg) — not re-verified here.
