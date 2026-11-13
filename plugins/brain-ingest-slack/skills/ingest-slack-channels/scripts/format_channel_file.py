#!/usr/bin/env python3
"""Write one channel's fetched messages into per-channel-per-day files and record the ledger.

    python3 ${CLAUDE_SKILL_DIR}/scripts/format_channel_file.py --payload "system/run/payloads/slack-proj-checkout-2026-11-03.json"
    python3 ${CLAUDE_SKILL_DIR}/scripts/format_channel_file.py --empty --channel "#proj-checkout" --date 2026-11-03

Payload (written by the brick with the Write tool, verbatim from slack_read_channel/thread):
{
  "channel_name": "#proj-checkout", "channel_id": "C0FERN0001", "date": "2026-11-03",
  "messages": [{"ts": "1793611000.000100", "user_name": "...", "text": "...",
                "reactions": [{"name": "white_check_mark", "count": 2}],
                "thread": [{"ts": "...", "user_name": "...", "text": "..."}]}]
}

`ts` and `user_name` are required on every message and reply. `permalink` and `time` are optional:
the Slack MCP returns no permalinks, so the formatter derives them from channel_id + ts
(`<workspace_url>/archives/<C>/p<ts without dot>`, replies add `?thread_ts=<root>&cid=<C>`),
and always recomputes `time` from ts in the configured timezone.

Each root message is filed under its own local posting date, so the fetch overlap (previous
day) lands late messages in yesterday's file instead of duplicating them into today's.
Dedup is by message ts (parsed out of the permalink), so permalink format drift never
duplicates a message. When a merge adds messages, frontmatter counts are recomputed and
`wiki_processed` is reset to false so downstream bricks pick up the new content.
The ledger entry is recorded for the payload's `date`, transient channels included.
Validation runs before any write: a bad payload changes nothing on disk.

Confidential channels (channel entry `sensitivity: confidential`, or a name matching the
patterns in .claude/brain.json) get `sensitivity: confidential`, `redact_content: true`, and
every message body wrapped in CONFIDENTIAL markers.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from brainos import confidential, frontmatter, payload, verbatim  # noqa: E402
from brainos.workspace import emit, iso_week, parse_date, path, rel, week_dir  # noqa: E402

import ledger  # noqa: E402
import slack_cfg  # noqa: E402

CONFIDENTIAL_NOTE = ("> Confidential channel. Stored for the owner's reference only: never quote it in any "
                     "shared output. See `.claude/rules/confidential.md`.")
TS_IN_LINK = re.compile(r"/p(\d{10})\.?(\d{6})")


def ts_from_permalink(link: str) -> str | None:
    m = TS_IN_LINK.search(link or "")
    return f"{m.group(1)}.{m.group(2)}" if m else None


def derive_permalink(base: str, channel_id: str, ts: str, root_ts: str | None = None) -> str:
    link = f"{base.rstrip('/')}/archives/{channel_id}/p{ts.replace('.', '')}"
    if root_ts and root_ts != ts:
        link += f"?thread_ts={root_ts}&cid={channel_id}"
    return link


def local_time(ts: str, tz) -> str | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone(tz).strftime("%H:%M")
    except (TypeError, ValueError):
        return None


def fill_derived(messages: list[dict], channel_id: str, base: str, tz) -> None:
    """Fill missing permalinks from channel_id + ts and recompute `time` in the local timezone."""
    for m in messages:
        for msg, root_ts in [(m, None)] + [(r, m.get("ts")) for r in (m.get("thread") or [])]:
            ts = msg.get("ts")
            if not ts:
                continue
            if not msg.get("permalink") and channel_id:
                msg["permalink"] = derive_permalink(base, channel_id, str(ts), root_ts)
            t = local_time(ts, tz)
            if t:
                msg["time"] = t


def validate_messages(messages: list[dict]) -> None:
    """Reject a payload missing attribution, ts or permalink on any message or reply."""
    missing = []
    for i, m in enumerate(messages):
        for field in ("ts", "permalink", "user_name"):
            if not m.get(field):
                missing.append(f"messages[{i}].{field}")
        for j, r in enumerate(m.get("thread") or []):
            for field in ("ts", "permalink", "user_name"):
                if not r.get(field):
                    missing.append(f"messages[{i}].thread[{j}].{field}")
    if missing:
        raise ValueError(
            "payload missing required fields (verbatim passthrough needs ts and user_name "
            f"from the MCP response, not just text; permalink is derived from ts): {', '.join(missing)}"
        )


def posted_date(msg: dict, fallback: date, tz) -> date:
    try:
        return datetime.fromtimestamp(float(msg["ts"]), tz=timezone.utc).astimezone(tz).date()
    except (KeyError, TypeError, ValueError):
        return fallback


def render_message(msg: dict, redact: bool) -> str:
    lines = [f"## {msg.get('time', '??:??')} — {msg.get('user_name', '<unknown>')}"]
    if msg.get("permalink"):
        lines.append(f"> permalink: {msg['permalink']}")
    lines.append("")
    text = (msg.get("text") or "").strip()
    lines += [confidential.OPEN, text, confidential.CLOSE] if redact else [text]
    if msg.get("reactions"):
        lines += ["", "_Reactions: " + " ".join(f":{r['name']}: ×{r['count']}" for r in msg["reactions"]) + "_"]
    thread = msg.get("thread") or []
    if thread:
        lines += ["", f"### Thread ({len(thread)} repl{'y' if len(thread) == 1 else 'ies'})", ""]
        for r in thread:
            link = f" ([permalink]({r['permalink']}))" if r.get("permalink") else ""
            lines.append(f"- **{r.get('time', '??:??')} — {r.get('user_name', '<unknown>')}**{link}")
            body = (r.get("text") or "").strip().splitlines() or [""]
            if redact:
                lines.append(f"  {confidential.OPEN}")
            lines += [f"  {ln}" for ln in body]
            if redact:
                lines.append(f"  {confidential.CLOSE}")
        lines.append("")
    return "\n".join(lines)


def write_day(channel: dict, channel_id: str, d: date, msgs: list[dict], redact: bool,
              stamp: str | None = None) -> tuple[Path, int]:
    """Create or merge the file for (channel, d). Returns (path, messages actually added)."""
    s = slack_cfg.slug(channel["name"])
    out = week_dir(path("slack", "raw"), d) / f"slack-{d.isoformat()}-{s}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    existing = out.read_text(encoding="utf-8") if out.exists() else None
    if existing:
        known = {ts_from_permalink(link) for link in re.findall(r"permalink:\s*(\S+)", existing)}
        known.discard(None)
        msgs = [m for m in msgs if ts_from_permalink(m.get("permalink", "")) not in known]
        if not msgs:
            return out, 0
    blocks = "\n\n".join(render_message(m, redact) for m in msgs)
    contributors = {m.get("user_name") for m in msgs if m.get("user_name")}
    threads = sum(1 for m in msgs if m.get("thread"))

    if existing:
        fm = frontmatter.parse(existing)
        stamp = stamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        text = existing.rstrip() + f"\n\n---\n\n## Additional messages — {stamp}\n\n" + blocks + "\n"
        text = frontmatter.set_fields(text, {
            "source_type": "slack-channel",
            "message_count": int(fm.get("message_count") or 0) + len(msgs),
            "thread_count": int(fm.get("thread_count") or 0) + threads,
            "contributors": sorted(set(fm.get("contributors") or []) | contributors),
            "wiki_processed": False,
        })
        out.write_text(text, encoding="utf-8")
        return out, len(msgs)

    fields = {
        "id": f"slack-{d.isoformat()}-{s}",
        "source_type": "slack-channel",
        "type": "slack-ingest",
        "date": d.isoformat(),
        "week": iso_week(d)[1],
        "channel": s,
        "channel_id": channel_id,
        "tags": channel.get("tags", []),
        "sensitivity": "confidential" if redact else channel.get("sensitivity", "internal"),
        "redact_content": redact,
        "tech_decisions": bool(channel.get("tech_decisions")),
        "message_count": len(msgs),
        "thread_count": threads,
        "contributors": sorted(contributors),
        "wiki_processed": False,
    }
    head = frontmatter.render(fields) + f"\n# {channel['name']} — {d.isoformat()}\n\n"
    if redact:
        head += CONFIDENTIAL_NOTE + "\n\n"
    out.write_text(head + blocks + "\n", encoding="utf-8")
    return out, len(msgs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload")
    ap.add_argument("--empty", action="store_true", help="Record a zero-message attempt; no payload.")
    ap.add_argument("--channel")
    ap.add_argument("--date")
    ap.add_argument("--keep-payload", action="store_true")
    args = ap.parse_args()

    if args.empty:
        if not (args.channel and args.date):
            ap.error("--empty needs --channel and --date")
        data = {"channel_name": args.channel, "date": args.date, "messages": []}
    elif args.payload:
        data = payload.load(args.payload)
    else:
        ap.error("pass --payload or --empty")

    channel = slack_cfg.find_channel(data.get("channel_name", ""))
    if channel is None:
        print(f"ERROR: channel {data.get('channel_name')!r} not in the channel list", file=sys.stderr)
        return 2
    cfg, tz = slack_cfg.settings(), slack_cfg.local_tz()
    target = parse_date(data["date"])
    messages = data.get("messages") or []
    channel_id = data.get("channel_id") or channel.get("id", "")
    fill_derived(messages, channel_id, cfg["workspace_url"], tz)
    try:
        validate_messages(messages)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    warnings = verbatim.check(verbatim.slack_texts(messages))
    redact = slack_cfg.is_confidential_channel(channel["name"], channel)

    by_day: dict[date, list[dict]] = {}
    for m in messages:
        by_day.setdefault(posted_date(m, target, tz), []).append(m)

    files, added, target_file = [], 0, None
    for d in sorted(by_day):
        out, n = write_day(channel, channel_id, d, by_day[d], redact)
        if n:
            files.append(rel(out))
            added += n
        if d == target and out.exists():
            target_file = out

    s = slack_cfg.slug(channel["name"])
    file_for_ledger = str(target_file.relative_to(path("slack", "raw"))) if target_file else None
    ledger.record(target.isoformat(), s, len(by_day.get(target, [])), file_for_ledger)
    if args.payload:
        payload.consume(args.payload, keep=args.keep_payload)

    emit({
        "ok": True, "channel": s, "date": target.isoformat(), "confidential": redact,
        "messages_fetched": len(messages), "messages_added": added,
        "files_written": files, "verbatim_warnings": warnings,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
