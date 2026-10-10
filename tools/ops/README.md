# tools/ops/ — operator runbooks (NOT product code, NOT tested in CI)

Manual MCP-operator scripts used during the 2026-10 sessions. They drive
`harmo_dsp.mcp_server` (or REW's API) as a real client and print results.
Kept for the next model to re-run flows without reinventing them.

- dirac_flow.py — measure (UMIK-1) → auto-EQ preview → FIR → graph
- approve_write.py — re-measure + auto_eq(write=true, listen_approved=true)
- rew_rta_flow.py — REW generator+RTA (free API) → FR pull → our auto_eq
- rew_manual_flow.py — import a REW manual sweep export → auto_eq
- gate3_measure.py — measure + export IR + design A/B FIRs (Gate-3 dry run)
- gate3_compare.py — naive baseline + compare table + overlay PNGs
- mk_preset.py — speakercorrect.txt on disk → GUI preset JSON

All read absolute paths (L:\...); adjust before reuse on another machine.
Audio side effects (sweeps) only with the user's live consent.
