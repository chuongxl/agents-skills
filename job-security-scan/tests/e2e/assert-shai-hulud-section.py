#!/usr/bin/env python3
"""assert-shai-hulud-section.py RUN_DIR - the report's Shai-Hulud section has one row per raw result folder,
with the verdict the scanner wrote, what it checked, and a raw-output link that exists. Exit 0 ok, 1 not."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "lib"))
import report_store  # noqa: E402

run = Path(sys.argv[1])
doc = report_store.load_full(run)
sh = doc["shai_hulud"]
rows = dict((t["repo"], t) for t in sh["targets"])
md = (run / "security-report.md").read_text().split("## 🪱 Shai-Hulud check")[1].split("\n## ")[0]
bad = []
for raw in sorted(run.glob("*/shai-hulud.json")):
    label = "this machine" if raw.parent.name == "_host" else raw.parent.name
    want = json.loads(raw.read_text())["verdict"]
    row = rows.get(label)
    if row is None:
        bad.append("%s: no row" % label)
        continue
    if row["verdict"] != want:
        bad.append("%s: report says %s, scanner said %s" % (label, row["verdict"], want))
    if not row["checked"].get("ioc_version"):
        bad.append("%s: no indicator version in 'checked'" % label)
    if not row["raw"] or not (run / row["raw"]).is_file():
        bad.append("%s: raw output link %r does not exist" % (label, row["raw"]))
    if "| %s |" % label not in md:
        bad.append("%s: no row in the Markdown section" % label)
if not sh["ran"]:
    bad.append("section says the check did not run")
print("\n".join(bad) or "%d targets ok" % len(rows))
sys.exit(1 if bad else 0)
