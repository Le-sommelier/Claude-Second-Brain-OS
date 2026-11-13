#!/usr/bin/env python3
"""Phase 1 of growth-signals: deterministic signal mining. Pure read plus one confidential output file.

    python3 mine_signals.py [--since YYYY-MM-DD | --days N | --backfill] [--today YYYY-MM-DD] [--no-actor-filter]

Walks the files listed in .claude/brain/growth/source-config.json (meeting summaries, project
decisions, digests, the growth folder), applies signal-patterns.json, drops snippets whose hash is
already in the candidates file, and writes the raw candidates to growth/development/run/. The
output is confidential (it holds snippets), so only counts go to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growthlib as gl  # noqa: E402
from brainos.confidential import is_confidential_path  # noqa: E402
from brainos.workspace import root, rel, emit, parse_date  # noqa: E402
from brainos import frontmatter  # noqa: E402

DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def file_date(p: Path, fm: dict) -> date | None:
    m = DATE_IN_NAME.search(p.name)
    for cand in ([m.group(1)] if m else []) + [str(fm.get("date") or "")]:
        try:
            return parse_date(cand)
        except ValueError:
            continue
    return None


def senior_names(cfg: dict) -> list[str]:
    """Names of senior leaders: people pages and the org chart whose role matches, plus the fallback list."""
    names = list(cfg.get("fallback_names", []))
    kws = [k.lower() for k in cfg.get("role_keywords", [])]
    pdir = gl.path("core", "people")
    if pdir.is_dir():
        for p in sorted(pdir.glob("*.md")):
            if p.name.startswith("_"):
                continue
            fm = frontmatter.read(p)
            role = str(fm.get("role") or "").lower()
            if role and any(k in role for k in kws) and fm.get("name"):
                names.append(str(fm["name"]))
    return sorted(set(names))


def compile_patterns(spec: dict, seniors_re) -> list[dict]:
    out = []
    for p in spec["patterns"]:
        out.append({"id": p["id"], "regexes": [re.compile(r, re.I) for r in p["regex_patterns"]],
                    "anchors": [a.lower() for a in p.get("keyword_anchors", [])],
                    "needs_senior": bool(p.get("requires_senior_leader")), "seniors_re": seniors_re})
    return out


def mine_lines(p: Path, lines: list[str], patterns: list[dict], actor_re, require_actor: bool) -> list[dict]:
    actor_lines = {i for i, ln in enumerate(lines) if actor_re.search(ln)}
    hits, seen = [], set()
    for pat in patterns:
        for i, ln in enumerate(lines):
            if not any(r.search(ln) for r in pat["regexes"]):
                continue
            lo, hi = max(0, i - 5), min(len(lines), i + 6)
            window = "\n".join(lines[lo:hi])
            if require_actor and not any(abs(i - a) <= 5 for a in actor_lines):
                continue
            if pat["anchors"] and not any(a in window.lower() for a in pat["anchors"]):
                continue
            senior = pat["seniors_re"].search(window) if pat["seniors_re"] else None
            if pat["needs_senior"] and not senior:
                continue
            start, end = max(0, i - 1), min(len(lines), i + 3)
            snippet = "\n".join(lines[start:end]).strip()
            sha = hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:12]
            if (pat["id"], sha) in seen:
                continue
            seen.add((pat["id"], sha))
            am = actor_re.search(window)
            hits.append({"source_path": rel(p), "snippet": snippet, "line_range": [start + 1, end],
                         "content_sha256": sha, "pattern_id": pat["id"],
                         "actor_evidence": am.group(0) if am else "",
                         "senior_leader": senior.group(0) if senior else ""})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since")
    ap.add_argument("--days", type=int)
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--today", help="override today's date (tests)")
    ap.add_argument("--no-actor-filter", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    cfg = gl.source_config()
    spec = gl.load_cfg("signal-patterns.json")
    seniors_cfg = gl.load_cfg("senior-leaders.json")
    today = parse_date(args.today) if args.today else date.today()
    if args.since:
        since = parse_date(args.since)
    else:
        days = args.days or (cfg["lookback"]["backfill_days"] if args.backfill else cfg["lookback"]["default_days"])
        since = today - timedelta(days=days)

    actor_re = re.compile(r"\b(" + "|".join(re.escape(a) for a in gl.actor_aliases(spec.get("actor_aliases"))) + r")\b", re.I)
    names = senior_names(seniors_cfg)
    seniors_re = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.I) if names else None
    patterns = compile_patterns(spec, seniors_re)

    known = gl.existing_hashes(gl.read_text(gl.gp("evidence")))
    root_dir = root()
    scan = cfg["scan"]
    excl_globs = cfg["exclusions"].get("path_globs", [])
    files: dict[Path, bool] = {}  # path -> is_growth (no date filter, confidentiality allowed)
    for g in scan["globs"]:
        for p in sorted(root_dir.glob(g)):
            if p.is_file():
                files.setdefault(p, False)
    for g in scan.get("growth_globs", []):
        for p in sorted(root_dir.glob(g)):
            if p.is_file():
                files[p] = True

    candidates, scanned, skipped_known, seen_hash = [], 0, 0, set()
    for p, is_growth in files.items():
        r = rel(p)
        if any(fnmatch(r, g) for g in excl_globs):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter.parse(text)
        if not is_growth:
            if is_confidential_path(r, fm) or fm.get("redact_content") is True:
                continue
            d = file_date(p, fm)
            if d is None or d < since:
                continue
        scanned += 1
        _, body = frontmatter.split(text)
        for c in mine_lines(p, body.splitlines(), patterns, actor_re, not args.no_actor_filter):
            if c["content_sha256"] in known:
                skipped_known += 1
                continue
            if c["content_sha256"] in seen_hash:
                continue
            seen_hash.add(c["content_sha256"])
            c["mined_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            candidates.append(c)

    out = Path(args.out) if args.out else gl.run_dir() / f"candidates-{today.isoformat()}.json"
    if not out.is_absolute():
        out = root_dir / out
    gl.write_atomic(out, json.dumps(candidates, indent=2, ensure_ascii=False) + "\n")
    emit({"status": "success", "since": since.isoformat(), "files_scanned": scanned,
          "candidates": len(candidates), "already_known": skipped_known, "output": rel(out)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
