"""Validate a review payload and write it to steal.db in one transaction; then archive the images.

Validate first, write second: any validation error leaves the DB and the inbox untouched.
Payload shape (JSON, written with the Write tool):
  {"run_id": "YYYY-MM-DD-HHMM", "batch_pov": "...",
   "dupes": ["<inbox path>", ...], "failed": [{"path": "...", "reason": "..."}],
   "items": [{"source_file": "<inbox path>", "sha256": "...", "seq": 0, "captured_at": "YYYY-MM-DD HH:MM",
              "platform": "instagram", "author_handle": "@x", "title": "...", "summary": "...",
              "claims": [...], "named_tools": [...], "topics": [...],
              "verdict": "steal|adapt|watch|skip", "targets": [...], "why": "...", "how": "...",
              "effort": "S|M|L", "novelty": "high|med|low", "evidence": "solid|thin|hype",
              "confidence": "high|med|low", "pov": "..."}]}
A screenshot with several posts = several items with the same sha256 and seq 0,1,2...
Text sources (pasted transcript/article): save the text as <steal home>/sources/YYYY-MM-DD-slug.md, use that file as
source_file (sha256 of the file), add "source_url". One item per idea, seq 0,1,2... The source file is kept, not archived.
A source_url already in the DB is skipped as a dupe.
Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/record.py --payload <file.json>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402

REQUIRED = ("source_file", "sha256", "title", "summary", "verdict", "why", "pov")


def validate(payload: dict, inbox: Path) -> list:
    errs = []
    if not isinstance(payload, dict) or not payload.get("run_id"):
        return ["payload must be an object with run_id"]
    items = payload.get("items")
    if not isinstance(items, list):
        return ["items must be a list"]
    if not items and not payload.get("dupes") and not payload.get("failed"):
        return ["payload is empty (no items, dupes or failed): refusing to write"]
    seen = set()
    for i, it in enumerate(items):
        tag = f"items[{i}]"
        for k in REQUIRED:
            if not str(it.get(k, "")).strip():
                errs.append(f"{tag}: missing {k}")
        if it.get("verdict") not in _steal.VERDICTS:
            errs.append(f"{tag}: verdict must be one of {_steal.VERDICTS}")
        for key, allowed in (("effort", _steal.EFFORTS), ("novelty", _steal.NOVELTY),
                             ("evidence", _steal.EVIDENCE), ("confidence", _steal.CONFIDENCE)):
            if it.get(key) not in (None, "") and it[key] not in allowed:
                errs.append(f"{tag}: {key} must be one of {allowed}")
        targets = it.get("targets") or []
        if isinstance(targets, str):
            targets = [targets]
        bad = [t for t in targets if t not in _steal.targets()]
        if bad:
            errs.append(f"{tag}: unknown targets {bad}")
        if it.get("verdict") in ("steal", "adapt"):
            if not str(it.get("how", "")).strip():
                errs.append(f"{tag}: steal/adapt needs a concrete 'how'")
            if not [t for t in targets if t != "none"]:
                errs.append(f"{tag}: steal/adapt needs at least one real target")
            if not it.get("effort"):
                errs.append(f"{tag}: steal/adapt needs effort")
        key = (it.get("sha256"), int(it.get("seq", 0) or 0))
        if key in seen:
            errs.append(f"{tag}: duplicate (sha256, seq) in payload")
        seen.add(key)
        src = Path(str(it.get("source_file", "")))
        if not src.is_file():
            errs.append(f"{tag}: source_file not found {src}")
        elif inbox not in src.resolve().parents and _steal.sources_dir().resolve() not in src.resolve().parents:
            errs.append(f"{tag}: source_file outside the inbox and the sources folder")
        elif _steal.sha256_file(src) != it.get("sha256"):
            errs.append(f"{tag}: sha256 does not match the file")
    return errs


def archive(path: Path, inbox: Path, day: str) -> str:
    dest_dir = inbox / "_processed" / day
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        dest = dest_dir / f"{path.stem}-{_steal.sha256_file(path)[:8]}{path.suffix}"
    shutil.move(str(path), str(dest))
    return str(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    args = ap.parse_args()

    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _steal.emit({"status": "failed", "reason": f"unreadable payload: {exc}"})
        raise SystemExit(1)

    inbox = _steal.inbox_dir().resolve()
    errs = validate(payload, inbox)
    if errs:
        _steal.emit({"status": "failed", "reason": "validation failed, nothing written", "errors": errs})
        raise SystemExit(1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    day = now[:10]
    con = _steal.connect()
    inserted, skipped_dupe, ids = 0, 0, []
    known_urls = {r[0] for r in con.execute("SELECT DISTINCT source_url FROM items WHERE source_url IS NOT NULL")}
    try:
        with con:
            con.execute("INSERT OR IGNORE INTO runs (run_id, started_at) VALUES (?, ?)", (payload["run_id"], now))
            for it in payload["items"]:
                seq = int(it.get("seq", 0) or 0)
                if con.execute("SELECT 1 FROM items WHERE sha256=? AND seq=?", (it["sha256"], seq)).fetchone() \
                        or (it.get("source_url") and it["source_url"] in known_urls):
                    skipped_dupe += 1
                    continue
                cur = con.execute(
                    "INSERT INTO items (sha256, seq, run_id, captured_at, reviewed_at, platform, author_handle,"
                    " title, summary, claims, named_tools, topics, source_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (it["sha256"], seq, payload["run_id"], it.get("captured_at"), now, it.get("platform"),
                     it.get("author_handle"), it["title"].strip(), it["summary"].strip(),
                     _steal.jlist(it.get("claims")), _steal.jlist(it.get("named_tools")), _steal.jlist(it.get("topics")),
                     it.get("source_url") or None))
                iid = cur.lastrowid
                con.execute(
                    "INSERT INTO verdicts (item_id, verdict, targets, why, how, effort, novelty, evidence, confidence, pov)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (iid, it["verdict"], _steal.jlist(it.get("targets")), it["why"].strip(), (it.get("how") or "").strip(),
                     it.get("effort") or None, it.get("novelty") or None, it.get("evidence") or None,
                     it.get("confidence") or None, it["pov"].strip()))
                status = "skipped" if it["verdict"] == "skip" else "proposed"
                con.execute("INSERT INTO decisions (item_id, status, updated_at) VALUES (?,?,?)", (iid, status, now))
                con.execute("INSERT INTO decision_log (item_id, status, at, note) VALUES (?,?,?,?)",
                            (iid, status, now, "auto: review verdict"))
                inserted += 1
                ids.append(iid)
            n_dupe = len(payload.get("dupes") or []) + skipped_dupe
            n_failed = len(payload.get("failed") or [])
            con.execute("UPDATE runs SET n_new = n_new + ?, n_dupe = n_dupe + ?, n_failed = n_failed + ?,"
                        " batch_pov = COALESCE(?, batch_pov) WHERE run_id = ?",
                        (inserted, n_dupe, n_failed, payload.get("batch_pov"), payload["run_id"]))
    except Exception as exc:  # transaction rolled back by the context manager
        _steal.emit({"status": "failed", "reason": f"db write failed, rolled back: {exc}"})
        raise SystemExit(1)

    archived = []
    for p in sorted({it["source_file"] for it in payload["items"]} | set(payload.get("dupes") or [])):
        src = Path(p)
        if src.is_file() and inbox in src.resolve().parents:
            archived.append(archive(src, inbox, day))
    _steal.emit({"status": "success", "run_id": payload["run_id"], "inserted": inserted, "item_ids": ids,
                 "dupes": n_dupe, "failed": payload.get("failed") or [], "archived": len(archived)})


if __name__ == "__main__":
    main()
