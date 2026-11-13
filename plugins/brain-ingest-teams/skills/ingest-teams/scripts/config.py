"""Settings for brain-ingest-teams: defaults, overridden by .claude/brain/teams.json when present."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

DEFAULTS = {
    "default_lookback_days": 7,
    "overlap_hours": 24,
    "max_attempts": 4,
    "retry_window_days": 5,
    "occurrence_mismatch_tolerance_hours": 3,
    "transcript_created_early_minutes": 10,
    "transcript_created_late_minutes": 5,
    "same_meeting_minutes": 10,
    "extra_windows_tz": {},
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        from brainos.workspace import path
        p = path("core", "module_config_dir") / "teams.json"
        if p.is_file():
            cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")})
    except Exception:  # outside a workspace: defaults
        pass
    return cfg
