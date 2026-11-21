"""Simulate the 12:01 am file drop: move any files waiting in seed/pending into the raw volume.

Idempotent: a file already landed is not copied again. Prints a JSON run summary.
"""
import argparse
import json
import shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--seed_dir", default="/Volumes/c360_bank/cards/seed")
ap.add_argument("--raw_dir", default="/Volumes/c360_bank/cards/raw")
a = ap.parse_args()

pending = Path(a.seed_dir) / "pending"
landed, skipped = [], []
for f in sorted(pending.glob("*.csv")) if pending.exists() else []:
    folder = "crm_solicitations" if f.name.startswith("crm_solicitations_") else f.name.rsplit("_", 1)[0]
    dest = Path(a.raw_dir) / folder / f.name
    if dest.exists():
        skipped.append(f.name)
    else:
        shutil.copy(f, dest)
        landed.append(f"{folder}/{f.name}")
    f.unlink()
print(json.dumps({"task": "land_files", "landed": landed, "already_present": skipped, "files_landed": len(landed)}))
