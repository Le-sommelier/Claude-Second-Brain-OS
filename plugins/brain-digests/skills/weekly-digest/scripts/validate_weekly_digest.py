#!/usr/bin/env python3
"""Validate a weekly digest against the template.

    python3 ${CLAUDE_SKILL_DIR}/scripts/validate_weekly_digest.py --digest digests/weekly/2026-W45.md [--week 2026-W45] [--project-titles "A,B"]

Errors (exit 1): missing headings, unreplaced placeholders, a missing project row, a
CONFIDENTIAL marker or `sensitivity: confidential` in a shared digest, or the digest quoting a
confidential source's title. Warnings: vague phrases, no [[id]] citations, a Sources count lower
than the number of summaries that week. Project rows come from `--project-titles`, else from
`.claude/brain/digests.json` / `projects/`. Prints {"ok", "errors", "warnings"}.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from collect_kb_context import build_payload, list_projects, load_config, project_title, resolve_week  # noqa: E402
from brainos import confidential  # noqa: E402
from brainos.workspace import emit, root  # noqa: E402

REQUIRED_HEADINGS = ("# Weekly Digest", "## Overview", "## Project status", "## Sources")
PLACEHOLDERS = ("YYYY-Www", "YYYY-MM-DD", "{{", "}}")
VAGUE = ("ongoing", "alignment continues", "progress continues", "tbd", "to be confirmed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--digest", required=True)
    ap.add_argument("--week", help="check the Sources count against this week's summaries")
    ap.add_argument("--project-titles", help="comma-separated; default is the configured project list")
    args = ap.parse_args()

    p = Path(args.digest)
    p = p if p.is_absolute() else root() / p
    content = p.read_text(encoding="utf-8")
    low = content.lower()
    errors: list[str] = []
    warnings: list[str] = []

    for h in REQUIRED_HEADINGS:
        if h not in content:
            errors.append(f"Missing heading: {h}")
    for ph in PLACEHOLDERS:
        if ph in content:
            errors.append(f"Template placeholder left in digest: {ph}")

    if args.project_titles:
        names = [t.strip() for t in args.project_titles.split(",") if t.strip()]
    else:
        names = [project_title(d) for d in list_projects(load_config())]
    for n in names:
        if not re.search(r"^\|\s*" + re.escape(n.lower()) + r"\b", low, re.M):
            errors.append(f"Missing project row: {n}")

    if confidential.OPEN in content or re.search(r"^sensitivity:\s*confidential", content, re.M):
        errors.append("Digest carries confidential markers: shared digests hold signal-level content only")
    for v in VAGUE:
        if v in low:
            warnings.append(f"Contains vague phrase: '{v}'")
    if "[[" not in content:
        warnings.append("No [[id]] citations: every claim should point at a summary or entry")

    if args.week:
        payload = build_payload(load_config(), resolve_week(args.week, None))
        noted = re.search(r"summaries reviewed:\s*(\d+)", low)
        if noted and int(noted.group(1)) < payload["summaries_count"]:
            warnings.append(f"Sources says {noted.group(1)} summaries but {payload['summaries_count']} exist for the week")
        for s in payload["summaries"]:
            if s["confidential"] and s["title"] and str(s["title"]).lower() in low:
                errors.append(f"Names a confidential meeting by its title: {s['id']}")

    emit({"ok": not errors, "errors": errors, "warnings": warnings})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
