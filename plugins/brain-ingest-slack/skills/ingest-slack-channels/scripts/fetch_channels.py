#!/usr/bin/env python3
"""Print the fetch plan for one target date, or save a resolved channel ID.

The Slack calls themselves are made by the brick through the Slack MCP connector; this script
holds the deterministic part: which window, which channels, which limits, what is already done.

    python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_channels.py --date 2026-11-03
    python3 ${CLAUDE_SKILL_DIR}/scripts/fetch_channels.py --set-id "#proj-checkout" C0FERN0001

The window comes from system/run/run-context.json (`slack.window[<date>]`), written by
`brain run plan`. If it is missing the script exits 2: the brick must return needs_escalation
rather than compute a window itself.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from brainos.workspace import emit, path  # noqa: E402

import ledger  # noqa: E402
import slack_cfg  # noqa: E402


def plan(date: str) -> int:
    ctx_path = path("core", "run_context")
    ctx = json.loads(ctx_path.read_text(encoding="utf-8")) if ctx_path.exists() else {}
    window = (ctx.get("slack") or {}).get("window", {}).get(date)
    if not window:
        print(f"ERROR: no slack.window[{date}] in run-context.json — run `brain run plan` first", file=sys.stderr)
        return 2
    cfg = slack_cfg.settings()
    done = ledger.load().get(date, {})
    chans = [{
        "name": c["name"], "slug": slack_cfg.slug(c["name"]), "id": c.get("id", ""),
        "transient": bool(c.get("transient")),
        "confidential": slack_cfg.is_confidential_channel(c["name"], c),
        "already_attempted": slack_cfg.slug(c["name"]) in done,
    } for c in slack_cfg.channels()]
    emit({
        "date": date, "oldest_ts": window["oldest_ts"], "latest_ts": window["latest_ts"],
        "page_limit": cfg["page_limit"], "thread_limit": cfg["thread_limit"],
        "include_bot_messages": cfg["include_bot_messages"],
        "channels": chans,
        "channels_missing_id": [c["name"] for c in chans if not c["id"]],
    })
    return 0


def set_id(name: str, channel_id: str) -> int:
    chans = slack_cfg.channels()
    hit = next((c for c in chans if slack_cfg.slug(c["name"]) == slack_cfg.slug(name)), None)
    if hit is None:
        print(f"ERROR: {name!r} is not in the channel list", file=sys.stderr)
        return 2
    hit["id"] = channel_id
    slack_cfg.save_channels(chans)
    emit({"ok": True, "channel": hit["name"], "id": channel_id})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date")
    ap.add_argument("--set-id", nargs=2, metavar=("CHANNEL", "ID"))
    a = ap.parse_args()
    if a.set_id:
        return set_id(*a.set_id)
    if a.date:
        return plan(a.date)
    ap.error("pass --date or --set-id")


if __name__ == "__main__":
    raise SystemExit(main())
