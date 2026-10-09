# plugins/ — external tools (user installs, never bundled)

Rule (brief): GPL or unclear-license tools run ONLY as separate programs
via subprocess. Nothing here is linked or copied into MIT core code.

| folder | tool | license (verify in Fase 0) | status |
|---|---|---|---|
| `drc-fir/` | DRC-FIR (FIR generator) | GPL → plugin-only | manifest stub |
| `rephase/` | rePhase (phase-linearisation) | unclear → plugin-only | manifest stub |

Each manifest (`plugin.json`): name, version, license, source_url, exe,
args template (`{in}`/`{out}`), input/output formats, supported sha256,
user-facing description.

Install flow (UI "Plugins" page, Fase 4): status installed/missing →
license text → user approves → download from source_url → sha256 check.
The app works fully WITHOUT any plugin (in-house FIR in `src/harmo_dsp/dsp/`).
