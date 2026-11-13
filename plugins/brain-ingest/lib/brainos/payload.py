"""Payload hand-off between a skill's model step and its formatter script.

The model writes JSON with the Write tool into system/run/payloads/; the formatter loads it,
validates it, writes the canonical file, then deletes the payload. Validate first, write
second: a bad payload raises before anything on disk changes.
"""
from __future__ import annotations

import json
from pathlib import Path

from brainos.workspace import path


def payload_dir() -> Path:
    d = path("core", "run_dir") / "payloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load(p: str | Path, expect: type = dict):
    p = Path(p)
    if not p.is_file():
        raise FileNotFoundError(f"payload not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, expect):
        raise ValueError(f"payload must be a JSON {expect.__name__}, got {type(data).__name__}")
    return data


def consume(p: str | Path, keep: bool = False) -> None:
    if not keep:
        Path(p).unlink(missing_ok=True)
