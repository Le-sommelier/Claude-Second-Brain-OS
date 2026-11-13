#!/usr/bin/env python3
"""Tier 3 helper of growth-signals: promote the candidates the owner has triaged.

    python3 promote.py [--today YYYY-MM-DD] [--dry-run]

For each candidate with a ticked triage box in evidence-candidates.md:
  Accept -> append an evidence bullet (tagged with its criterion ids) under the matching skill in
            performance-tracker.md, deduplicated by hash, and replace the triage line with a status line.
  Reject / Defer -> replace the triage line with a status line only.
Candidates that already carry a status line are skipped, so the script is idempotent. Rows are
never deleted. Rebuilds the markdown coverage matrix when anything changed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growthlib as gl  # noqa: E402
from brainos.workspace import rel, emit  # noqa: E402

TRACKER_PREAMBLE = "---\nsensitivity: confidential\n---\n\n# Performance tracker\n\n> Promoted evidence, by skill. Edit freely; promote.py only appends.\n"


def append_to_tracker(tracker: Path, cand: dict, today: str) -> bool:
    text = gl.read_text(tracker) or TRACKER_PREAMBLE
    if f"hash: {cand['hash']}" in text:
        return False
    skill = cand["skill"] or "Unclassified"
    lines = text.rstrip("\n").splitlines()
    bullet = [f"- {cand['title']} <!-- crit: {', '.join(cand['criteria'])} -->",
              f"  - Promoted: {today} · `hash: {cand['hash']}`"]
    sk = next((i for i, ln in enumerate(lines) if ln.strip() == f"## {skill}"), None)
    if sk is None:
        lines += ["", f"## {skill}", "", "### Evidence", ""] + bullet
    else:
        end = next((i for i in range(sk + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        ev = next((i for i in range(sk + 1, end) if lines[i].strip() == "### Evidence"), None)
        if ev is None:
            ins = end
            while ins > sk + 1 and not lines[ins - 1].strip():
                ins -= 1
            lines[ins:ins] = ["", "### Evidence", ""] + bullet
        else:
            sub_end = next((i for i in range(ev + 1, end) if lines[i].startswith("### ")), end)
            ins = sub_end
            while ins > ev + 1 and not lines[ins - 1].strip():
                ins -= 1
            lines[ins:ins] = bullet
    gl.write_atomic(tracker, "\n".join(lines) + "\n")
    return True


def status_line(action: str, today: str) -> str:
    word = {"accept": "Promoted", "reject": "Rejected", "defer": "Deferred"}[action]
    return f"- **Status:** {word} on {today}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ev = gl.gp("evidence")
    if not ev.is_file():
        emit({"status": "skipped", "reason": f"no candidates file at {rel(ev)}"})
        return 0
    text = ev.read_text(encoding="utf-8")
    cands = gl.parse_candidates(text)
    today = args.today or date.today().isoformat()
    s = {"status": "success", "total": len(cands), "already_triaged": 0, "accepted": 0, "rejected": 0,
         "deferred": 0, "no_action": 0, "tracker_already_had": 0, "matrix_rebuilt": False}
    lines = text.splitlines()
    tracker = gl.gp("tracker")
    for c in cands:
        if c["status_idx"] is not None:
            s["already_triaged"] += 1
            continue
        if not c["action"]:
            s["no_action"] += 1
            continue
        if c["action"] == "accept":
            if not args.dry_run and not append_to_tracker(tracker, c, today):
                s["tracker_already_had"] += 1
            s["accepted"] += 1
        else:
            s["rejected" if c["action"] == "reject" else "deferred"] += 1
        if not args.dry_run and c["triage_idx"] is not None:
            lines[c["triage_idx"]] = status_line(c["action"], today)
    changed = s["accepted"] + s["rejected"] + s["deferred"]
    if changed and not args.dry_run:
        gl.write_atomic(ev, "\n".join(lines) + "\n")
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "build_matrix.py"), "--today", today],
                           capture_output=True, text=True, cwd=str(gl.root()))
        s["matrix_rebuilt"] = r.returncode == 0
        if r.returncode != 0:
            s["warning"] = "matrix rebuild failed: " + r.stderr.strip()[-200:]
    emit(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
