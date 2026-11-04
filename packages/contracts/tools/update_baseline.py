"""Copy current schemas to baseline/. Run deliberately after reviewing a compatible change."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("events", "dto"):
    dest = ROOT / "baseline" / sub
    dest.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / sub).glob("*.schema.json"):
        shutil.copyfile(f, dest / f.name)
print("baseline updated")
