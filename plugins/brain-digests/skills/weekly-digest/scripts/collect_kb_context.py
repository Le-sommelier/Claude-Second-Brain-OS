#!/usr/bin/env python3
"""Collect the week's meeting summaries, Slack files and logged facts for the weekly digest.

    python3 ${CLAUDE_SKILL_DIR}/scripts/collect_kb_context.py [--week 2026-W45 | --date 2026-11-04] [--format markdown|json]

Inputs are already-processed workspace files: `raw/meetings/**/*.summary.md`, `raw/slack/**`,
`projects/<slug>/*.md` facet logs and `decisions/`. Nothing is fetched and nothing is written.
Settings come from `.claude/brain/digests.json` (projects, tags_filter); defaults apply when absent.
Confidential sources are flagged (`confidential: true`) so the digest keeps them at signal level.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import kbparse  # noqa: E402
from brainos import confidential, frontmatter  # noqa: E402
from brainos.workspace import emit, path, rel  # noqa: E402

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


@dataclass(frozen=True)
class WeekWindow:
    iso_year: int
    iso_week: int
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.iso_year}-W{self.iso_week:02d}"


def week_from(iso_year: int, iso_week: int) -> WeekWindow:
    start = date.fromisocalendar(iso_year, iso_week, 1)
    return WeekWindow(iso_year, iso_week, start, start + timedelta(days=6))


def resolve_week(week_value: str | None, date_value: str | None) -> WeekWindow:
    if week_value and date_value:
        raise SystemExit("Use either --week or --date, not both.")
    if week_value:
        m = WEEK_RE.fullmatch(week_value)
        if not m:
            raise SystemExit("Invalid --week value. Expected YYYY-Www.")
        return week_from(int(m.group(1)), int(m.group(2)))
    d = datetime.strptime(date_value, "%Y-%m-%d").date() if date_value else date.today()
    iso = d.isocalendar()
    return week_from(iso.year, iso.week)


def previous_week(week: WeekWindow) -> WeekWindow:
    iso = (week.start - timedelta(days=1)).isocalendar()
    return week_from(iso.year, iso.week)


def load_config() -> dict:
    cfg_path = path("core", "module_config_dir") / "digests.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
    cfg.setdefault("projects", [])
    cfg.setdefault("tags_filter", [])
    return cfg


def project_title(pdir: Path) -> str:
    readme = pdir / "README.md"
    if readme.is_file():
        fm = frontmatter.read(readme)
        if fm.get("title"):
            return str(fm["title"])
        m = re.search(r"^# (.+)$", readme.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return pdir.name


def list_projects(cfg: dict) -> list[Path]:
    base = path("core", "projects")
    if not base.is_dir():
        return []
    wanted = cfg.get("projects") or []
    dirs = [base / s for s in wanted] if wanted else sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")))
    return [d for d in dirs if d.is_dir()]


def in_window(d: str | None, week: WeekWindow) -> bool:
    return bool(d) and week.start.isoformat() <= str(d)[:10] <= week.end.isoformat()


def find_summaries(week: WeekWindow, tags_filter: list[str]) -> list[dict]:
    base = path("core", "raw") / "meetings"
    out = []
    for p in sorted(base.rglob("*.summary.md")) if base.is_dir() else []:
        fm = frontmatter.read(p)
        if not (in_window(fm.get("date"), week) or fm.get("week") == week.label):
            continue
        tags = fm.get("tags") or []
        if tags_filter and not any(t in tags for t in tags_filter):
            continue
        conf = confidential.is_confidential_path(rel(p), fm)
        out.append({"id": fm.get("id") or p.name.removesuffix(".summary.md"), "path": rel(p), "date": str(fm.get("date")),
                    "title": fm.get("title"), "project": fm.get("project"), "meeting_type": fm.get("meeting_type"),
                    "tags": tags, "confidential": conf})
    return sorted(out, key=lambda e: (e["date"], e["id"]))


def find_slack(week: WeekWindow) -> list[dict]:
    d = path("core", "raw") / "slack" / str(week.iso_year) / week.label
    out = []
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if p.name.startswith("_"):
            continue
        fm = frontmatter.read(p)
        channel = str(fm.get("channel") or "")
        conf = bool(fm.get("redact_content")) or confidential.is_confidential_channel(channel) or confidential.is_confidential_path(rel(p), fm)
        out.append({"path": rel(p), "channel": channel or None, "confidential": conf})
    return out


def project_facts(pdir: Path, week: WeekWindow) -> dict:
    entries = kbparse.project_entries(pdir)
    status = sorted((e for e in entries if e["facet"] == "status" and e["meta"].get("rag")), key=lambda e: (e["date"], e["line"]))
    week_entries = [{"key": f"{pdir.name}/{e['id']}", "date": e["date"], "state": e["state"], "facet": e["facet"],
                     "rag": e["meta"].get("rag"), "owner": e["meta"].get("owner"), "source": e["meta"].get("source"),
                     "confidential": e["meta"].get("sensitivity") == "confidential",
                     "body": None if e["meta"].get("sensitivity") == "confidential" else e["body"][:240]}
                    for e in entries if in_window(e["date"], week)]
    open_risks = [e for e in kbparse.latest_by_id(entries) if e["facet"] == "risks" and e["state"] in ("open", "at-risk")]
    decisions = []
    ddir = pdir / "decisions"
    for f in sorted(ddir.glob("*.md")) if ddir.is_dir() else []:
        fm = frontmatter.read(f)
        if in_window(fm.get("date"), week):
            conf = fm.get("sensitivity") == "confidential"
            decisions.append({"id": fm.get("id", f.stem), "date": str(fm.get("date")), "status": fm.get("status"),
                              "by": fm.get("by"), "confidential": conf, "title": None if conf else fm.get("title")})
    return {"slug": pdir.name, "title": project_title(pdir), "current_rag": status[-1]["meta"]["rag"] if status else None,
            "open_risks": len(open_risks), "entries_this_week": week_entries, "decisions_this_week": decisions}


def build_payload(cfg: dict, week: WeekWindow) -> dict:
    digest_dir = path("core", "digests") / "weekly"
    prior = digest_dir / f"{previous_week(week).label}.md"
    out = digest_dir / f"{week.label}.md"
    projects = [project_facts(d, week) for d in list_projects(cfg)]
    summaries = find_summaries(week, cfg["tags_filter"])
    slack = find_slack(week)
    return {
        "week": {"label": week.label, "iso_year": week.iso_year, "iso_week": week.iso_week,
                 "start": week.start.isoformat(), "end": week.end.isoformat()},
        "output_path": rel(out), "output_exists": out.is_file(),
        "previous_digest_path": rel(prior) if prior.is_file() else None,
        "tags_filter": cfg["tags_filter"],
        "summaries": summaries, "summaries_count": len(summaries),
        "slack_files": slack,
        "projects": projects,
        "facts_count": sum(len(p["entries_this_week"]) + len(p["decisions_this_week"]) for p in projects),
    }


def print_markdown(p: dict) -> None:
    w = p["week"]
    print(f"# Weekly digest context for {w['label']}\n")
    print(f"- Window: {w['start']} to {w['end']}")
    print(f"- Output path: {p['output_path']}")
    print(f"- Previous digest: {p['previous_digest_path'] or 'none found'}")
    print(f"- Slack files: {len(p['slack_files'])}")
    print(f"- Summaries ({p['summaries_count']}):")
    for s in p["summaries"]:
        flag = " [confidential]" if s["confidential"] else ""
        print(f"  - [{s['date']}] {s['title']} ({s['project'] or 'no project'}){flag}")
    for pr in p["projects"]:
        print(f"- {pr['title']}: rag {pr['current_rag'] or '?'}, {len(pr['entries_this_week'])} entries, "
              f"{len(pr['decisions_this_week'])} decisions, {pr['open_risks']} open risks")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week")
    ap.add_argument("--date")
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = ap.parse_args()
    payload = build_payload(load_config(), resolve_week(args.week, args.date))
    emit(payload) if args.format == "json" else print_markdown(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
