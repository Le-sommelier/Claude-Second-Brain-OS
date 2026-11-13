#!/usr/bin/env python3
"""Update a people page from evidence, without touching anything the owner or brain-wiki wrote.

    python3 person_page.py --id casey-nguyen --payload growth/one-on-ones/payloads/person-casey.json [--dry-run]

Create the page first with `brain new person <id>`; this script only updates.
Payload: {"fields": {"influence": 3, "health": "strong", "last_contact": "2026-11-05"},
          "notes": [{"date": "2026-11-05", "text": "Prefers written pre-reads."}],
          "evidence": [{"date": "2026-11-04", "text": "Presented the roadmap unaided", "source": "mtg-2026-11-04-roadmap-review"}]}
Writes only: the stakeholder frontmatter fields, and the sections 'Stakeholder notes' (inside a
confidential wrapper), '1:1 log' and 'Evidence log'. Aborts, writing nothing, if a human fence
would change or an input is invalid. Evidence lines are deduplicated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import peoplelib as pl  # noqa: E402


def validate(d: dict) -> list[str]:
    errs = []
    for k, v in (d.get("fields") or {}).items():
        allowed = pl.STAKEHOLDER_FIELDS.get(k, "missing")
        if allowed == "missing":
            errs.append(f"field '{k}' is not owned by stakeholders (allowed: {sorted(pl.STAKEHOLDER_FIELDS)})")
        elif k == "last_contact":
            if not pl.DATE_RE.match(str(v)):
                errs.append("last_contact must be YYYY-MM-DD")
        elif allowed is not None and v not in allowed:
            errs.append(f"{k}={v!r} not allowed")
    for key in ("notes", "evidence"):
        for i, e in enumerate(d.get(key) or []):
            if not isinstance(e, dict) or not e.get("text") or not pl.DATE_RE.match(str(e.get("date", ""))):
                errs.append(f"{key}[{i}]: needs 'date' (YYYY-MM-DD) and 'text'")
            elif "\n" in e["text"]:
                errs.append(f"{key}[{i}]: text must be one line")
    return errs


def apply(text: str, d: dict) -> tuple[str, dict]:
    fm_text, body = pl.frontmatter.split(text)
    if fm_text is None:
        raise ValueError("page has no frontmatter")
    if d.get("fields"):
        text = pl.frontmatter.set_fields(text, d["fields"])
        _, body = pl.frontmatter.split(text)
    secs = pl.split_sections(body)
    added = {"notes": 0, "evidence": 0}
    if d.get("notes"):
        i = pl.ensure_section(secs, "Stakeholder notes")
        new = [f"- {n['date']} · {n['text']}" for n in d["notes"]]
        new = [ln for ln in new if ln not in secs[i][1]]
        if new:
            secs[i] = (secs[i][0], pl.insert_in_confidential(secs[i][1], new))
            added["notes"] = len(new)
    if d.get("evidence"):
        i = pl.ensure_section(secs, "Evidence log")
        lines = list(secs[i][1])
        for e in d["evidence"]:
            ln = f"- {e['date']} · {e['text']}" + (f" · source: [[{e['source']}]]" if e.get("source") else "")
            if ln not in lines:
                while lines and not lines[-1].strip():
                    lines.pop()
                lines += [ln, ""]
                added["evidence"] += 1
        secs[i] = (secs[i][0], lines)
    head = text[: len(text) - len(body)]
    return head + pl.join_sections(secs), added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", required=True)
    ap.add_argument("--payload", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    page = pl.page_path(args.id)
    if not page.is_file():
        pl.emit({"status": "failed", "reason": f"{pl.rel(page)} missing; run `brain new person {args.id}` first"})
        return 1
    pp = Path(args.payload)
    if not pp.is_absolute():
        pp = pl.root() / pp
    try:
        d = json.loads(pp.read_text(encoding="utf-8"))
        assert isinstance(d, dict)
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        pl.emit({"status": "invalid", "errors": [f"cannot read payload: {exc}"]})
        return 1
    errs = validate(d)
    if errs:
        pl.emit({"status": "invalid", "errors": errs})
        return 1
    old = page.read_text(encoding="utf-8")
    try:
        new, added = apply(old, d)
    except ValueError as exc:
        pl.emit({"status": "failed", "reason": str(exc)})
        return 1
    if pl.human_fences(old) != pl.human_fences(new):
        pl.emit({"status": "failed", "reason": "a human-fenced section would change; nothing written"})
        return 1
    if not args.dry_run and new != old:
        pl.write_atomic(page, new)
        pp.unlink(missing_ok=True)
    pl.emit({"status": "success", "page": pl.rel(page), "fields_set": sorted(d.get("fields") or {}),
             "notes_added": added["notes"], "evidence_added": added["evidence"], "changed": new != old})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
