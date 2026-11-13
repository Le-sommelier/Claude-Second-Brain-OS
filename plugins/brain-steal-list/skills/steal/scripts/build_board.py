"""Rebuild <steal home>/board.md from steal.db: a markdown status board.

One section per status (new, adopted, plan_drafted, plan_approved, done, deferred, rejected, skipped). Each row has
the id, title, verdict, and the exact `/brain-steal-list:steal` command to act on it.

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/build_board.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402

# (status in the database, section heading)
SECTIONS = [("proposed", "New"), ("adopted", "Adopted"), ("plan_drafted", "Plan drafted"), ("plan_approved", "Plan approved"),
            ("done", "Done"), ("deferred", "Deferred"), ("rejected", "Rejected"), ("skipped", "Skipped")]
VERB = {"adopted": "adopt", "rejected": "reject", "deferred": "defer"}
NEXT = {"proposed": ["adopted", "rejected", "deferred"], "deferred": ["adopted", "rejected"], "adopted": ["rejected", "deferred"],
        "plan_drafted": ["rejected", "deferred"], "plan_approved": [], "skipped": ["adopted"], "rejected": ["adopted"], "done": []}


def cell(text: object) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def commands(status: str, item_id: int) -> str:
    cmds = [f"`/brain-steal-list:steal {VERB[s]} {item_id}`" for s in NEXT.get(status, [])]
    return "<br>".join(cmds) if cmds else "-"


def render(rows: list, built: str) -> str:
    out = ["# Steal board", "", f"Built {built}. {len(rows)} items. Paste a command in Claude Code to act on a row.", ""]
    for status, heading in SECTIONS:
        sub = [r for r in rows if r["status"] == status]
        out += [f"## {heading} ({len(sub)})", ""]
        if not sub:
            out += ["Nothing here.", ""]
            continue
        out += ["| Id | Title | Verdict | Command |", "|---|---|---|---|"]
        for r in sub:
            out.append(f"| {r['id']} | {cell(r['title'])} | {r['verdict']} | {commands(status, r['id'])} |")
        out.append("")
    return "\n".join(out)


def main() -> None:
    con = _steal.connect()
    rows = con.execute(
        "SELECT i.id, i.title, v.verdict, d.status FROM items i JOIN verdicts v ON v.item_id=i.id"
        " JOIN decisions d ON d.item_id=i.id ORDER BY i.id DESC").fetchall()
    dest = _steal.path("steal", "board")
    dest.write_text(render(rows, datetime.now().strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    _steal.emit({"status": "success", "board": _steal.rel(dest), "items": len(rows)})


if __name__ == "__main__":
    main()
