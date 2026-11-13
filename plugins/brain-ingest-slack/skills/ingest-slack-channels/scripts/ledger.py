#!/usr/bin/env python3
"""Per-(date, channel) attempt ledger. A key present = attempted (0 messages = silent day);
a key absent = never attempted = a real gap.

Written by format_channel_file.py after every channel attempt. Manual queries:

    python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --query-date 2026-11-03
    python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --coverage --dates 2026-11-02,2026-11-03

`--coverage` lists the dates (weekends exempt) on which a non-transient watched channel has no
ledger entry. The orchestrator treats those as partial dates and re-plans them next run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from brainos.workspace import emit, parse_date, path  # noqa: E402

import slack_cfg  # noqa: E402


def _ledger() -> Path:
    return path("slack", "channel_ledger")


def load() -> dict:
    p = _ledger()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record(date_str: str, channel_slug: str, messages: int, file_rel: str | None = None) -> None:
    data = load()
    entry = {"attempted": True, "messages": messages}
    if messages and file_rel:
        entry["file"] = file_rel
    data.setdefault(date_str, {})[channel_slug] = entry
    p = _ledger()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def coverage(dates: list[str]) -> list[str]:
    watched = [slack_cfg.slug(c["name"]) for c in slack_cfg.channels() if not c.get("transient")]
    ledger = load()
    return [d for d in dates
            if parse_date(d).weekday() < 5 and any(ch not in ledger.get(d, {}) for ch in watched)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Query the Slack channel ingest ledger.")
    ap.add_argument("--query-date")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--dates", help="Comma-separated dates for --coverage.")
    a = ap.parse_args()
    if a.coverage:
        if not a.dates:
            ap.error("--coverage needs --dates")
        emit({"dates_partial": coverage([d.strip() for d in a.dates.split(",") if d.strip()])})
    elif a.query_date:
        emit(load().get(a.query_date, {}))
    else:
        ap.error("pass --query-date or --coverage")
