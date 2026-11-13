"""Optional: move new screenshots from a synced folder (Google Drive, iCloud, Dropbox) into the local inbox.

Configure steal.json -> "drive_inbox" with the folder your phone saves screenshots into. Unset means this script
reports `skipped` and exits 0, so the nightly run never fails on a feature you did not enable.
Safe move: copy, verify sha256 on the copy, only then delete the original. Never deletes on a mismatch.
Where the OS blocks the process from reading that folder (macOS privacy settings), the error is reported and
nothing is retried; run this script from your own terminal instead.
Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/sync_drive_inbox.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = _steal.drive_inbox_dir()
    if src is None:
        _steal.emit({"status": "skipped", "reason": "no drive_inbox configured in .claude/brain/steal.json"})
        return
    dst = _steal.inbox_dir()
    if not src.is_dir():
        _steal.emit({"status": "failed", "reason": f"synced inbox not found or not readable: {src}"})
        raise SystemExit(1)
    try:
        files = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in _steal.IMAGE_EXT)
    except PermissionError as exc:
        _steal.emit({"status": "failed", "reason": f"permission denied on the synced inbox: {exc}"})
        raise SystemExit(1)

    dst.mkdir(parents=True, exist_ok=True)
    moved, failed = [], []
    for p in files:
        target = dst / p.name
        if target.exists():
            target = dst / f"{p.stem}-{_steal.sha256_file(p)[:8]}{p.suffix}"
        if args.dry_run:
            moved.append(p.name)
            continue
        try:
            shutil.copy2(p, target)
            if _steal.sha256_file(target) != _steal.sha256_file(p):
                target.unlink()
                failed.append({"file": p.name, "reason": "hash mismatch after copy, original kept"})
                continue
            os.remove(p)
            moved.append(p.name)
        except OSError as exc:
            failed.append({"file": p.name, "reason": str(exc)})
    _steal.emit({"status": "success" if not failed else "partial", "dry_run": args.dry_run,
                 "counts": {"moved": len(moved), "failed": len(failed)}, "moved": moved, "failed": failed})


if __name__ == "__main__":
    main()
