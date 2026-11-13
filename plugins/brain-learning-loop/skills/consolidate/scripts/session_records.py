#!/usr/bin/env python3
"""Write one structured record per Claude Code session to <core.sessions>/YYYY/MM.jsonl (append-only, deduped by id).

    python3 session_records.py [--since ISO] [--summaries summaries.json] [--dry-run] [--transcripts-dir D]

Record: {id, date, model, summary, files_touched, turns, sensitivity?}. `summary` defaults to the opening ask
(<=160 chars); --summaries is {"<session id or 8-char prefix>": "one-line summary"} written by the nightly model.
A session that touched a confidential path gets a redacted summary and no file list. Own watermark:
<core.sessions>/.watermark.json. Validates the summaries file before writing anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainos.workspace import emit, path, rel  # noqa: E402
import extract_sessions as ex  # noqa: E402


def record_for(p: Path, summaries: dict) -> dict | None:
    humans, _ = ex.extract_turns(p)
    if not humans:
        return None
    first_ts, models = None, Counter()
    for d in ex.read_events(p):
        first_ts = first_ts or d.get("timestamp")
        msg = d.get("message") or {}
        if d.get("type") == "assistant" and msg.get("model"):
            models[msg["model"]] += 1
    files = ex.files_touched(p)
    day = (first_ts or datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat())[:10]
    confidential = ex.touches_confidential(files)
    given = next((v for k, v in summaries.items() if p.stem.startswith(k)), None)
    summary = ex.tidy(given or humans[0], 160)
    rec = {"id": p.stem, "date": day, "model": models.most_common(1)[0][0] if models else None,
           "summary": "(redacted: session touched a confidential area)" if confidential else summary,
           "files_touched": [] if confidential else sorted(files)[:40], "turns": len(humans)}
    if confidential:
        rec["sensitivity"] = "confidential"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since")
    ap.add_argument("--summaries")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--transcripts-dir")
    ap.add_argument("--min-age-seconds", type=int, default=120)
    args = ap.parse_args()

    summaries: dict = {}
    if args.summaries:
        try:
            summaries = json.loads(Path(args.summaries).read_text(encoding="utf-8"))
            if not isinstance(summaries, dict) or not all(isinstance(v, str) for v in summaries.values()):
                raise ValueError("expected an object of string values")
        except (OSError, ValueError) as exc:
            emit({"brick": "session-records", "status": "failed", "reason": f"bad --summaries file: {exc}"})
            return 1

    sessions = path("core", "sessions")
    wm_file = sessions / ".watermark.json"
    if args.since:
        since = ex.parse_iso(args.since)
    elif wm_file.is_file():
        since = ex.parse_iso(json.loads(wm_file.read_text(encoding="utf-8"))["watermark"])
    else:
        since = datetime.now(timezone.utc) - timedelta(days=2)

    pdir = ex.transcripts_dir(args.transcripts_dir)
    if not pdir.is_dir():
        emit({"brick": "session-records", "status": "failed", "reason": f"transcript folder not found: {pdir}"})
        return 1
    known: set[str] = set()
    for f in sessions.glob("*/*.jsonl"):
        known |= {json.loads(ln)["id"] for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()}

    now = datetime.now(timezone.utc)
    new, newest, skipped = [], since, 0
    for p in sorted(pdir.glob("*.jsonl")):
        mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mt <= since or (now - mt).total_seconds() < args.min_age_seconds:
            continue
        newest = max(newest, mt)
        if p.stem in known:
            skipped += 1
            continue
        rec = record_for(p, summaries)
        if rec:
            new.append(rec)

    by_month: dict[Path, list[dict]] = {}
    for r in new:
        by_month.setdefault(sessions / r["date"][:4] / f"{r['date'][5:7]}.jsonl", []).append(r)
    if not args.dry_run:
        for f, recs in by_month.items():
            f.parent.mkdir(parents=True, exist_ok=True)
            with f.open("a", encoding="utf-8") as fh:
                for r in sorted(recs, key=lambda x: x["date"]):
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        sessions.mkdir(parents=True, exist_ok=True)
        wm_file.write_text(json.dumps({"watermark": newest.isoformat()}), encoding="utf-8")
    emit({"brick": "session-records", "status": "success", "dry_run": args.dry_run,
          "counts": {"new": len(new), "already_recorded": skipped,
                     "confidential": sum(1 for r in new if r.get("sensitivity"))},
          "outputs": sorted(rel(f) for f in by_month),
          "warnings": [], "observations": []})
    return 0


if __name__ == "__main__":
    sys.exit(main())
