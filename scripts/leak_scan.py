#!/usr/bin/env python3
"""Scan the repo for leaked private terms before any commit or release.

    python3 scripts/leak_scan.py [--denylist .local/denylist.txt] [--path plugins/brain-core]

Reads a denylist of literals (one per line, '#' comments), matches each
case-insensitively on word boundaries across every text file (skipping .git and
.local), and also runs generic secret patterns. Exit code 1 on any hit, so it can
gate a pre-commit hook or CI. Hits print the term's line number in the denylist,
never the matched text, so the scan log stays clean.
The denylist itself must never be committed: the scan fails if git tracks it.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".local", "__pycache__", ".venv", "node_modules"}
TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts",
    ".txt", ".toml", ".sql", ".svg", ".mmd", ".cff", ".env", "",
}
SECRET_PATTERNS = {
    "slack token": r"xox[abprs]-[0-9A-Za-z-]{10,}",
    "github token": r"gh[pousr]_[0-9A-Za-z]{30,}",
    "anthropic key": r"sk-ant-[0-9A-Za-z_-]{20,}",
    "openai-style key": r"\bsk-[0-9A-Za-z]{32,}\b",
    "aws key": r"AKIA[0-9A-Z]{16}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "jwt": r"eyJ[0-9A-Za-z_-]{15,}\.[0-9A-Za-z_-]{15,}\.[0-9A-Za-z_-]{10,}",
    "atlassian token": r"ATATT[0-9A-Za-z_=-]{20,}",
    "absolute home path": r"/Users/[a-z][a-z0-9._-]+/",
}


def load_denylist(path: Path) -> list[str]:
    if not path.is_file():
        sys.exit(f"denylist not found: {path} (create it locally; never commit it)")
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def denylist_is_tracked(path: Path) -> bool:
    try:
        out = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)],
                             cwd=REPO, capture_output=True, text=True)
        return out.returncode == 0
    except FileNotFoundError:
        return False


def iter_files(base: Path):
    for p in base.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--denylist", default=str(REPO / ".local" / "denylist.txt"))
    ap.add_argument("--path", default=".", help="sub-path of the repo to scan")
    args = ap.parse_args()

    denylist = Path(args.denylist).resolve()
    if denylist_is_tracked(denylist):
        print("FAIL: the denylist is tracked by git — remove it from the index now.")
        return 1

    terms = load_denylist(denylist)
    term_re = [(i + 1, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![A-Za-z0-9])", re.I))
               for i, t in enumerate(terms)]
    secret_re = [(n, re.compile(p)) for n, p in SECRET_PATTERNS.items()]

    hits = 0
    base = (REPO / args.path).resolve()
    for f in iter_files(base):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = f.relative_to(REPO)
        for lineno, line in enumerate(text.splitlines(), 1):
            for idx, rx in term_re:
                if rx.search(line):
                    hits += 1
                    print(f"{rel}:{lineno}: denylisted term #{idx}")
            for name, rx in secret_re:
                if rx.search(line):
                    hits += 1
                    print(f"{rel}:{lineno}: {name}")
    print(f"{'FAIL' if hits else 'PASS'}: {hits} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
