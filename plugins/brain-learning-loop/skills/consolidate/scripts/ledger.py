#!/usr/bin/env python3
"""The learning ledger: patterns and hypotheses with evidence counted in distinct sessions.

One writer for two files: <learning.ledger> (state, JSON) and <learning.hypotheses> (generated view, markdown).

  observe --payload F    merge observations (validate first, write second)
  list [--status S]      print the ledger as JSON
  set-status --id ID --status open|promoted|rejected   OWNER ACTION ONLY: run it when the owner said so in chat
  render                 rewrite the markdown view

Observation payload (written with the Write tool to <run_dir>/payloads/):
  {"observations": [
     {"kind": "pattern|hypothesis",           # required for a new item
      "id": "PAT-003",                        # optional: add evidence to an existing item
      "statement": "one sentence, no confidential detail",
      "session": "<session id or 8-char prefix>", "date": "YYYY-MM-DD",
      "polarity": "supports|refutes",         # default supports
      "note": "why this session counts (<=200 chars)"}]}

An item matches an existing one by id, else by its normalised statement. Evidence is deduplicated per
(session, polarity), so one long session can never fire a pattern three times. `crossed` in the output lists the
items that reached the promotion threshold on this call: candidates for the weekly review, never auto-promoted.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos.workspace import emit, path, rel  # noqa: E402

KINDS = {"pattern": "PAT", "hypothesis": "HYP"}
STATUSES = ("open", "promoted", "rejected")
POLARITIES = ("supports", "refutes")
DEFAULT_PROMOTE = 3
DEFAULT_DEMOTE = 2
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}")


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def load() -> dict:
    f = path("learning", "ledger")
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"version": 1, "items": {}}


def counts(item: dict) -> tuple[int, int]:
    sup = {e["session"] for e in item["evidence"] if e["polarity"] == "supports"}
    ref = {e["session"] for e in item["evidence"] if e["polarity"] == "refutes"}
    return len(sup), len(ref)


def save(ledger: dict) -> None:
    f = path("learning", "ledger")
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(f)
    render(ledger)


def render(ledger: dict) -> None:
    out = ["---", "type: learning-ledger-view", "generated: true", "---", "",
           "# Hypotheses and patterns", "",
           "_Generated from `ledger.json` by the nightly consolidation. Do not edit: the owner decides status "
           "(`ledger.py set-status`). Evidence counts distinct sessions._", ""]
    for kind, title in (("hypothesis", "Hypotheses"), ("pattern", "Patterns")):
        items = sorted((i for i in ledger["items"].values() if i["kind"] == kind),
                       key=lambda i: (i["status"] != "open", -counts(i)[0], i["id"]))
        out += [f"## {title}", ""]
        if not items:
            out += ["_None yet._", ""]
            continue
        out += ["| ID | Statement | Status | For | Against | First seen | Last seen |", "|---|---|---|---|---|---|---|"]
        for i in items:
            sup, ref = counts(i)
            stmt = i["statement"].replace("|", "/")
            out.append(f"| {i['id']} | {stmt} | {i['status']} | {sup} | {ref} | {i['first_seen']} | {i['last_seen']} |")
        out.append("")
    dest = path("learning", "hypotheses")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out), encoding="utf-8")


def validate(payload: object) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
        return ["payload must be an object with an 'observations' list"]
    if not payload["observations"]:
        return ["observations is empty: nothing to write"]
    errs = []
    for n, o in enumerate(payload["observations"]):
        tag = f"observations[{n}]"
        if not isinstance(o, dict):
            errs.append(f"{tag}: not an object")
            continue
        if not o.get("id") and o.get("kind") not in KINDS:
            errs.append(f"{tag}: new items need kind in {sorted(KINDS)}")
        if not o.get("id") and not str(o.get("statement", "")).strip():
            errs.append(f"{tag}: new items need a statement")
        if not re.fullmatch(r"[A-Za-z0-9-]{4,64}", str(o.get("session", ""))):
            errs.append(f"{tag}: session must be a session id or its 8-char prefix")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(o.get("date", ""))):
            errs.append(f"{tag}: date must be YYYY-MM-DD")
        if o.get("polarity", "supports") not in POLARITIES:
            errs.append(f"{tag}: polarity must be one of {POLARITIES}")
        for k in ("statement", "note"):
            if SECRET_RE.search(str(o.get(k, ""))):
                errs.append(f"{tag}: {k} looks like it contains a secret")
    return errs


def cmd_observe(args) -> int:
    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        emit({"status": "failed", "reason": f"unreadable payload: {exc}"})
        return 1
    errs = validate(payload)
    if errs:
        emit({"status": "failed", "reason": "validation failed, nothing written", "errors": errs})
        return 1
    ledger = load()
    items = ledger["items"]
    by_stmt = {(i["kind"], norm(i["statement"])): i["id"] for i in items.values()}
    before = {k: counts(v)[0] for k, v in items.items()}
    new = updated = dup = 0
    unknown: list[str] = []
    for o in payload["observations"]:
        pol = o.get("polarity", "supports")
        sid = str(o["session"])[:8]
        item = items.get(o["id"]) if o.get("id") else items.get(by_stmt.get((o.get("kind"), norm(o.get("statement", "")))))
        if o.get("id") and not item:
            unknown.append(o["id"])
            continue
        if not item:
            prefix = KINDS[o["kind"]]
            n = 1 + max([int(i["id"].split("-")[1]) for i in items.values() if i["id"].startswith(prefix)] or [0])
            item = {"id": f"{prefix}-{n:03d}", "kind": o["kind"], "statement": o["statement"].strip(), "status": "open",
                    "first_seen": o["date"], "last_seen": o["date"], "evidence": []}
            items[item["id"]] = item
            by_stmt[(item["kind"], norm(item["statement"]))] = item["id"]
            new += 1
        if any(e["session"] == sid and e["polarity"] == pol for e in item["evidence"]):
            dup += 1
            continue
        item["evidence"].append({"session": sid, "date": o["date"], "polarity": pol,
                                 "note": str(o.get("note", ""))[:200]})
        item["first_seen"] = min(item["first_seen"], o["date"])
        item["last_seen"] = max(item["last_seen"], o["date"])
        updated += 1
    if unknown:
        emit({"status": "failed", "reason": "unknown ids, nothing written", "unknown_ids": unknown})
        return 1
    save(ledger)
    crossed = sorted(k for k, v in items.items()
                     if v["status"] == "open" and before.get(k, 0) < args.promote_at <= counts(v)[0])
    emit({"status": "success", "counts": {"new_items": new, "evidence_added": updated, "duplicate_evidence": dup,
                                           "items_total": len(items)},
          "crossed": crossed, "outputs": [rel(path("learning", "ledger")), rel(path("learning", "hypotheses"))]})
    return 0


def cmd_list(args) -> int:
    ledger = load()
    rows = []
    for i in sorted(ledger["items"].values(), key=lambda x: x["id"]):
        if args.status and i["status"] != args.status:
            continue
        sup, ref = counts(i)
        rows.append({k: i[k] for k in ("id", "kind", "statement", "status", "first_seen", "last_seen")}
                    | {"supports": sup, "refutes": ref})
    emit({"status": "success", "items": rows, "counts": {"items": len(rows)}})
    return 0


def cmd_set_status(args) -> int:
    ledger = load()
    item = ledger["items"].get(args.id)
    if not item:
        emit({"status": "failed", "reason": f"unknown id {args.id}"})
        return 1
    item["status"] = args.status
    item.setdefault("history", []).append({"on": date.today().isoformat(), "status": args.status})
    save(ledger)
    emit({"status": "success", "id": args.id, "new_status": args.status})
    return 0


def cmd_render(args) -> int:
    render(load())
    emit({"status": "success", "outputs": [rel(path("learning", "hypotheses"))]})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("observe")
    o.add_argument("--payload", required=True)
    o.add_argument("--promote-at", type=int, default=DEFAULT_PROMOTE)
    o.set_defaults(fn=cmd_observe)
    ls = sub.add_parser("list")
    ls.add_argument("--status", choices=STATUSES)
    ls.set_defaults(fn=cmd_list)
    st = sub.add_parser("set-status")
    st.add_argument("--id", required=True)
    st.add_argument("--status", required=True, choices=STATUSES)
    st.set_defaults(fn=cmd_set_status)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
