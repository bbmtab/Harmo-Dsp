"""One-off: current speakercorrect.txt bands -> GUI preset JSON."""
import json
import re
import sys

sys.path.insert(0, r"L:\test-code\Harmo-dsp\src")

src = r"C:\Program Files\EqualizerAPO\config\speakercorrect.txt"
dst = r"L:\test-code\Harmo-dsp\config\presets\dirac-mcp.json"

text = open(src, encoding="utf-8", errors="replace").read()
pat = re.compile(
    r"Filter:\s+ON\s+PK\s+Fc\s+([\d.]+)\s+Hz\s+Gain\s+([-\d.]+)\s+dB\s+Q\s+([\d.]+)")
bands = []
for m in pat.finditer(text):
    bands.append({"on": True, "type": "PK", "fc": float(m.group(1)),
                  "gain": float(m.group(2)), "q": float(m.group(3)),
                  "t60": 100.0, "ch": "all"})
# dedupe (L block == R block)
seen, unique = set(), []
for b in bands:
    k = (b["fc"], b["gain"], b["q"])
    if k not in seen:
        seen.add(k)
        unique.append(b)

data = {"app": "Harmo-Dsp", "v": 2, "name": "dirac-mcp (measured sweep)",
        "preamp": 0.0, "bands": unique}
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
print(f"preset: {dst}")
print(f"bands: {len(unique)}")
for b in unique:
    print(f"  {b['fc']:7.1f} Hz  {b['gain']:+6.1f} dB  Q {b['q']:.2f}")
