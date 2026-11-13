"""Create the steal folders, steal.db and its schema. Idempotent.

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    home = _steal.home_dir()
    for sub in ("digests", "plans", "sources"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    _steal.inbox_dir().mkdir(parents=True, exist_ok=True)
    con = _steal.connect(must_exist=False)
    con.executescript(_steal.SCHEMA)
    con.commit()
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    _steal.emit({"status": "success", "db": _steal.rel(_steal.db_path()), "tables": tables,
                 "inbox": str(_steal.inbox_dir()), "drive_sync_configured": _steal.drive_inbox_dir() is not None})


if __name__ == "__main__":
    main()
