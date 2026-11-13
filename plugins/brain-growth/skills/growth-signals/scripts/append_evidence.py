#!/usr/bin/env python3
"""Phase 4 of growth-signals: write classified candidates to the growth files.

    python3 append_evidence.py --classified <path> [--today YYYY-MM-DD] [--dry-run]

Validates first (every criterion id must exist in the framework files, every item needs a hash,
a confidence and a title), then writes a dated section at the top of evidence-candidates.md and
opens or increments hypotheses. A single bad item aborts the run and writes nothing. Appends
one line to the growth run log. Never touches MEMORY.md or the tracker.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import growthlib as gl  # noqa: E402
from brainos.workspace import rel, emit  # noqa: E402

PREAMBLE = ("---\nsensitivity: confidential\n---\n\n# Evidence candidates\n\n> Mined from your work by growth-signals. "
            "Tick one triage box per candidate, then run promote.py.\n\n---\n\n")
CONF = ["High", "Medium", "Low", "Manual"]


def validate(items: list, idx: dict) -> list[str]:
    errs = []
    for n, it in enumerate(items):
        tag = f"item {n} ({it.get('content_sha256', '?')})"
        if not isinstance(it, dict):
            errs.append(f"item {n}: not an object")
            continue
        for k in ("content_sha256", "snippet", "title", "confidence", "classifications", "source_path"):
            if not it.get(k):
                errs.append(f"{tag}: missing '{k}'")
        if it.get("confidence") and it["confidence"] not in CONF:
            errs.append(f"{tag}: confidence must be one of {CONF}")
        for c in it.get("classifications") or []:
            if c.get("criterion_id") not in idx:
                errs.append(f"{tag}: unknown criterion id '{c.get('criterion_id')}'")
    return errs


def render_block(it: dict, idx: dict) -> str:
    cls = it["classifications"]
    first = idx[cls[0]["criterion_id"]]
    lines = [f"#### {it['title']}", f"- **Skill:** {first.skill}", "- **Criteria evidenced:**"]
    for c in cls:
        crit = idx[c["criterion_id"]]
        lines.append(f'  - `{crit.id}` — "{crit.text}"')
    lines += [f"- **Target level:** {cls[0].get('target_level') or first.level}",
              f"- **Framework version:** {first.version}"]
    vals = it.get("values_evidenced") or []
    if vals:
        lines.append("- **Values evidenced:**")
        lines += [f"  - `{v.get('id', '')}` — {v.get('name', '')}" for v in vals]
    lines += [f"- **Source:** `{it['source_path']}`",
              "- **Snippet:**", "  > " + it["snippet"].strip().replace("\n", "\n  > "),
              f"- **Confidence:** {it['confidence']}",
              "- **Triage:** `[ ]` Accept · `[ ]` Reject · `[ ]` Defer",
              f"- `hash: {it['content_sha256']}`"]
    return "\n".join(lines)


def render_section(today: str, items: list, dups: int, idx: dict) -> str:
    out = [f"## {today} — weekly run", f"_New candidates: {len(items)} · duplicates skipped: {dups}_", ""]
    for conf in CONF:
        group = [i for i in items if i["confidence"] == conf]
        if not group:
            continue
        out += [f"### {conf} confidence", ""]
        for it in group:
            out += [render_block(it, idx), ""]
    out += ["---", ""]
    return "\n".join(out)


def update_hypotheses(items: list, today: str, thresholds: dict, idx: dict) -> int:
    hyp_path = gl.gp("hypotheses")
    existing = gl.load_hypotheses(gl.read_text(hyp_path))
    hits = defaultdict(list)
    for it in items:
        for c in it["classifications"]:
            hits[c["criterion_id"]].append(it)
    open_after = thresholds.get("open_after_n_confirmations", 3)
    nxt = max((h["hyp_num"] for h in existing.values()), default=0) + 1
    changes = 0
    for cid, its in hits.items():
        if cid in existing:
            h = existing[cid]
            h["confirmations"] += len(its)
            h["sources"] += [f"- {today} — {i['title']}" for i in its]
            changes += 1
        elif len(its) >= open_after:
            crit = idx[cid]
            existing[cid] = {"hyp_num": nxt, "title": f"Operating at target level on {crit.skill}: {crit.text[:80]}",
                             "criterion_id": cid, "confirmations": len(its), "refutations": 0,
                             "sources": [f"- {today} — {i['title']}" for i in its], "status": "open"}
            nxt += 1
            changes += 1
    if changes:
        gl.write_atomic(hyp_path, render_hypotheses(existing, thresholds))
    return changes


def render_hypotheses(hyps: dict, thresholds: dict) -> str:
    promo = thresholds.get("promotion_candidate_after_n_confirmations", 5)

    def block(cid, h):
        lines = [f"### H-{h['hyp_num']:03d}: {h['title']}", f"- **Criterion targeted:** `{cid}`",
                 f"- **Confirmations:** {h['confirmations']} · **Refutations:** {h.get('refutations', 0)}"]
        if h["sources"]:
            lines.append("- **Sources:**")
            lines += [f"  {s}" for s in h["sources"]]
        lines.append(f"- **Status:** {'Paused' if h['status'] == 'paused' else 'Open'}")
        return "\n".join(lines)

    groups = {"Open": [], f"Promotion candidates (>= {promo} confirmations, awaiting the owner)": [], "Refuted or paused": []}
    keys = list(groups)
    for cid, h in sorted(hyps.items(), key=lambda kv: -kv[1]["confirmations"]):
        k = keys[2] if h["status"] == "paused" else keys[1] if h["confirmations"] >= promo else keys[0]
        groups[k].append(block(cid, h))
    out = ["---", "sensitivity: confidential", "---", "", "# Level hypotheses", "",
           "> Auto-managed by growth-signals. One hypothesis per criterion: are you operating at the target level on it?", ""]
    for title, blocks in groups.items():
        out += [f"## {title}", ""] + (["\n\n".join(blocks)] if blocks else ["*(empty)*"]) + [""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--classified", required=True)
    ap.add_argument("--today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p = Path(args.classified)
    if not p.is_absolute():
        p = gl.root() / p
    try:
        items = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(items, list)
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        emit({"status": "failed", "reason": f"cannot read classified payload: {exc}"})
        return 1
    idx = gl.criteria_index()
    if not idx:
        emit({"status": "failed", "reason": "no framework criteria found in growth/development/frameworks"})
        return 1
    errs = validate(items, idx)
    if errs:
        emit({"status": "failed", "reason": "invalid classified payload; nothing written", "errors": errs})
        return 1

    ev_path = gl.gp("evidence")
    known = gl.existing_hashes(gl.read_text(ev_path))
    new, dups, seen = [], 0, set()
    for it in items:
        if it["content_sha256"] in known or it["content_sha256"] in seen:
            dups += 1
            continue
        seen.add(it["content_sha256"])
        new.append(it)
    today = args.today or date.today().isoformat()
    summary = {"status": "success", "candidates_added": len(new), "duplicates_skipped": dups, "hypotheses_updated": 0}
    if args.dry_run:
        summary["dry_run"] = True
        emit(summary)
        return 0
    if new:
        existing = gl.read_text(ev_path) or PREAMBLE
        # insert the new section right after the preamble divider (first '---' line after the heading)
        marker = "\n---\n\n"
        pos = existing.find(marker, existing.find("# Evidence candidates"))
        cut = pos + len(marker) if pos >= 0 else len(existing)
        gl.write_atomic(ev_path, existing[:cut] + render_section(today, new, dups, idx) + "\n" + existing[cut:])
    summary["hypotheses_updated"] = update_hypotheses(new, today, gl.source_config()["hypotheses"], idx)
    log = gl.gp("run_log")
    entries = json.loads(log.read_text(encoding="utf-8")) if log.is_file() else []
    entries.append({"date": today, **{k: summary[k] for k in ("candidates_added", "duplicates_skipped", "hypotheses_updated")}})
    gl.write_atomic(log, json.dumps(entries, indent=2) + "\n")
    summary["evidence_file"] = rel(ev_path)
    emit(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
