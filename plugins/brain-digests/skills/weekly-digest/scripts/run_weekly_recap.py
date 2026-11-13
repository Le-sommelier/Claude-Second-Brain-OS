#!/usr/bin/env python3
"""Prepare the weekly digest: collect context and print a manifest. Writes nothing.

    python3 ${CLAUDE_SKILL_DIR}/scripts/run_weekly_recap.py [--week 2026-W45 | --date 2026-11-04]

Exit 3 with `requires_user_confirmation: true` when the week has no summaries and no logged facts
(the ingest probably has not run). Otherwise exit 0 with the manifest the skill reads in step 2.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from collect_kb_context import build_payload, load_config, resolve_week  # noqa: E402
from brainos.workspace import emit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week")
    ap.add_argument("--date")
    args = ap.parse_args()
    week = resolve_week(args.week, args.date)
    p = build_payload(load_config(), week)

    if p["summaries_count"] == 0 and p["facts_count"] == 0:
        emit({"ok": False, "requires_user_confirmation": True,
              "stop_reason": f"Nothing found for {week.label}: no meeting summaries and no logged entries. "
                             "The ingest may not have run yet, or the tags filter excludes everything."})
        return 3

    conf = sum(1 for s in p["summaries"] if s["confidential"]) + sum(1 for s in p["slack_files"] if s["confidential"])
    p["ok"] = True
    p["confidential_sources"] = conf
    p["next_steps"] = [
        f"Read the {p['summaries_count']} summaries listed in `summaries` (skip bodies of confidential ones: signal level only)",
        "Read the Slack files in `slack_files` that are not confidential, if any",
        "Use `projects[*]` for RAG, open risks, entries and decisions logged this week; confirm anything surprising with `brain kb show <id>`",
        f"Write the digest to {p['output_path']} using references/output-template.md",
        f"Validate: python3 ${{CLAUDE_SKILL_DIR}}/scripts/validate_weekly_digest.py --digest {p['output_path']} --week {week.label}",
    ]
    emit(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
