#!/usr/bin/env python3
"""List queued 1:1 drafts, or show one in full for the owner to approve.

    python3 queue_status.py              # counts and ids per person
    python3 queue_status.py --show <id>  # the full draft, rendered as the page entry
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

TITLES = {"discussed": "Discussed", "decisions": "Decisions", "feedback": "Feedback", "career": "Career", "carryover": "Carryover"}


def render_entry(d: dict) -> list[str]:
    """The lines pushed onto the person's page, newest-first inside the confidential wrapper."""
    out = [f"### {d['date']} · {d['title']}"]
    for k in c.SECTION_KEYS:
        items = d["sections"].get(k) or []
        if items:
            out.append(f"- {TITLES[k]}:")
            out += [f"  - {i}" for i in items]
    for a in d["actions"]:
        due = f" (due {a['due']})" if a.get("due") else ""
        out.append(f"- [ ] {a['who']}: {a['what']}{due}")
    out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show")
    args = ap.parse_args()
    files = sorted(c.queue_dir().glob("*/*.json"))
    if args.show:
        hit = [f for f in files if f.stem == args.show]
        if not hit:
            c.emit({"status": "not_found", "id": args.show})
            return 1
        d = json.loads(hit[0].read_text(encoding="utf-8"))
        c.emit({"status": "success", "id": d["id"], "person_id": d["person_id"], "withheld": d["withheld"],
                "source": d["source"], "entry": "\n".join(render_entry(d))})
        return 0
    items = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        items.append({"id": d["id"], "person_id": d["person_id"], "date": d["date"], "title": d["title"]})
    c.emit({"queued": len(items), "items": items})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
