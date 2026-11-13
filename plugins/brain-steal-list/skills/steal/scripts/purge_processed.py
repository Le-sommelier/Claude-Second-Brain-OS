"""Delete archived inbox images older than N days, only when their content hash has a DB row.

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/purge_processed.py [--days N] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="default: steal.json purge_days (14)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = _steal.inbox_dir() / "_processed"
    if not base.is_dir():
        _steal.emit({"status": "success", "deleted": 0, "kept_unrecorded": 0, "note": "no _processed folder"})
        return
    known = {r[0] for r in _steal.connect().execute("SELECT DISTINCT sha256 FROM items")}
    days = args.days if args.days is not None else int(_steal.settings().get("purge_days", 14))
    cutoff = time.time() - days * 86400
    deleted, unrecorded = 0, []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _steal.IMAGE_EXT or p.stat().st_mtime > cutoff:
            continue
        if _steal.sha256_file(p) not in known:
            unrecorded.append(str(p))
            continue
        if not args.dry_run:
            p.unlink()
        deleted += 1
    for d in sorted((x for x in base.iterdir() if x.is_dir()), reverse=True):
        if not args.dry_run and not any(d.iterdir()):
            d.rmdir()
    _steal.emit({"status": "success", "dry_run": args.dry_run, "deleted": deleted, "kept_unrecorded": unrecorded})


if __name__ == "__main__":
    main()
