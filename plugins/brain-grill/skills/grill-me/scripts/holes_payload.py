#!/usr/bin/env python3
"""Validate (and preview) the "holes found" list of a grilling session before anything is saved.

    python3 holes_payload.py --payload system/run/payloads/grill-<project>-<date>.json [--normalize OUT.json]

Payload (written with the Write tool; the owner has seen the list in chat first):
  {"project": "<slug>", "mode": "prd|roadmap|decision|exec-update", "session_date": "YYYY-MM-DD",
   "holes": [{"facet": "risks|hypotheses", "severity": "blocker|major|minor",
              "kind": "assumption|risk|gap|contradiction|unowned|evidence",
              "title": "<=100 chars", "body": "what is missing or wrong and what would close it",
              "refs": ["checkout-revamp/RSK-001"], "owner": "person-id (optional)", "due": "YYYY-MM-DD (optional)"}]}

Checks that every hole fits the knowledge-base entry grammar once appended as AI-written entries: state `proposed`,
`by: ai`, `trust: low`, a `source` of `grill:<mode>:<date>`. Prints the rendered entries so the owner can read exactly
what would be added. With --normalize it also writes the normalised list that `brain kb append` takes. It never
writes into a project itself: the append happens only after the owner's explicit yes.
The `objectives` mode is refused here by design: objectives are personal and confidential, so their holes never
go into a project log.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import frontmatter  # noqa: E402
from brainos.confidential import is_confidential_path  # noqa: E402
from brainos.workspace import emit, path, rel, root  # noqa: E402

MODES = ("prd", "roadmap", "decision", "exec-update")
FACETS = {"risks": "RSK", "hypotheses": "HYP"}
SEVERITIES = ("blocker", "major", "minor")
KINDS = ("assumption", "risk", "gap", "contradiction", "unowned", "evidence")
MAX_HOLES = 12
REF_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[A-Z]+-\d+$|^DEC-[a-z0-9-]+-\d+$")
PERSON_RE = re.compile(r"^[a-z][a-z-]*[a-z]$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def check_date(v: str) -> bool:
    try:
        datetime.strptime(v, "%Y-%m-%d")
        return bool(DATE_RE.match(v))
    except ValueError:
        return False


def validate(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    errs: list[str] = []
    if payload.get("mode") == "objectives":
        return ["objectives mode is personal and confidential: holes are never appended to a project log"]
    if payload.get("mode") not in MODES:
        errs.append(f"mode must be one of {MODES}")
    slug = str(payload.get("project", ""))
    if not SLUG_RE.match(slug):
        errs.append("project must be a slug like checkout-revamp")
    else:
        proj = path("core", "projects") / slug
        if not proj.is_dir():
            errs.append(f"no project folder {rel(proj)}")
        else:
            readme = proj / "README.md"
            fm = frontmatter.read(readme) if readme.is_file() else {}
            if is_confidential_path(rel(proj) + "/README.md", fm):
                errs.append("project is confidential: do not append grill output to it")
    if not check_date(str(payload.get("session_date", ""))):
        errs.append("session_date must be YYYY-MM-DD")
    holes = payload.get("holes")
    if not isinstance(holes, list) or not holes:
        return errs + ["holes must be a non-empty list: an empty list means nothing to save"]
    if len(holes) > MAX_HOLES:
        errs.append(f"at most {MAX_HOLES} holes per session: keep the ones that would change a decision")
    for n, h in enumerate(holes):
        tag = f"holes[{n}]"
        if not isinstance(h, dict):
            errs.append(f"{tag}: not an object")
            continue
        if h.get("facet") not in FACETS:
            errs.append(f"{tag}: facet must be one of {sorted(FACETS)}")
        if h.get("severity") not in SEVERITIES:
            errs.append(f"{tag}: severity must be one of {SEVERITIES}")
        if h.get("kind") not in KINDS:
            errs.append(f"{tag}: kind must be one of {KINDS}")
        title = str(h.get("title", "")).strip()
        if not title or len(title) > 100 or "\n" in title:
            errs.append(f"{tag}: title is required, one line, at most 100 characters")
        body = str(h.get("body", "")).strip()
        if not body or len(body) > 1200:
            errs.append(f"{tag}: body is required and at most 1200 characters")
        if re.search(r"<!--|^## ", body, re.M):
            errs.append(f"{tag}: body must not contain comment markers or '## ' lines (they would break the entry parser)")
        for r in h.get("refs") or []:
            if not REF_RE.match(str(r)):
                errs.append(f"{tag}: ref {r!r} is not a <project>/<ID> or DEC-<project>-NNN id")
        if h.get("owner") and not PERSON_RE.match(str(h["owner"])):
            errs.append(f"{tag}: owner must be a person-id like riley-chen")
        if h.get("due") and not check_date(str(h["due"])):
            errs.append(f"{tag}: due must be YYYY-MM-DD")
    return errs


def normalise(payload: dict) -> dict:
    src = f"grill:{payload['mode']}:{payload['session_date']}"
    entries = []
    for h in payload["holes"]:
        entries.append({"facet": h["facet"], "id_prefix": FACETS[h["facet"]], "date": payload["session_date"],
                        "state": "proposed", "by": "ai", "trust": "low", "source": src,
                        "owner": h.get("owner") or None, "due": h.get("due") or None, "refs": h.get("refs") or [],
                        "body": f"[{h['severity']}/{h['kind']}] {h['title'].strip()}. {h['body'].strip()}"})
    return {"project": payload["project"], "entries": entries}


def preview(norm: dict) -> str:
    out = []
    for e in norm["entries"]:
        meta = [f"by: {e['by']}", f"trust: {e['trust']}", f"source: {e['source']}"]
        for k in ("owner", "due"):
            if e[k]:
                meta.append(f"{k}: {e[k]}")
        if e["refs"]:
            meta.append("refs: " + ", ".join(e["refs"]))
        out.append(f"## {e['date']} · {e['id_prefix']}-NNN · {e['state']}\n" + " · ".join(meta) + f"\n{e['body']}\n")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--payload", required=True)
    ap.add_argument("--normalize", help="write the normalised entries for `brain kb append` to this path")
    args = ap.parse_args()
    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        emit({"brick": "grill-holes", "status": "failed", "reason": f"unreadable payload: {exc}"})
        return 1
    errs = validate(payload)
    if errs:
        emit({"brick": "grill-holes", "status": "failed", "reason": "validation failed, nothing written", "errors": errs})
        return 1
    norm = normalise(payload)
    outputs = []
    if args.normalize:
        dest = Path(args.normalize)
        dest = dest if dest.is_absolute() else root() / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(norm, indent=2, ensure_ascii=False), encoding="utf-8")
        outputs.append(rel(dest))
    emit({"brick": "grill-holes", "status": "success", "counts": {"holes": len(norm["entries"])},
          "outputs": outputs, "preview": preview(norm), "warnings": [], "observations": []})
    return 0


if __name__ == "__main__":
    sys.exit(main())
