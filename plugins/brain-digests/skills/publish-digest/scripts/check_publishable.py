#!/usr/bin/env python3
"""Pre-flight for publishing a digest. Reads only; publishes nothing.

    python3 ${CLAUDE_SKILL_DIR}/scripts/check_publishable.py [--period 2026-W45] [--kind weekly|monthly] [--destination confluence|slack|email]

Finds digests/<kind>/<period>.md (default: the current ISO week, weekly), refuses template
placeholders and confidential markers, and loads the owner's destination from
`.claude/brain/digests.json` (`publish.destination`, overridable). Prints
{"ok", "errors", "file", "destination", "target", "title", "body_chars"}. Exit 1 when not ok.
The skill uses `target` and `title` to draft; it still needs an explicit yes before anything is sent.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos import confidential, frontmatter  # noqa: E402
from brainos.workspace import emit, path, rel  # noqa: E402

PLACEHOLDERS = ("YYYY-Www", "YYYY-MM-DD", "YYYY-MM", "{{", "}}")
REQUIRED = {"confluence": ("space", "parent_page_id"), "slack": ("channel",), "email": ("to",)}


def period_end(period: str) -> str:
    if "-W" in period:
        y, w = period.split("-W")
        return (date.fromisocalendar(int(y), int(w), 1) + timedelta(days=6)).isoformat()
    y, m = map(int, period.split("-"))
    return (date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=("weekly", "monthly"), default="weekly")
    ap.add_argument("--period")
    ap.add_argument("--destination", choices=("confluence", "slack", "email"))
    args = ap.parse_args()

    iso = date.today().isocalendar()
    period = args.period or (f"{iso.year}-W{iso.week:02d}" if args.kind == "weekly" else date.today().strftime("%Y-%m"))
    f = path("core", "digests") / args.kind / f"{period}.md"
    errors: list[str] = []
    result = {"file": rel(f), "period": period, "kind": args.kind}

    cfg_path = path("core", "module_config_dir") / "digests.json"
    pub = (json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}).get("publish", {})
    dest = args.destination or pub.get("destination", "none")
    result["destination"] = dest
    if dest not in REQUIRED:
        errors.append("No publish destination configured: set publish.destination in .claude/brain/digests.json (confluence, slack or email)")
    else:
        target = pub.get(dest, {})
        missing = [k for k in REQUIRED[dest] if not target.get(k)]
        if missing:
            errors.append(f"Destination {dest} is missing: {', '.join(missing)}")
        result["target"] = target
        tmpl = target.get("title_template") or target.get("subject_template") or f"Digest {{period}}"
        result["title"] = tmpl.format(period=period, week_end=period_end(period))

    if not f.is_file():
        errors.append(f"Digest not found: {rel(f)}. Run the digest skill first.")
    else:
        text = f.read_text(encoding="utf-8")
        result["body_chars"] = len(text)
        for ph in PLACEHOLDERS:
            if ph in text.replace(f"period: {period}", ""):
                errors.append(f"Template placeholder in digest: {ph}")
                break
        if confidential.OPEN in text or str(frontmatter.parse(text).get("sensitivity", "")).lower() == "confidential":
            errors.append("Digest carries confidential content: it cannot be published")

    emit({"ok": not errors, "errors": errors, **result})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
