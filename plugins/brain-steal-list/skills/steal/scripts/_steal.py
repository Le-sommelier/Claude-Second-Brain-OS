"""Shared helpers for the steal-list scripts: paths, DB connection, schema, enums, settings.

Scripts import it with:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _steal
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos.workspace import emit, path, rel, root  # noqa: E402,F401

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}
VERDICTS = ("steal", "adapt", "watch", "skip")
DEFAULT_TARGETS = ("wiki", "artifact-tooling", "personal-tools", "strategy", "brain-work", "none")
EFFORTS = ("S", "M", "L")
NOVELTY = ("high", "med", "low")
EVIDENCE = ("solid", "thin", "hype")
CONFIDENCE = ("high", "med", "low")
STATUSES = ("proposed", "adopted", "plan_drafted", "plan_approved", "done", "rejected", "deferred", "skipped")

# from-status -> allowed to-statuses. plan_approved is the build gate: only from plan_drafted.
TRANSITIONS = {
    "proposed": ("adopted", "rejected", "deferred"),
    "deferred": ("adopted", "rejected"),
    "adopted": ("plan_drafted", "rejected", "deferred"),
    "plan_drafted": ("plan_approved", "adopted", "rejected", "deferred"),
    "plan_approved": ("done", "plan_drafted", "rejected", "deferred"),
    "skipped": ("adopted",),
    "rejected": ("adopted",),
    "done": (),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  n_new INTEGER DEFAULT 0,
  n_dupe INTEGER DEFAULT 0,
  n_failed INTEGER DEFAULT 0,
  batch_pov TEXT
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sha256 TEXT NOT NULL,
  seq INTEGER NOT NULL DEFAULT 0,
  run_id TEXT REFERENCES runs(run_id),
  captured_at TEXT,
  reviewed_at TEXT NOT NULL,
  platform TEXT,
  author_handle TEXT,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  claims TEXT,
  named_tools TEXT,
  topics TEXT,
  source_url TEXT,
  UNIQUE (sha256, seq)
);
CREATE TABLE IF NOT EXISTS verdicts (
  item_id INTEGER PRIMARY KEY REFERENCES items(id),
  verdict TEXT NOT NULL CHECK (verdict IN ('steal','adapt','watch','skip')),
  targets TEXT,
  why TEXT NOT NULL,
  how TEXT,
  effort TEXT,
  novelty TEXT,
  evidence TEXT,
  confidence TEXT,
  pov TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  item_id INTEGER PRIMARY KEY REFERENCES items(id),
  status TEXT NOT NULL,
  decided_at TEXT,
  note TEXT,
  plan_path TEXT,
  link TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL REFERENCES items(id),
  status TEXT NOT NULL,
  at TEXT NOT NULL,
  note TEXT
);
"""


def settings() -> dict:
    """steal.json merged over defaults. A missing or unreadable file means defaults, never a crash."""
    base = {"drive_inbox": None, "purge_days": 14, "targets": list(DEFAULT_TARGETS),
            "setup_scan": [".claude/skills", ".claude/commands", ".claude/agents", ".claude/rules", ".claude/hooks"]}
    try:
        base.update(json.loads(path("steal", "config").read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError):
        pass
    return base


def targets() -> tuple[str, ...]:
    return tuple(settings()["targets"])


def home_dir() -> Path:
    """Folder holding steal.db, digests/, plans/, board.md."""
    return path("steal", "home")


def inbox_dir() -> Path:
    """Local inbox the review reads. $STEAL_INBOX overrides."""
    raw = os.environ.get("STEAL_INBOX")
    return Path(os.path.expanduser(raw)).resolve() if raw else path("steal", "inbox")


def drive_inbox_dir() -> Path | None:
    """The optional synced folder outside the workspace (steal.json -> drive_inbox), or None."""
    raw = settings().get("drive_inbox")
    return Path(os.path.expanduser(raw)) if raw else None


def sources_dir() -> Path:
    """Text sources (pasted transcripts, articles). Kept here, never in raw/sources (that queue feeds the wiki)."""
    return path("steal", "sources")


def db_path() -> Path:
    return path("steal", "db")


def migrate(con: sqlite3.Connection) -> None:
    """Idempotent column adds for DBs created before a schema change."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(items)")}
    if cols and "source_url" not in cols:
        con.execute("ALTER TABLE items ADD COLUMN source_url TEXT")
        con.commit()


def connect(must_exist: bool = True) -> sqlite3.Connection:
    p = db_path()
    if must_exist and not p.is_file():
        raise SystemExit(f"steal.db missing at {rel(p)}. Run scripts/init_db.py first.")
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    migrate(con)
    return con


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jlist(value) -> str:
    """Store lists as JSON text; None/'' -> '[]'."""
    if value in (None, ""):
        return "[]"
    if isinstance(value, str):
        value = [value]
    return json.dumps(list(value), ensure_ascii=False)
