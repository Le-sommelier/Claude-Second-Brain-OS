"""Confidentiality checks — one implementation for every module.

Patterns come from .claude/brain.json → "confidential" so each owner sets their own:

    "confidential": {
      "globs": ["growth/**"],
      "channel_patterns": ["*-leadership*", "*-leads", "*-lead-*", "*-exec*", "exec-*", "leads-*"]
    }
"""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

DEFAULT_GLOBS = ["growth/**"]
DEFAULT_CHANNELS = ["*-leadership*", "*-leads", "*-lead-*", "*-exec*", "exec-*", "leads-*"]
OPEN, CLOSE = "<!-- CONFIDENTIAL: redact-on-share -->", "<!-- /CONFIDENTIAL -->"


def _cfg() -> dict:
    try:
        from brainos.workspace import config
        return config().get("confidential", {})
    except Exception:  # outside a workspace (tests, setup) fall back to defaults
        return {}


def channel_patterns() -> list[str]:
    return _cfg().get("channel_patterns", DEFAULT_CHANNELS)


def path_globs() -> list[str]:
    return _cfg().get("globs", DEFAULT_GLOBS)


def is_confidential_channel(channel_name: str | None) -> bool:
    name = (channel_name or "").lstrip("#").lower()
    return any(fnmatch(name, p) for p in channel_patterns())


def is_confidential_path(rel_path: str | Path, frontmatter: dict | None = None) -> bool:
    if frontmatter and str(frontmatter.get("sensitivity", "")).lower() == "confidential":
        return True
    s = str(rel_path).replace("\\", "/")
    return any(fnmatch(s, g) for g in path_globs())


# Backwards-compatible name used by the Slack bricks.
is_confidential = is_confidential_channel


def wrap(block: str) -> str:
    return f"{OPEN}\n{block}\n{CLOSE}"
