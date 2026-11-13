#!/usr/bin/env python3
"""Briefing for a self-review: promoted evidence by skill and a values evidence map.

    python3 evidence_map.py [--since YYYY-MM-DD]

Prints, from growth/development only: promoted evidence bullets per skill (with criterion ids), the
candidate titles tagged to each company value (values.json), and the values with zero evidence, so
the coach can ask about them instead of inventing an example. `--since` keeps candidates whose title
date is on or after it. Confidential output for the coaching session only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "growth-signals" / "scripts"))
import growthlib as gl  # noqa: E402
from brainos.workspace import emit  # noqa: E402

VAL_ITEM = re.compile(r"^\s+-\s+`([a-z0-9-]+)`")


def candidate_values(text: str) -> dict[str, list[str]]:
    """value id -> titles of candidates tagged with it (any triage state except Rejected)."""
    lines = text.splitlines()
    out: dict[str, list[str]] = {}
    for c in gl.parse_candidates(text):
        if c["status"] and "Rejected" in c["status"]:
            continue
        in_vals = False
        for ln in lines[c["start"]:c["end"]]:
            if ln.startswith("- **Values evidenced:**"):
                in_vals = True
            elif ln.startswith("- **"):
                in_vals = False
            elif in_vals and (m := VAL_ITEM.match(ln)):
                out.setdefault(m.group(1), []).append(c["title"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since")
    args = ap.parse_args()
    values = gl.load_cfg("values.json")["values"]
    tagged = candidate_values(gl.read_text(gl.gp("evidence")))
    since = args.since or "0000-00-00"
    idx = gl.criteria_index()
    by_skill: dict[str, list[dict]] = {}
    for cid, titles in gl.tracker_evidence(gl.read_text(gl.gp("tracker"))).items():
        skill = idx[cid].skill if cid in idx else "Unmapped"
        for t in titles:
            by_skill.setdefault(skill, []).append({"criterion": cid, "evidence": t})
    vmap = []
    for v in values:
        titles = [t for t in tagged.get(v["id"], []) if t[:10] >= since or not t[:4].isdigit()]
        vmap.append({"id": v["id"], "name": v["name"], "prompt": v["prompt"], "count": len(titles), "evidence": titles})
    vmap.sort(key=lambda v: -v["count"])
    emit({"status": "success", "promoted_by_skill": by_skill, "values": vmap,
          "values_without_evidence": [v["id"] for v in vmap if v["count"] == 0]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
