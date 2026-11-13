#!/usr/bin/env python3
"""Validate a 1:1 draft payload against the style rules and queue it locally.

    python3 queue_draft.py --payload growth/one-on-ones/payloads/1on1-<id>.json

On success: writes <queue>/<person-id>/<id>.json, records the draft in the ledger, deletes the
payload. On failure: touches nothing (the payload stays) and prints {"status": "invalid", "errors": [...]}
so the draft can be rewritten. The queue lives under growth/, so it is confidential.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def words(s: str) -> int:
    return len(s.split())


def validate(d: dict, people: dict, banned: list[str]) -> list[str]:
    errs = [f"missing field '{k}'" for k in ("id", "person_id", "date", "title", "sections", "actions", "withheld", "source") if k not in d]
    if errs:
        return errs
    person = people.get(d["person_id"])
    if not person:
        return [f"unknown person_id '{d['person_id']}' (not on the roster)"]
    if not c.pl.DATE_RE.match(str(d["date"])):
        errs.append("date must be YYYY-MM-DD")
    if not isinstance(d["withheld"], int) or d["withheld"] < 0:
        errs.append("withheld must be a non-negative integer")
    sec = d["sections"]
    if set(sec) - set(c.SECTION_KEYS):
        errs.append(f"unknown sections {sorted(set(sec) - set(c.SECTION_KEYS))}")
    if sec.get("career") and not person.get("showCareer"):
        errs.append("career section is not used for this person; fold it elsewhere or drop it")
    total, texts = words(d["title"]), [d["title"]]
    for k in c.SECTION_KEYS:
        items = sec.get(k, [])
        if not isinstance(items, list) or not all(isinstance(i, str) and i.strip() for i in items):
            errs.append(f"section '{k}' must be a list of non-empty strings")
            continue
        if len(items) > c.MAX_BULLETS:
            errs.append(f"section '{k}' has {len(items)} bullets (max {c.MAX_BULLETS})")
        for i in items:
            if words(i) > c.MAX_BULLET_WORDS:
                errs.append(f"bullet too long in '{k}' ({words(i)} words, max {c.MAX_BULLET_WORDS}): {i[:60]}...")
            total += words(i)
            texts.append(i)
    for a in d["actions"]:
        if not isinstance(a, dict) or not a.get("who") or not a.get("what"):
            errs.append("each action needs 'who' and 'what'")
            continue
        if a.get("due") and not c.pl.DATE_RE.match(a["due"]):
            errs.append(f"action due must be YYYY-MM-DD or empty: {a['what'][:40]}")
        total += words(a["what"])
        texts.append(a["what"])
    if len(d["actions"]) > c.MAX_ACTIONS:
        errs.append(f"{len(d['actions'])} actions (max {c.MAX_ACTIONS}); keep the real commitments")
    if total > c.MAX_TOTAL_WORDS:
        errs.append(f"{total} words in total (max {c.MAX_TOTAL_WORDS}); cut to what matters")
    blob = "\n".join(texts)
    if c.FORBIDDEN_TEXT.search(blob):
        errs.append("remove system metadata (links, frontmatter, flags) from the text")
    for w in banned:
        if re.search(r"\b" + re.escape(w) + r"\b", blob.lower()):
            errs.append(f"banned word or phrase: '{w}'")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()
    payload = Path(args.payload)
    if not payload.is_absolute():
        payload = c.root() / payload
    try:
        d = json.loads(payload.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        c.emit({"status": "invalid", "errors": [f"cannot read payload: {exc}"]})
        return 1
    errs = validate(d, {p["person_id"]: p for p in c.roster()}, c.banned_words())
    if errs:
        c.emit({"status": "invalid", "id": d.get("id"), "errors": errs})
        return 1
    for k in c.SECTION_KEYS:
        d["sections"].setdefault(k, [])
    target = c.queue_dir() / d["person_id"] / f"{d['id']}.json"
    ledger = c.load_ledger()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ledger["drafted"][d["id"]] = d["date"]
    c.save_ledger(ledger)
    payload.unlink()
    c.emit({"status": "queued", "id": d["id"], "person_id": d["person_id"], "queued": c.rel(target)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
