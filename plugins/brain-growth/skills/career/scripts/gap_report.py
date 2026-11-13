#!/usr/bin/env python3
"""Gap report for career conversations: where the evidence is thin against the target level.

    python3 gap_report.py [--level P4]

Reads the framework files, the tracker, hypotheses and self-ratings. For the chosen level (default:
`levels.target` in source-config.json) prints, per skill, the criteria with their evidence count,
pending candidates, hypothesis state and self-rating, sorted weakest first, plus the rating-vs-evidence
mismatches (rated 3+ with no evidence). Confidential output: it goes to the model, not to a shared file.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "growth-signals" / "scripts"))
import growthlib as gl  # noqa: E402
from build_matrix import matrix_rows  # noqa: E402
from brainos.workspace import emit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--level")
    args = ap.parse_args()
    cfg = gl.source_config()
    level = args.level or cfg["levels"]["target"]
    rows = [r for r in matrix_rows() if r["level"] == level]
    if not rows:
        emit({"status": "failed", "reason": f"no framework criteria for level '{level}' in growth/development/frameworks"})
        return 1
    by_skill: dict[str, list] = {}
    for r in rows:
        score = r["evidence"] * 2 + (r["hypothesis"][0] if r["hypothesis"] else 0) + (r["rating"] or 0) * 0.5
        by_skill.setdefault(r["skill"], []).append({**{k: r[k] for k in ("id", "text", "evidence", "pending", "hypothesis", "rating", "comment")}, "score": score})
    skills = []
    for s, crits in by_skill.items():
        crits.sort(key=lambda c: c["score"])
        skills.append({"skill": s, "evidence_total": sum(c["evidence"] for c in crits),
                       "gaps": [c["id"] for c in crits if c["evidence"] == 0], "criteria": crits})
    skills.sort(key=lambda s: s["evidence_total"] / max(1, len(s["criteria"])))
    mismatches = [{"id": r["id"], "rating": r["rating"], "comment": r["comment"]} for r in rows
                  if (r["rating"] or 0) >= 3 and r["evidence"] == 0]
    emit({"status": "success", "current_level": cfg["levels"]["current"], "target_level": level,
          "skills_weakest_first": skills, "rated_without_evidence": mismatches})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
