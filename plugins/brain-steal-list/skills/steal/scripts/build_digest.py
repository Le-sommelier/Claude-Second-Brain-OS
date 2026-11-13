"""Render one run from steal.db into digests/<run_id>-steal-digest.md (terse: picks, watch, skipped, patterns).

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/build_digest.py --run-id 2026-11-03-2200
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def lst(v) -> str:
    return ", ".join(json.loads(v or "[]"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    con = _steal.connect()
    run = con.execute("SELECT * FROM runs WHERE run_id=?", (args.run_id,)).fetchone()
    if not run:
        _steal.emit({"status": "failed", "reason": f"unknown run {args.run_id}"})
        raise SystemExit(1)
    rows = con.execute("SELECT i.id, i.title, i.summary, i.author_handle, i.platform, i.source_url, v.* FROM items i"
                       " JOIN verdicts v ON v.item_id=i.id WHERE i.run_id=? ORDER BY i.id", (args.run_id,)).fetchall()
    by = {k: [r for r in rows if r["verdict"] == k] for k in _steal.VERDICTS}

    out = [f"---\nrun_id: {args.run_id}\nsensitivity: personal\n---\n",
           f"# Steal digest {args.run_id}\n",
           f"- {run['n_new']} reviewed: {len(by['steal'])} steal, {len(by['adapt'])} adapt, "
           f"{len(by['watch'])} watch, {len(by['skip'])} skip. {run['n_dupe']} dupes, {run['n_failed']} failed.\n"]

    for label, key in (("Steal", "steal"), ("Adapt", "adapt")):
        if by[key]:
            out.append(f"\n## {label}\n")
            for r in by[key]:
                out.append(f"### #{r['id']} {r['title']}\n"
                           f"- Source: {r['author_handle'] or 'unknown'} ({r['platform'] or '?'}){' ' + r['source_url'] if r['source_url'] else ''}. Effort {r['effort']}, "
                           f"novelty {r['novelty']}, evidence {r['evidence']}, confidence {r['confidence']}.\n"
                           f"- Target: {lst(r['targets'])}\n- Why: {r['why']}\n- How: {r['how']}\n- POV: {r['pov']}\n"
                           f"- Decide: `/brain-steal-list:steal adopt {r['id']}` (or reject, defer)\n")
    if by["watch"]:
        out.append("\n## Watch\n")
        for r in by["watch"]:
            out.append(f"- #{r['id']} **{r['title']}**: {r['pov']}\n")
    if by["skip"]:
        out.append("\n## Skipped\n")
        for r in by["skip"]:
            out.append(f"- #{r['id']} {r['title']}: {r['why']}\n")
    if run["batch_pov"]:
        out.append(f"\n## Patterns in this batch\n{run['batch_pov']}\n")

    dest = _steal.home_dir() / "digests" / f"{args.run_id}-steal-digest.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(out), encoding="utf-8")
    _steal.emit({"status": "success", "digest": _steal.rel(dest), "counts": {k: len(v) for k, v in by.items()}})


if __name__ == "__main__":
    main()
