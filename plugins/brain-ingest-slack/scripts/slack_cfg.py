"""Shared config loader for the brain-ingest-slack scripts.

Reads two owner-editable files (copied from templates/ by setup, never overwritten):
  paths.json slack.channels_config  -> the watched channel list
  paths.json slack.settings         -> timezone, workspace URL, flag emoji, limits

Imported by the three skills' scripts with:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
"""
from __future__ import annotations

import json
from datetime import timezone, tzinfo
from zoneinfo import ZoneInfo

from brainos import confidential
from brainos.workspace import config, path

DEFAULTS = {
    "timezone": None,                 # falls back to owner.timezone, then UTC
    "workspace_url": "https://example.slack.com",
    "flag_reaction": "inbox_tray",    # the emoji you react with to flag a message (no colons)
    "owner_slack_user_id": "",
    "include_bot_messages": False,
    "hot_day_threshold": 100,
    "stale_transient_dead_days": 7,
    "page_limit": 100,
    "thread_limit": 1000,
}


def settings() -> dict:
    p = path("slack", "settings")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if not k.startswith("_")}}


def channels() -> list[dict]:
    p = path("slack", "channels_config")
    if not p.exists():
        raise FileNotFoundError(f"channel list not found: {p} — run /brain-core:setup to copy the template")
    return json.loads(p.read_text(encoding="utf-8")).get("channels", [])


def save_channels(chans: list[dict]) -> None:
    p = path("slack", "channels_config")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["channels"] = chans
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(name: str) -> str:
    return name.lstrip("#").lower()


def find_channel(name: str) -> dict | None:
    return next((c for c in channels() if slug(c["name"]) == slug(name)), None)


def local_tz() -> tzinfo:
    name = settings()["timezone"] or config().get("owner", {}).get("timezone") or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def is_confidential_channel(name: str | None, channel: dict | None = None) -> bool:
    """Confidential when the channel entry says so or its name matches a brain.json pattern."""
    if channel and str(channel.get("sensitivity", "")).lower() == "confidential":
        return True
    if channel is None and name:
        channel = find_channel(name) if _safe_has_config() else None
        if channel and str(channel.get("sensitivity", "")).lower() == "confidential":
            return True
    return confidential.is_confidential_channel(name)


def _safe_has_config() -> bool:
    try:
        return path("slack", "channels_config").exists()
    except Exception:
        return False
