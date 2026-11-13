#!/usr/bin/env python3
"""Vendor /lib/brainos into every plugins/*/lib/brainos (plugins can't import across the cache).

    python3 scripts/sync_lib.py          # copy
    python3 scripts/sync_lib.py --check  # exit 1 if any plugin copy has drifted (CI)
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "lib" / "brainos"


def plugin_dirs() -> list[Path]:
    return sorted(p for p in (REPO / "plugins").iterdir() if (p / ".claude-plugin").is_dir())


def drifted(dst: Path) -> list[str]:
    if not dst.is_dir():
        return ["<missing>"]
    cmp = filecmp.dircmp(SRC, dst, ignore=["__pycache__"])
    return cmp.left_only + cmp.right_only + cmp.diff_files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    bad = 0
    for plugin in plugin_dirs():
        dst = plugin / "lib" / "brainos"
        diff = drifted(dst)
        if args.check:
            if diff:
                bad += 1
                print(f"DRIFT {plugin.name}: {diff}")
            continue
        if diff:
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__"))
            print(f"synced {plugin.name}")
    if args.check:
        print("OK" if not bad else f"{bad} plugin(s) drifted — run scripts/sync_lib.py")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
