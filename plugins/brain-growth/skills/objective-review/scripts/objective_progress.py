#!/usr/bin/env python3
"""Facts for a mid-period objective check-in: progress of each objective against mined evidence.

    python3 objective_progress.py [--file growth/objectives/2027-H1.md] [--today YYYY-MM-DD]

For each objective: boxes done/total, the criteria it is tagged with, promoted evidence bullets
and pending candidates for those criteria since the objective set date, and a signal
(on-track, thin, no-evidence, no-tag). Defaults to the newest objectives file. Prints JSON for the
model; it writes nothing. The check-in notes are written by the skill, after the owner agrees.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "growth-signals" / "scripts"))
import growthlib as gl  # noqa: E402
from brainos import frontmatter  # noqa: E402
from brainos.workspace import emit, rel, parse_date  # noqa: E402

DATE_IN_TITLE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def signal(boxes_done: int, boxes: int, promoted: int, pending: int, tagged: bool, elapsed: float) -> str:
    if not tagged:
        return "no-tag"
    if promoted == 0 and pending == 0:
        return "no-evidence" if elapsed >= 0.25 else "too-early"
    if promoted == 0 or (boxes and boxes_done / boxes < elapsed - 0.3):
        return "thin"
    return "on-track"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file")
    ap.add_argument("--today")
    ap.add_argument("--period-days", type=int, default=182)
    args = ap.parse_args()
    files = [Path(args.file)] if args.file else gl.objective_files()
    if not files:
        emit({"status": "failed", "reason": "no objectives file in growth/objectives; run the objectives skill first"})
        return 1
    p = files[-1]
    if not p.is_absolute():
        p = gl.root() / p
    text = p.read_text(encoding="utf-8")
    fm = frontmatter.parse(text)
    today = parse_date(args.today) if args.today else date.today()
    try:
        set_on = parse_date(str(fm.get("set")))
    except ValueError:
        set_on = today
    elapsed = max(0.0, min(1.0, (today - set_on).days / args.period_days))

    tracker = gl.tracker_evidence(gl.read_text(gl.gp("tracker")))
    cands = [c for c in gl.parse_candidates(gl.read_text(gl.gp("evidence"))) if c["status_idx"] is None]
    objs = []
    for o in gl.parse_objectives(text):
        promoted = sorted({t for cid in o["criteria"] for t in tracker.get(cid, [])})
        pending = [c["title"] for c in cands if set(c["criteria"]) & set(o["criteria"])]
        done = sum(1 for d in o["done"] if d["checked"])
        objs.append({"n": o["n"], "title": o["title"], "boxes_done": done, "boxes_total": len(o["done"]),
                     "open_boxes": [d["text"] for d in o["done"] if not d["checked"]], "criteria": o["criteria"],
                     "promoted_evidence": promoted, "pending_candidates": pending,
                     "signal": signal(done, len(o["done"]), len(promoted), len(pending), bool(o["criteria"]), elapsed)})
    emit({"status": "success", "file": rel(p), "period": fm.get("period"), "set": str(set_on), "elapsed_fraction": round(elapsed, 2),
          "objectives": objs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
