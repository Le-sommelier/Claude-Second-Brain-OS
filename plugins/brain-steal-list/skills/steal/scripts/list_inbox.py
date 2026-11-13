"""List screenshots waiting in the local inbox and flag ones already reviewed (by content hash).

HEIC/HEIF files get a JPEG copy in <steal home>/.tmp/ (view_path) so they can be read as images; the conversion
uses macOS `sips` and is skipped, with a warning, where it is not installed.
Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/list_inbox.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402


def main() -> None:
    inbox = _steal.inbox_dir()
    if not inbox.is_dir():
        _steal.emit({"status": "failed", "reason": f"inbox not found: {inbox}", "new": [], "dupes": []})
        raise SystemExit(1)
    try:
        entries = sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in _steal.IMAGE_EXT)
    except PermissionError as exc:
        _steal.emit({"status": "failed", "reason": f"permission denied on {inbox}: {exc}", "new": [], "dupes": []})
        raise SystemExit(1)

    con = _steal.connect()
    seen = {r[0] for r in con.execute("SELECT DISTINCT sha256 FROM items")}
    tmp = _steal.home_dir() / ".tmp"
    new, dupes, warnings, batch_hashes = [], [], [], set()
    for p in entries:
        digest = _steal.sha256_file(p)
        row = {"path": str(p), "name": p.name, "sha256": digest, "size": p.stat().st_size,
               "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
        if digest in seen or digest in batch_hashes:
            dupes.append(row)
            continue
        batch_hashes.add(digest)
        row["view_path"] = str(p)
        if p.suffix.lower() in (".heic", ".heif"):
            if not shutil.which("sips"):
                warnings.append(f"{p.name}: HEIC needs macOS sips to convert; convert it to JPEG or PNG by hand")
            else:
                tmp.mkdir(parents=True, exist_ok=True)
                out = tmp / f"{digest[:16]}.jpg"
                res = subprocess.run(["sips", "-s", "format", "jpeg", str(p), "--out", str(out)],
                                     capture_output=True, text=True)
                if res.returncode == 0 and out.is_file():
                    row["view_path"] = str(out)
        new.append(row)
    _steal.emit({"status": "success", "inbox": str(inbox), "new": new, "dupes": dupes, "warnings": warnings,
                 "counts": {"new": len(new), "dupes": len(dupes)}})


if __name__ == "__main__":
    main()
