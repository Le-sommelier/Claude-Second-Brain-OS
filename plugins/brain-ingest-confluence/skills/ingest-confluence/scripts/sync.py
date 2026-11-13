#!/usr/bin/env python3
"""Sync state for the Confluence watch list: plan the searches, diff a listing, write changed pages.

  python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py plan
      -> {"since", "queries": [{"name","cql"}], "max_pages"}   the CQL queries the brick must run
  python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py diff --listing system/run/payloads/confluence-listing.json
      listing = JSON array of {"id","title","version"?,"lastModified","space"?} (union of all query results)
      -> {"to_fetch": [{"id","title","reason": new|version_changed|modified}], "unchanged": N}
  python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py write --payload system/run/payloads/confluence-<id>.json
      payload = {"id","title","url","space","version","last_modified","labels":[...],"body"}; body is the
      page's own markdown, verbatim. Refuses empty, stub or placeholder bodies (exit 1, nothing written).
      A new version rewrites the same file and resets wiki_processed: false; the same version and body
      is reported `unchanged` and touches nothing.
  python3 ${CLAUDE_SKILL_DIR}/scripts/sync.py finish
      stamps last_sync after a fully successful run (a partial run leaves it, so the next run re-lists).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import confidential, frontmatter, payload, verbatim  # noqa: E402
from brainos.workspace import emit, iso_week, path, rel  # noqa: E402

MIN_BODY_CHARS = 60
_PLACEHOLDER = re.compile(r"^\s*[\[(<{].{0,120}[\])>}]\s*$|^\s*(tbd|todo|n/?a|pending|placeholder)\W*$", re.IGNORECASE | re.DOTALL)
DEFAULT_WATCH = {"lookback_days": 14, "max_pages_per_run": 50, "spaces": [], "page_ids": [], "labels": [], "cql": [],
                 "decision_detection": {"title_patterns": [], "labels": [], "tag": "decision-page"},
                 "confidential_labels": ["confidential", "restricted"]}


def watch() -> dict:
    cfg = dict(DEFAULT_WATCH)
    p = path("confluence", "watch")
    if p.is_file():
        cfg.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")})
    return cfg


def state_file() -> Path:
    return path("confluence", "state")


def load_state() -> dict:
    p = state_file()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"last_sync": None, "pages": {}}


def save_state(state: dict) -> None:
    p = state_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def slugify(title: str) -> str:
    t = unicodedata.normalize("NFKD", title.strip()).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80] or "untitled"


def check_body(text: str | None) -> None:
    """Reject placeholders and stubs: a fetch that did not happen must never overwrite a real file."""
    if not text or not text.strip():
        raise ValueError("body is empty: fetch the page with getConfluencePage before writing")
    if _PLACEHOLDER.match(text):
        raise ValueError(f"body looks like a placeholder ({text.strip()[:60]!r}): copy the real page content")
    if len(text.strip()) < MIN_BODY_CHARS:
        raise ValueError(f"body is only {len(text.strip())} chars: copy the full page body verbatim")


def is_decision(title: str, labels: list[str], cfg: dict) -> bool:
    dd = cfg.get("decision_detection", {})
    return (any(re.search(p, title, re.IGNORECASE) for p in dd.get("title_patterns", []))
            or bool({l.lower() for l in labels} & {l.lower() for l in dd.get("labels", [])}))


# ---------- plan ----------

def plan(today: date | None = None) -> dict:
    cfg, state = watch(), load_state()
    today = today or date.today()
    if state["last_sync"]:
        since = datetime.fromisoformat(state["last_sync"].replace("Z", "+00:00")).date() - timedelta(days=1)
    else:
        since = today - timedelta(days=int(cfg["lookback_days"]))
    s = since.isoformat()
    queries = []
    for sp in cfg["spaces"]:
        cql = f'space = "{sp["key"]}" AND type = page AND lastmodified >= "{s}"'
        if sp.get("include_labels"):
            cql += " AND label in (" + ", ".join(f'"{l}"' for l in sp["include_labels"]) + ")"
        queries.append({"name": f"space-{sp['key']}", "cql": cql})
    if cfg["labels"]:
        labels = ", ".join(f'"{l}"' for l in cfg["labels"])
        queries.append({"name": "labels", "cql": f'type = page AND label in ({labels}) AND lastmodified >= "{s}"'})
    if cfg["page_ids"]:
        ids = ", ".join(str(i) for i in cfg["page_ids"])
        queries.append({"name": "page-ids", "cql": f'id in ({ids}) AND lastmodified >= "{s}"'})
    for q in cfg["cql"]:
        queries.append({"name": q.get("name", "cql"), "cql": q["query"].replace("{since}", s)})
    return {"since": s, "queries": queries, "max_pages": int(cfg["max_pages_per_run"]), "first_run": not state["last_sync"]}


# ---------- diff ----------

def diff(listing: list[dict]) -> dict:
    state = load_state()
    cfg = watch()
    to_fetch, unchanged, seen = [], 0, set()
    for page in listing:
        pid = str(page["id"])
        if pid in seen:
            continue
        seen.add(pid)
        known = state["pages"].get(pid)
        if known is None:
            reason = "new"
        elif page.get("version") is not None and int(page["version"]) != int(known.get("version") or 0):
            reason = "version_changed"
        elif page.get("version") is None and str(page.get("lastModified", "")) != str(known.get("last_modified", "")):
            reason = "modified"
        else:
            unchanged += 1
            continue
        to_fetch.append({"id": pid, "title": page.get("title"), "reason": reason})
    capped = to_fetch[: int(cfg["max_pages_per_run"])]
    return {"ok": True, "listed": len(listing), "to_fetch": capped, "deferred": len(to_fetch) - len(capped), "unchanged": unchanged}


# ---------- write ----------

def write(page: dict) -> dict:
    missing = [k for k in ("id", "title", "url", "last_modified", "body") if not page.get(k)]
    if missing:
        raise ValueError(f"payload missing {missing}")
    check_body(page["body"])
    cfg, state = watch(), load_state()
    pid = str(page["id"])
    known = state["pages"].get(pid, {})
    version = int(page["version"]) if page.get("version") is not None else None
    body = page["body"].strip("\n")
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if known and known.get("sha") == sha and (version is None or version == known.get("version")):
        return {"ok": True, "changed": False, "status": "unchanged", "file": known["local_file"]}

    fname = known.get("local_file")
    if not fname:  # the ID is fixed at first sight: raw/confluence/YYYY/YYYY-Www/conf-<date>-<slug>.md
        d0 = str(page["last_modified"])[:10]
        year, week = iso_week(date.fromisoformat(d0))
        fname = f"{year}/{week}/conf-{d0}-{slugify(page['title'])}.md"
    labels = [str(l) for l in (page.get("labels") or [])]
    tags = [cfg["decision_detection"].get("tag", "decision-page")] if is_decision(page["title"], labels, cfg) else []
    secret = bool({l.lower() for l in labels} & {l.lower() for l in cfg.get("confidential_labels", [])})
    fields = {
        "id": Path(fname).stem,
        "source_type": "confluence",
        "confluence_page_id": pid,
        "confluence_version": version,
        "confluence_space": page.get("space"),
        "confluence_url": page["url"],
        "title": page["title"],
        "date": str(page["last_modified"])[:10],
        "labels": labels,
        "tags": tags,
        "last_modified_confluence": str(page["last_modified"]),
        "fetched_at": date.today().isoformat(),
        "sensitivity": "confidential" if secret else "internal",
        "wiki_processed": False,  # a new or changed version always re-enters the pending queue
    }
    content = confidential.wrap(body) if secret else body
    out = path("confluence", "root") / fname
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(frontmatter.render(fields) + f"\n# {page['title']}\n\n{content}\n", encoding="utf-8")
    state["pages"][pid] = {"title": page["title"], "version": version, "last_modified": str(page["last_modified"]),
                           "local_file": fname, "sha": sha}
    save_state(state)
    warnings = verbatim.check([(pid, page["body"])])
    return {"ok": True, "changed": True, "status": "rewritten" if known else "created", "file": rel(out),
            "version": version, "decision_page": bool(tags), "verbatim_warnings": warnings}


def finish() -> dict:
    state = load_state()
    state["last_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state)
    return {"ok": True, "last_sync": state["last_sync"], "pages_tracked": len(state["pages"])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    sub.add_parser("finish")
    d = sub.add_parser("diff")
    d.add_argument("--listing", required=True)
    w = sub.add_parser("write")
    w.add_argument("--payload", required=True)
    for p in (d, w):
        p.add_argument("--keep-payload", action="store_true")
    a = ap.parse_args()
    try:
        if a.cmd == "plan":
            result = plan()
        elif a.cmd == "finish":
            result = finish()
        elif a.cmd == "diff":
            result = diff(payload.load(a.listing, expect=list))
            payload.consume(a.listing, a.keep_payload)
        else:
            result = write(payload.load(a.payload))
            payload.consume(a.payload, a.keep_payload)
    except (FileNotFoundError, ValueError, KeyError, TypeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
