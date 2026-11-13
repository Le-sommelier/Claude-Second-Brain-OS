#!/usr/bin/env python3
"""List raw meeting transcripts that have no summary yet.

    python3 ${CLAUDE_SKILL_DIR}/scripts/detect_new_meetings.py
    python3 ${CLAUDE_SKILL_DIR}/scripts/detect_new_meetings.py --lookback-weeks 8 --today 2026-11-13

Raw transcripts are `mtg-*.txt` (plain text) or `mtg-*.md` (fetched with frontmatter).
Scans raw/meetings/ in the ISO week of --today plus --lookback-weeks earlier weeks (default 2).
A transcript counts as summarised when `<id>.summary.md` sits beside it, or when any note's
`source_transcript` frontmatter points at it. Prints
{"count", "fan_out", "meetings": [{"id", "path", "name", "size_bytes", "week", "note_dir", "note_path", "raw_has_flags"}]}.
`fan_out` is true when batching into subagents is worthwhile (see SKILL.md).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos import frontmatter  # noqa: E402
from brainos.workspace import emit, iso_week, parse_date, path, rel, week_dir  # noqa: E402

TRANSCRIPT = re.compile(r"^mtg-(\d{4}-\d{2}-\d{2})-.+\.(?:txt|md)$")
FAN_OUT_COUNT = 5
FAN_OUT_BYTES = 80 * 1024


def notes_on_disk(week_dirs: list[Path]) -> set[str]:
    out: set[str] = set()
    for d in week_dirs:
        for note in d.glob("*.md"):
            if note.name.startswith("_"):
                continue
            st = frontmatter.read(note).get("source_transcript")
            if st:
                out.add(str(st))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--lookback-weeks", type=int, default=2)
    args = ap.parse_args()

    today = parse_date(args.today)
    base = path("core", "raw") / "meetings"
    weeks = [week_dir(base, today - timedelta(weeks=i)) for i in range(args.lookback_weeks + 1)]
    done = notes_on_disk([w for w in weeks if w.exists()])

    meetings = []
    for wd in weeks:
        if not wd.exists():
            continue
        for t in sorted(wd.glob("mtg-*")):
            m = TRANSCRIPT.match(t.name)
            if not m or t.name.endswith(".summary.md"):
                continue
            note = wd / f"{t.stem}.summary.md"
            if rel(t) in done or note.exists():
                continue
            meetings.append({
                "id": t.stem, "path": rel(t), "name": t.name, "size_bytes": t.stat().st_size,
                "week": iso_week(parse_date(m.group(1)))[1], "note_dir": rel(wd), "note_path": rel(note),
                "raw_has_flags": t.suffix == ".md" and "wiki_processed" in frontmatter.read(t),
            })
    fan_out = len(meetings) >= FAN_OUT_COUNT or any(m["size_bytes"] > FAN_OUT_BYTES for m in meetings)
    emit({"count": len(meetings), "fan_out": fan_out, "meetings": meetings})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
