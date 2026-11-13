#!/usr/bin/env python3
"""Pre-check a facet payload before `brain kb append` (which re-validates and assigns IDs).

    python3 ${CLAUDE_SKILL_DIR}/scripts/validate_facets.py --project checkout-revamp --file system/run/payloads/facets-checkout-revamp.json

Payload: JSON array of facet entries and decisions (shape in SKILL.md). Checks facet/prefix pairs,
states, dates, mandatory sources, that updated IDs exist in the project log, and that a
confidential source never produces a decision or a quoted body. Prints {"ok", "errors", "warnings", "count"}.
Exit 1 on any error. Writes nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import kbparse  # noqa: E402
from brainos import payload  # noqa: E402
from brainos.workspace import emit, path  # noqa: E402

FACETS = {"status": ("STA",), "risks": ("RSK", "DEP"), "milestones": ("MS",), "resources": ("RES",), "hypotheses": ("HYP",)}
STATES = {"open", "closed", "mitigated", "proposed", "accepted", "superseded", "at-risk", "on-track",
          "off-track", "done", "slipped"}
RAGS = {"green", "amber", "red"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--confidential-sources", default="", help="comma-separated source ids that are confidential")
    args = ap.parse_args()

    items = payload.load(args.file, list)
    proj = path("core", "projects") / args.project
    errors: list[str] = []
    warnings: list[str] = []
    if not proj.is_dir():
        errors.append(f"no such project: {args.project}")
    known = {e["id"] for e in kbparse.project_entries(proj)} if proj.is_dir() else set()
    secret = {s.strip() for s in args.confidential_sources.split(",") if s.strip()}

    for i, it in enumerate(items):
        w = f"[{i}]"
        if not isinstance(it, dict):
            errors.append(f"{w} not an object")
            continue
        src = it.get("source") or []
        src = [src] if isinstance(src, str) else src
        if not src:
            errors.append(f"{w} source is mandatory")
        if not DATE.match(str(it.get("date", ""))):
            errors.append(f"{w} bad date {it.get('date')!r}")
        body = str(it.get("body", "")).strip()
        if not body:
            errors.append(f"{w} empty body")
        from_secret = bool(secret & set(src))
        if from_secret and re.search(r"[\"“”]", body):
            errors.append(f"{w} quotes text from a confidential source")
        if it.get("type") == "decision":
            if not it.get("title"):
                errors.append(f"{w} decision needs a title")
            if from_secret:
                errors.append(f"{w} decision from a confidential source needs a non-confidential corroboration")
            continue
        facet, prefix = it.get("facet"), it.get("prefix")
        if facet not in FACETS or prefix not in FACETS[facet]:
            errors.append(f"{w} facet/prefix mismatch ({facet}/{prefix})")
        if it.get("state") not in STATES:
            errors.append(f"{w} bad state {it.get('state')!r}")
        if facet == "status" and it.get("rag") not in RAGS:
            errors.append(f"{w} status entries need rag green|amber|red")
        if it.get("id") and it["id"] not in known:
            errors.append(f"{w} unknown ID {it['id']}")
        if it.get("due") and not DATE.match(str(it["due"])):
            errors.append(f"{w} bad due date")
        if len(body) > 600:
            warnings.append(f"{w} long body ({len(body)} chars): entries should be one or two sentences")

    emit({"ok": not errors, "errors": errors, "warnings": warnings, "count": len(items)})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
