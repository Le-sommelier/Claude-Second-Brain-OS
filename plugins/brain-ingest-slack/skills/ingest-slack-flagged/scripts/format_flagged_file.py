#!/usr/bin/env python3
"""Write flagged Slack messages into the day's flagged file, deduped against every past flag.

    python3 ${CLAUDE_SKILL_DIR}/scripts/format_flagged_file.py --payload "system/run/payloads/slack-flagged.json" --date 2026-11-06

Payload (Write tool, text verbatim from the MCP):
{"messages": [{
   "permalink": "...", "channel_name": "#proj-checkout", "channel_id": "C…", "ts": "1793…",
   "posted_at": "2026-11-05T09:23:14+00:00", "author": "Full Name", "author_handle": "@handle",
   "text": "...", "tags": ["checkout"], "signal_quality": "high|medium|low",
   "thread": [{"author": "...", "time": "HH:MM", "permalink": "...", "text": "..."}]}]}

The file is the ingest day's (`--date`), not the posting day's: a message flagged today that
was posted last week lands in today's file. A permalink ledger means a flag is ingested once
ever, so the search window can be wide without duplicates. Confidential channels get their
message bodies wrapped in CONFIDENTIAL markers and the file `sensitivity: confidential`.
Validation runs before any write.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from brainos import confidential, frontmatter, payload, verbatim  # noqa: E402
from brainos.workspace import emit, iso_week, parse_date, path, rel, week_dir  # noqa: E402

import slack_cfg  # noqa: E402

RANK = {"low": 0, "medium": 1, "high": 2}


def quote(text: str) -> str:
    return "\n".join(f"> {ln}" for ln in ((text or "").splitlines() or [""]))


def is_conf(channel_name: str | None) -> bool:
    return slack_cfg.is_confidential_channel(channel_name)


def render(i: int, m: dict) -> str:
    yaml_fields = {
        "author": m.get("author", "<unknown>"),
        "author_handle": m.get("author_handle", ""),
        "channel": m.get("channel_name", ""),
        "channel_id": m.get("channel_id", ""),
        "posted_at": m.get("posted_at", ""),
        "permalink": m["permalink"],
        "tags": m.get("tags", []),
        "signal_quality": m.get("signal_quality", "medium"),
        "thread_reply_count": len(m.get("thread") or []),
    }
    yaml = "\n".join(f"{k}: {frontmatter.format_value(v)}" for k, v in yaml_fields.items())
    body = quote(m.get("text", ""))
    thread = m.get("thread") or []
    if thread:
        replies = []
        for r in thread:
            lines = (r.get("text") or "").splitlines() or [""]
            replies.append(f"- **{r.get('author', '<unknown>')}** ({r.get('time', '??:??')}): {lines[0]}"
                           + "".join(f"\n  {ln}" for ln in lines[1:]))
        body += "\n\n### Thread\n\n" + "\n".join(replies)
    if is_conf(m.get("channel_name")):
        body = confidential.wrap(body)
    return f"## Message {i} — {m.get('channel_name', '')}\n\n```yaml\n{yaml}\n```\n\n{body}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload", required=True)
    ap.add_argument("--date", required=True, help="Ingest date (run-context `today`).")
    ap.add_argument("--keep-payload", action="store_true")
    args = ap.parse_args()

    data = payload.load(args.payload)
    messages = data.get("messages")
    if not isinstance(messages, list) or any(not isinstance(m, dict) or "permalink" not in m for m in messages):
        print("ERROR: payload.messages must be a list of objects with a permalink", file=sys.stderr)
        return 2

    ledger_path = path("slack", "flagged_ledger")
    seen = set(json.loads(ledger_path.read_text(encoding="utf-8"))) if ledger_path.exists() else set()
    new, batch = [], set()
    for m in messages:
        if m["permalink"] not in seen and m["permalink"] not in batch:
            new.append(m)
            batch.add(m["permalink"])
    warnings = verbatim.check([(m["permalink"], m.get("text", "")) for m in new]
                              + [(r.get("permalink", m["permalink"]), r.get("text", ""))
                                 for m in new for r in m.get("thread") or []])

    emoji = slack_cfg.settings()["flag_reaction"].strip(":")
    d = parse_date(args.date)
    out = week_dir(path("slack", "raw"), d) / f"slack-{d.isoformat()}-slack-ingest.md"
    if new:
        out.parent.mkdir(parents=True, exist_ok=True)
        existing = out.read_text(encoding="utf-8") if out.exists() else None
        prior = frontmatter.parse(existing) if existing else {}
        start = int(prior.get("message_count") or 0) + 1
        blocks = "\n---\n\n".join(render(start + i, m) for i, m in enumerate(new))
        tags = sorted(set(prior.get("tags") or []) | {t for m in new for t in m.get("tags", [])})
        quality = max([prior.get("signal_quality") or "low"] + [m.get("signal_quality", "medium") for m in new],
                      key=lambda q: RANK.get(q, 1))
        confidential_file = prior.get("sensitivity") == "confidential" or any(is_conf(m.get("channel_name")) for m in new)
        fields = {
            "source_type": "slack-flagged",
            "type": "slack-ingest",
            "title": f"Slack Ingest — {d.isoformat()}",
            "date": d.isoformat(),
            "week": iso_week(d)[1],
            "message_count": start - 1 + len(new),
            "signal_quality": quality,
            "tags": tags,
            "sensitivity": "confidential" if confidential_file else "internal",
            "wiki_processed": False,
            "todo_processed": False,
        }
        if existing:
            text = frontmatter.set_fields(existing.rstrip() + "\n\n---\n\n" + blocks, fields)
        else:
            text = (frontmatter.render(fields) + f"\n# Slack Ingest — {d.isoformat()}\n\n" + blocks
                    + f"\n---\n\n*Source: messages the owner flagged with :{emoji}: — fetched {d.isoformat()}*\n")
        out.write_text(text, encoding="utf-8")
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(sorted(seen | batch), indent=1) + "\n", encoding="utf-8")

    payload.consume(args.payload, keep=args.keep_payload)
    emit({
        "ok": True, "date": d.isoformat(), "messages_in_payload": len(messages),
        "messages_added": len(new), "already_ingested": len(messages) - len(new),
        "file": rel(out) if new else None, "verbatim_warnings": warnings,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
