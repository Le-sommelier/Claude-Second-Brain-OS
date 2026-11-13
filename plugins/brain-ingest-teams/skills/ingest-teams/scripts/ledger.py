#!/usr/bin/env python3
"""Per-calendar-event attempt ledger for ingest-teams.

Tracks which calendar events were already checked for a Teams transcript, so re-runs don't
re-fetch what is saved and don't hammer events that will never have one. Ledger file:
paths.json meetings.ledger (default system/run/teams-ledger.json).

Statuses
  fetched                                   terminal success, never retried
  cancelled / no_online_meeting / not_teams_meeting / all_day
                                            permanent skips (structural properties of the event)
  transcripts_empty / meeting_not_found / occurrence_mismatch
                                            retryable (Teams can publish transcripts late)

One single-line command per call, from the workspace root:
  python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --window
  python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --should-attempt --event-id ID --start 2026-11-05T14:00:00+00:00
  python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --record --event-id ID --subject "Partner API sync" --start ... --status fetched --vtt-path inbox/transcripts/teams/<name>.vtt
  python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --set-last-run 2026-11-05T15:00:00+00:00
  python3 ${CLAUDE_SKILL_DIR}/scripts/ledger.py --summary --since 2026-11-05T14:00:00+00:00
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainos.workspace import emit, path as ws_path  # noqa: E402
import config  # noqa: E402

CFG = config.load()
PERMANENT_SKIP_STATUSES = {"cancelled", "no_online_meeting", "not_teams_meeting", "all_day"}
RETRYABLE_STATUSES = {"transcripts_empty", "meeting_not_found", "occurrence_mismatch"}
TERMINAL_SUCCESS_STATUS = "fetched"


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _load(p: Path) -> dict:
    if not p.exists():
        return {"last_run": None, "events": {}}
    data = json.loads(p.read_text(encoding="utf-8"))  # bad JSON raises: never overwrite a corrupt ledger
    data.setdefault("last_run", None)
    data.setdefault("events", {})
    return data


def _save(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def window(p: Path, now: datetime | None = None) -> dict:
    """Search window: last_run minus overlap, or the default lookback on a first run. Until = now."""
    now = now or datetime.now(timezone.utc)
    last = _load(p)["last_run"]
    since = (_parse_iso(last) - timedelta(hours=CFG["overlap_hours"])) if last else now - timedelta(days=CFG["default_lookback_days"])
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {"since": since.strftime(fmt), "until": now.strftime(fmt), "last_run": last}


def summary(p: Path, since_iso: str) -> dict:
    since = _parse_iso(since_iso)
    files, by_status = [], {}
    for entry in _load(p)["events"].values():
        checked = entry.get("last_checked")
        if not checked or _parse_iso(checked) < since:
            continue
        by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
        if entry["status"] == TERMINAL_SUCCESS_STATUS and entry.get("vtt_path"):
            files.append(entry["vtt_path"])
    return {"fetched": len(files), "files": files, "by_status": by_status}


def should_attempt(p: Path, event_id: str, start_iso: str, now: datetime | None = None) -> dict:
    entry = _load(p)["events"].get(event_id)
    if entry is None:
        return {"should_attempt": True, "status": None, "attempts": 0, "reason": "never_checked"}
    status, attempts = entry.get("status"), entry.get("attempts", 0)

    def answer(go: bool, reason: str) -> dict:
        return {"should_attempt": go, "status": status, "attempts": attempts, "reason": reason}

    if status == TERMINAL_SUCCESS_STATUS:
        return answer(False, "already_fetched")
    if status in PERMANENT_SKIP_STATUSES:
        return answer(False, "permanent_skip")
    if status in RETRYABLE_STATUSES:
        if attempts >= CFG["max_attempts"]:
            return answer(False, "max_attempts_reached")
        try:
            age_days = ((now or datetime.now(timezone.utc)) - _parse_iso(start_iso)).days
        except ValueError:
            age_days = 0
        if age_days > CFG["retry_window_days"]:
            return answer(False, "retry_window_expired")
        return answer(True, "retryable")
    return answer(True, "unknown_status")


def record_event(p: Path, event_id: str, subject: str, start_iso: str, status: str, vtt_path: str | None = None) -> None:
    data = _load(p)
    entry = data["events"].get(event_id, {"attempts": 0})
    entry.update(subject=subject, start=start_iso, status=status,
                 attempts=entry.get("attempts", 0) + 1,
                 last_checked=datetime.now(timezone.utc).isoformat())
    if status == TERMINAL_SUCCESS_STATUS and vtt_path:
        entry["vtt_path"] = vtt_path
    data["events"][event_id] = entry
    _save(p, data)


def set_last_run(p: Path, iso_ts: str) -> None:
    data = _load(p)
    data["last_run"] = iso_ts
    _save(p, data)


def main() -> int:
    ap = argparse.ArgumentParser(description="Track per-event Teams transcript fetch attempts.")
    ap.add_argument("--window", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--since")
    ap.add_argument("--set-last-run", metavar="ISO_TS")
    ap.add_argument("--should-attempt", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--event-id")
    ap.add_argument("--subject")
    ap.add_argument("--start")
    ap.add_argument("--status")
    ap.add_argument("--vtt-path")
    a = ap.parse_args()
    p = ws_path("meetings", "ledger")
    if a.window:
        emit(window(p))
    elif a.summary:
        if not a.since:
            ap.error("--summary requires --since")
        emit(summary(p, a.since))
    elif a.set_last_run:
        set_last_run(p, a.set_last_run)
        emit({"ok": True, "last_run": a.set_last_run})
    elif a.should_attempt:
        if not (a.event_id and a.start):
            ap.error("--should-attempt requires --event-id and --start")
        emit(should_attempt(p, a.event_id, a.start))
    elif a.record:
        if not (a.event_id and a.subject and a.start and a.status):
            ap.error("--record requires --event-id, --subject, --start and --status")
        record_event(p, a.event_id, a.subject, a.start, a.status, a.vtt_path)
        emit({"ok": True, "event_id": a.event_id, "status": a.status})
    else:
        ap.error("choose one of --window / --set-last-run / --should-attempt / --record / --summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
