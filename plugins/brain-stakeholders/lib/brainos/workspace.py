"""Workspace root, config, path map and ISO-week helpers shared by every claude-second-brain-os script.

Import pattern (script at plugins/<module>/skills/<skill>/scripts/<script>.py):

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
    from brainos.workspace import root, path, rel, week_dir, emit

Root resolution: $BRAIN_ROOT, else the nearest parent of the *current directory* holding
.claude/brain.json. Never the script's own location: plugins run from the plugin cache.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

MARKER = Path(".claude") / "brain.json"


@lru_cache(maxsize=1)
def root() -> Path:
    env = os.environ.get("BRAIN_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if not (p / MARKER).is_file():
            raise RuntimeError(f"BRAIN_ROOT={p} has no {MARKER} — run /brain-core:setup there first.")
        return p
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        if (parent / MARKER).is_file():
            return parent
    raise RuntimeError(
        "No claude-second-brain-os workspace found. Run Claude Code inside your workspace, "
        "set BRAIN_ROOT, or run /brain-core:setup to create one."
    )


@lru_cache(maxsize=1)
def config() -> dict:
    """The owner profile, enabled modules and confidential patterns (.claude/brain.json)."""
    return json.loads((root() / MARKER).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def paths() -> dict:
    return json.loads((root() / ".claude" / "paths.json").read_text(encoding="utf-8"))


def path(section: str, key: str) -> Path:
    """Absolute path for a paths.json entry. Fails loudly on a missing key."""
    try:
        relative = paths()[section][key]
    except KeyError as exc:
        raise KeyError(
            f"paths.json has no {section}.{key} — is the module that owns it installed? "
            "Re-run /brain-core:setup to merge module paths."
        ) from exc
    return root() / relative


def owner() -> dict:
    """{"name", "first_name", "role", "company", "person_id", ...} from brainos.json."""
    return config().get("owner", {})


def rel(p: Path | str) -> str:
    """Workspace-relative string for a path."""
    return str(Path(p).resolve().relative_to(root()))


def iso_week(d: date) -> tuple[str, str]:
    iso = d.isocalendar()
    return str(iso.year), f"{iso.year}-W{iso.week:02d}"


def week_dir(base: Path, d: date) -> Path:
    """<base>/YYYY/YYYY-Www — the layout every raw source uses."""
    year, week = iso_week(d)
    return base / year / week


def parse_date(value: str) -> date:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def emit(result: dict) -> None:
    """Print a script's result as the single JSON object the calling skill reads."""
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
