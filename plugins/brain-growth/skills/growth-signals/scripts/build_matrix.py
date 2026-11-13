#!/usr/bin/env python3
"""Build the evidence matrix: a markdown file, one table per framework.

    python3 build_matrix.py [--today YYYY-MM-DD] [--dry-run]

One table per framework file. Per criterion, three independent signals: promoted evidence count
(bullets tagged `<!-- crit: id -->` in the tracker), the hypothesis state, and the owner's
self-rating (growth/development/self-assessment.json). Pending candidates are shown as a count.
Per criterion: evidence count, latest evidence, status (evidenced / in progress / gap).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growthlib as gl  # noqa: E402
from brainos.workspace import rel, emit  # noqa: E402


def matrix_rows(today: str | None = None) -> list[dict]:
    """One dict per criterion, grouped by framework. Reused by the career and objectives skills."""
    evidence = gl.tracker_evidence(gl.read_text(gl.gp("tracker")))
    hyps = gl.load_hypotheses(gl.read_text(gl.gp("hypotheses")))
    ratings = gl.self_ratings()
    pending: dict[str, int] = {}
    for c in gl.parse_candidates(gl.read_text(gl.gp("evidence"))):
        if c["status_idx"] is None:
            for cid in c["criteria"]:
                pending[cid] = pending.get(cid, 0) + 1
    rows = []
    for fw in gl.frameworks():
        for c in fw.criteria:
            h = hyps.get(c.id)
            r = ratings.get(c.id) or {}
            rows.append({"framework": fw.name, "level": fw.level, "track": fw.track, "skill": c.skill, "id": c.id,
                         "text": c.text, "evidence": len(evidence.get(c.id, [])), "evidence_titles": evidence.get(c.id, []),
                         "pending": pending.get(c.id, 0),
                         "hypothesis": (h["confirmations"], h["status"]) if h else None,
                         "rating": r.get("rating"), "comment": r.get("comment", "")})
    return rows


def cell(text: str) -> str:
    """Make text safe inside a markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def status(r: dict) -> str:
    if r["evidence"]:
        return "evidenced"
    if r["hypothesis"] or r["rating"] or r["pending"]:
        return "in progress"
    return "gap"


def render(rows: list[dict], today: str) -> str:
    out = ["---", "sensitivity: confidential", "---", "", "# Evidence matrix", "",
           f"Confidential. Built {today}. Evidence = promoted tracker bullets. "
           "Status `gap` means no evidence, hypothesis, rating or pending candidate yet.", ""]
    for fw in dict.fromkeys(r["framework"] for r in rows):
        sub = [r for r in rows if r["framework"] == fw]
        out += [f"## {cell(fw)} ({cell(sub[0]['level'])} {cell(sub[0]['track'])})", "",
                "| Criterion | Evidence | Latest evidence | Pending | Hypothesis | Self | Status |",
                "|---|---|---|---|---|---|---|"]
        for r in sub:
            hyp = f"{r['hypothesis'][0]} ({r['hypothesis'][1]})" if r["hypothesis"] else "-"
            latest = cell(r["evidence_titles"][-1]) if r["evidence_titles"] else "-"
            rating = f"{r['rating']}/5" if r["rating"] else "-"
            out.append(f"| {cell(r['text'])} (`{r['id']}`) | {r['evidence']} | {latest} | {r['pending']} | "
                       f"{cell(hyp)} | {rating} | {status(r)} |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = matrix_rows()
    if not rows:
        emit({"status": "failed", "reason": "no framework criteria; add files to growth/development/frameworks first"})
        return 1
    today = args.today or date.today().isoformat()
    out = gl.gp("matrix")
    if not args.dry_run:
        gl.write_atomic(out, render(rows, today))
    emit({"status": "success", "criteria": len(rows), "with_evidence": sum(1 for r in rows if r["evidence"]),
          "gaps": sum(1 for r in rows if r["evidence"] == 0 and not r["hypothesis"] and not r["rating"]),
          "output": rel(out)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
