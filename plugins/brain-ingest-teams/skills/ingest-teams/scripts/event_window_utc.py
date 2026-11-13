#!/usr/bin/env python3
"""Convert a calendar event's {dateTime, timeZone} (as the Outlook connector returns them) to UTC.

Outlook reports wall-clock strings plus a Windows timezone name, not an offset, so plain
fromisoformat cannot parse them. Only mapped zones convert; an unknown zone fails loudly
(a silent wrong offset would corrupt the occurrence check). Add zones through
`extra_windows_tz` in .claude/brain/teams.json.

  python3 ${CLAUDE_SKILL_DIR}/scripts/event_window_utc.py --start "2026-11-05T14:00:00.0000000" --end "2026-11-05T14:30:00.0000000" --tz "GMT Standard Time" --subject "Partner API sync"
    -> {"start_utc": "...Z", "end_utc": "...Z", "vtt_filename": "2026-11-05 14.00.00 Partner API sync.vtt"}
  python3 ${CLAUDE_SKILL_DIR}/scripts/event_window_utc.py --in-window <START_UTC> <END_UTC> <createdDateTime>...
    -> {"match": true, "matching": [...], "rejected": [...]}
     Occurrence check for recurring series: meeting.startDateTime is the SERIES start, never compare to it.
  python3 ${CLAUDE_SKILL_DIR}/scripts/event_window_utc.py --compare <EXPECTED_UTC> <ACTUAL_UTC>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

CFG = config.load()

WINDOWS_TZ_MAP = {
    "GMT Standard Time": "Europe/London",
    "UTC": "UTC",
    "Central European Standard Time": "Europe/Paris",
    "Romance Standard Time": "Europe/Paris",
    "W. Europe Standard Time": "Europe/Berlin",
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "Pacific Standard Time": "America/Los_Angeles",
    "India Standard Time": "Asia/Kolkata",
    **{k: v for k, v in CFG.get("extra_windows_tz", {}).items() if not k.startswith("_")},
}


def to_utc_iso(local_dt_str: str, windows_tz: str) -> str:
    iana = WINDOWS_TZ_MAP.get(windows_tz)
    if iana is None:
        raise ValueError(f"Unmapped Windows timezone: {windows_tz!r}. Add it to extra_windows_tz in .claude/brain/teams.json.")
    if "." in local_dt_str:  # Graph sends 7 fractional digits; fromisoformat takes 6
        base, frac = local_dt_str.split(".", 1)
        local_dt_str = f"{base}.{frac[:6].ljust(6, '0')}"
    aware = datetime.fromisoformat(local_dt_str).replace(tzinfo=ZoneInfo(iana))
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def vtt_filename(local_start: str, subject: str) -> str:
    """'YYYY-MM-DD HH.MM.00 <subject>.vtt' from the local wall-clock start; subject cleaned and capped."""
    clean = re.sub(r'[/\\:*?"<>|]', "", subject)
    clean = re.sub(r"\s+", " ", clean).strip()[:80].rstrip()
    return f"{local_start[:10]} {local_start[11:13]}.{local_start[14:16]}.00 {clean}.vtt"


def _parse_utc(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    if "." in s:
        base, rest = s.split(".", 1)
        frac = re.match(r"\d+", rest).group(0)
        s = f"{base}.{frac[:6].ljust(6, '0')}{rest[len(frac):]}"
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def window_bounds(start_utc: str, end_utc: str):
    """Accepted createdDateTime range: [start - early, end + late] (minutes, from config)."""
    return (_parse_utc(start_utc) - timedelta(minutes=CFG["transcript_created_early_minutes"]),
            _parse_utc(end_utc) + timedelta(minutes=CFG["transcript_created_late_minutes"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--tz")
    ap.add_argument("--subject")
    ap.add_argument("--compare", nargs=2, metavar=("EXPECTED_UTC", "ACTUAL_UTC"))
    ap.add_argument("--in-window", nargs="+", metavar="UTC")
    a = ap.parse_args()
    if a.in_window:
        if len(a.in_window) < 3:
            ap.error("--in-window needs START_UTC END_UTC and at least one createdDateTime")
        lo, hi = window_bounds(a.in_window[0], a.in_window[1])
        matching = [c for c in a.in_window[2:] if lo <= _parse_utc(c) <= hi]
        print(json.dumps({"match": bool(matching), "matching": matching,
                          "rejected": [c for c in a.in_window[2:] if c not in matching]}))
        return 0
    if a.compare:
        diff = abs((_parse_utc(a.compare[0]) - _parse_utc(a.compare[1])).total_seconds()) / 3600
        print(json.dumps({"match": diff <= CFG["occurrence_mismatch_tolerance_hours"], "diff_hours": round(diff, 2)}))
        return 0
    if not (a.start and a.end and a.tz):
        ap.error("--start, --end and --tz are required (or use --compare / --in-window)")
    try:
        result = {"start_utc": to_utc_iso(a.start, a.tz), "end_utc": to_utc_iso(a.end, a.tz)}
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    if a.subject is not None:
        result["vtt_filename"] = vtt_filename(a.start, a.subject)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
