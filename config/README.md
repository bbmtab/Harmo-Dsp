# config/ — all configuration lives here (nothing outside the project)

| file | committed? | purpose |
|---|---|---|
| `speakercorrect.example.txt` | ✓ example | format reference (copy → rename to `speakercorrect.txt`) |
| `speakercorrect.txt` | ✗ user output | written by Step 5 Export into the APO config dir |
| `presets/*.json` | ✓ examples | Peace-style presets (load via Step 4) |
| `*.wav` | ✗ generated | FIR correction impulses (Step 5 / Convolution) |
| `config.*.bak-*` | ✗ backups | automatic backups of APO `config.txt` |

The app NEVER writes outside this folder except the two user-confirmed
APO targets: `speakercorrect.txt` + one `Include:` line in APO `config.txt`.
Sample measurements/fixtures live in `samples/` (committed).
