#!/usr/bin/env python3
"""Lint an objectives file before the owner signs it off.

    python3 lint_objectives.py --file growth/objectives/2027-H1.md

Checks: 3 to 5 objectives; each has a narrative of at least 15 words; at least 2 'Done looks like'
boxes, none of them vague ('ongoing', 'continue', 'keep'); each carries a framework-criteria tag
whose ids exist in the framework files (a missing tag is a warning: the evidence plan is optional
but recommended). Exit code 1 on errors.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "growth-signals" / "scripts"))
import growthlib as gl  # noqa: E402
from brainos.workspace import emit  # noqa: E402

VAGUE = re.compile(r"\b(ongoing|continue to|keep (on )?(doing|improving)|general(ly)?|as needed|good work)\b", re.I)


def lint(text: str, idx: dict) -> tuple[list[str], list[str]]:
    objs = gl.parse_objectives(text)
    errs, warns = [], []
    if not 3 <= len(objs) <= 5:
        errs.append(f"{len(objs)} objectives: aim for 3 to 5")
    for o in objs:
        t = f"Objective {o['n']}"
        if len(o["narrative"].split()) < 15:
            errs.append(f"{t}: narrative under 15 words; state the outcome and why it matters")
        if len(o["done"]) < 2:
            errs.append(f"{t}: needs at least 2 'Done looks like' boxes")
        for d in o["done"]:
            if VAGUE.search(d["text"]):
                errs.append(f"{t}: vague deliverable '{d['text'][:50]}'")
        if not o["criteria"]:
            warns.append(f"{t}: no <!-- framework-criteria: ... --> tag, so it will not feed the evidence matrix")
        for cid in o["criteria"]:
            if idx and cid not in idx:
                errs.append(f"{t}: unknown criterion id '{cid}'")
    return errs, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", required=True)
    args = ap.parse_args()
    p = Path(args.file)
    if not p.is_absolute():
        p = gl.root() / p
    if not p.is_file():
        emit({"status": "failed", "reason": f"{args.file} not found"})
        return 1
    errs, warns = lint(p.read_text(encoding="utf-8"), gl.criteria_index())
    emit({"status": "invalid" if errs else "success", "errors": errs, "warnings": warns})
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
