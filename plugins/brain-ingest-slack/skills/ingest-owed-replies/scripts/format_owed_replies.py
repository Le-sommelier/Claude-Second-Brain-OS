#!/usr/bin/env python3
"""Deterministic owed-replies formatter (no LLM, no MCP).

    python3 ${CLAUDE_SKILL_DIR}/scripts/format_owed_replies.py --payload "system/run/payloads/owed-replies.json" --date 2026-11-06

The brick does the Slack searching and writes a JSON array of candidate items; this script
turns it into one digest (and deletes the payload):

  inbox/owed-replies/<date>-owed-replies.md   (path from paths.json slack.owed_dir)

Item shape: {kind, permalink, channel, author, ts, text, confidential}
with kind one of inbox_flag | dm | mention. Items from confidential channels (flag, or a
channel name matching .claude/brain.json) are wrapped in CONFIDENTIAL markers.
If the payload is missing or not a JSON array, the script exits non-zero and writes nothing.
The digest has no `wiki_processed` flag: it is a working view, not a pending-queue item.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from brainos import payload, verbatim  # noqa: E402
from brainos.workspace import emit, iso_week, path, rel  # noqa: E402
from brainos import confidential  # noqa: E402

import slack_cfg  # noqa: E402

KIND_HEADINGS = [("inbox_flag", "Flagged"), ("dm", "DMs"), ("mention", "Mentions")]


def dedupe_and_sort(items: list[dict]) -> list[dict]:
    """Dedupe by permalink (keep first), then newest-first by ts."""
    seen, out = set(), []
    for item in items:
        link = item.get("permalink")
        if link in seen:
            continue
        seen.add(link)
        out.append(item)

    def ts(i):
        try:
            return float(i.get("ts"))
        except (TypeError, ValueError):
            return 0.0
    return sorted(out, key=ts, reverse=True)


def entry_md(item: dict) -> str:
    channel = item.get("channel") or ""
    quote = "\n".join(f"> {ln}" for ln in ((item.get("text") or "").splitlines() or [""]))
    header = f"- **{item.get('author') or 'Unknown'}** ({channel}) — [link]({item.get('permalink') or ''})"
    if bool(item.get("confidential")) or slack_cfg.is_confidential_channel(channel):
        return header + " — _channel is confidential_\n\n" + confidential.wrap(quote)
    return header + "\n\n" + quote


def build_digest(items: list[dict], d: date) -> str:
    head = "\n".join([
        "---", "type: owed-replies", f"date: {d.isoformat()}", f"week: {iso_week(d)[1]}",
        "generated_by: brain-ingest-slack:ingest-owed-replies", f"count: {len(items)}", "---", "",
        f"# Owed replies — {d.isoformat()}", "", ""])
    if not items:
        return head + "No owed replies detected.\n"
    by_kind: dict[str, list[dict]] = {}
    for item in items:
        by_kind.setdefault(item.get("kind") or "other", []).append(item)
    known = {k for k, _ in KIND_HEADINGS}
    blocks = []
    for kind, heading in KIND_HEADINGS + [(k, k) for k in by_kind if k not in known]:
        if by_kind.get(kind):
            blocks.append(f"## {heading}\n\n" + "\n\n".join(entry_md(i) for i in by_kind[kind]))
    return head + "\n\n".join(blocks) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload", required=True)
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--keep-payload", action="store_true")
    args = ap.parse_args()
    try:
        items = dedupe_and_sort(payload.load(args.payload, expect=list))
    except (FileNotFoundError, ValueError) as exc:  # includes JSON decode errors
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    d = date.fromisoformat(args.date)
    warnings = verbatim.check([(i.get("permalink", "<no-permalink>"), i.get("text", "")) for i in items])
    out = path("slack", "owed_dir") / f"{d.isoformat()}-owed-replies.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_digest(items, d), encoding="utf-8")
    payload.consume(args.payload, keep=args.keep_payload)
    by_kind: dict[str, int] = {}
    for i in items:
        k = i.get("kind") or "other"
        by_kind[k] = by_kind.get(k, 0) + 1
    emit({"ok": True, "count": len(items), "by_kind": by_kind, "file": rel(out), "verbatim_warnings": warnings})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
