#!/usr/bin/env python3
"""Weekly system review: a 2-minute, observational report on how the workspace is learning and where it is drifting.

    python3 run_system_review.py [--week YYYY-Www] [--today YYYY-MM-DD] [--config PATH] [--dry-run] [--no-doctor]

Reads: the learning ledger, MEMORY.md, project facet logs (entry grammar), proposals, and the curated pages
(projects, topics, people). Writes exactly one file: <learning.reviews>/_system-review-YYYY-Www.md.
Never edits RULES.md, MEMORY.md, the ledger, a facet log or a proposal. Only the owner promotes a rule.
Files that are confidential (frontmatter or confidential globs) are never read.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos import frontmatter  # noqa: E402
from brainos.confidential import is_confidential_path, path_globs  # noqa: E402
from brainos.workspace import emit, iso_week, path, rel, root  # noqa: E402

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "references" / "review-config.json"
HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) · (\S+) · (\S+)\s*$")
OPEN_STATES = {"open", "at-risk", "proposed"}
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MEMORY_HEAD_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}) +[-—·] +(.+?)\s*$", re.MULTILINE)


def load_config(p: Path) -> dict:
    cfg = json.loads(p.read_text(encoding="utf-8"))
    for section, keys in (("scan", ["project_facets", "vault_dirs", "ignore_dirs", "output_filename_template"]),
                          ("thresholds", ["promotion_min_sessions", "demotion_min_refutations", "stale_ledger_days",
                                          "stale_entry_days", "inactive_project_days", "memory_window_days",
                                          "proposal_resurface_days", "oversized_page_lines"])):
        missing = [k for k in keys if k not in cfg.get(section, {})]
        if missing:
            raise ValueError(f"config {section} is missing {missing}")
    return cfg


def ignored_dirs(cfg: dict) -> set[str]:
    """Config ignore list plus the top folder of every confidential glob (for example growth/**)."""
    out = {d.lower() for d in cfg["scan"]["ignore_dirs"]}
    for g in path_globs():
        head = g.split("/", 1)[0]
        if head and not any(c in head for c in "*?["):
            out.add(head.lower())
    return out


def readable(p: Path, ignore: set[str]) -> bool:
    """False for ignored folders and confidential files: the review must not read them."""
    r = p.relative_to(root())
    if any(part.lower() in ignore for part in r.parts):
        return False
    if is_confidential_path(str(r)):
        return False
    try:
        return not is_confidential_path(str(r), frontmatter.read(p))
    except (OSError, UnicodeDecodeError):
        return False


def parse_entries(p: Path) -> list[dict]:
    """Entries of one facet log, per system/schema/entry-grammar.md. Fenced human blocks are skipped."""
    out, cur, in_human = [], None, False
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if "<!-- human -->" in line:
            in_human = True
            continue
        if "<!-- /human -->" in line:
            in_human = False
            continue
        if in_human:
            continue
        m = HEADER_RE.match(line)
        if m:
            cur = {"date": m.group(1), "id": m.group(2), "state": m.group(3), "line": n, "by": None, "body": ""}
            out.append(cur)
        elif cur is not None:
            if cur["by"] is None and line.startswith("by:"):
                cur["by"] = line[3:].split("·")[0].strip()
                for part in line.split("·")[1:]:
                    k, _, v = part.partition(":")
                    cur[k.strip()] = v.strip()
            else:
                cur["body"] += line + "\n"
    return out


def current_entries(entries: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for e in sorted(entries, key=lambda x: (x["date"], x["line"])):
        latest[e["id"]] = e
    return list(latest.values())


def project_scan(cfg: dict, today: date, ignore: set[str]) -> dict:
    base = path("core", "projects")
    th = cfg["thresholds"]
    res = {"stale_open": [], "unconfirmed_ai": [], "inactive": [], "skeleton": [], "projects": 0}
    if not base.is_dir():
        return res
    for proj in sorted(d for d in base.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        if proj.name.lower() in ignore:
            continue
        res["projects"] += 1
        missing = [f for f in cfg["scan"].get("project_files_expected", []) if not (proj / f).exists()]
        if missing:
            res["skeleton"].append(f"{proj.name}/ - missing {', '.join(missing)}")
        latest_date = None
        for facet in cfg["scan"]["project_facets"]:
            f = proj / f"{facet}.md"
            if not f.is_file() or not readable(f, ignore):
                continue
            for e in current_entries(parse_entries(f)):
                d = datetime.strptime(e["date"], "%Y-%m-%d").date()
                latest_date = max(latest_date or d, d)
                age = (today - d).days
                tag = f"{proj.name}/{e['id']}"
                if e["state"] in OPEN_STATES and age > th["stale_entry_days"]:
                    res["stale_open"].append((tag, e["state"], age, facet))
                if e["by"] == "ai" and e["state"] in OPEN_STATES and age > th["proposal_resurface_days"]:
                    res["unconfirmed_ai"].append((tag, e["state"], age, facet))
        if latest_date and (today - latest_date).days > th["inactive_project_days"]:
            res["inactive"].append((proj.name, (today - latest_date).days))
    return res


def ledger_scan(cfg: dict, today: date) -> dict:
    th = cfg["thresholds"]
    f = path("learning", "ledger")
    res = {"promotion": [], "demotion": [], "stale": [], "open": 0, "total": 0}
    if not f.is_file():
        return res
    items = json.loads(f.read_text(encoding="utf-8")).get("items", {})
    res["total"] = len(items)
    for i in sorted(items.values(), key=lambda x: x["id"]):
        if i["status"] != "open":
            continue
        res["open"] += 1
        sup = len({e["session"] for e in i["evidence"] if e["polarity"] == "supports"})
        ref = len({e["session"] for e in i["evidence"] if e["polarity"] == "refutes"})
        row = {**i, "supports": sup, "refutes": ref}
        if sup >= th["promotion_min_sessions"] and ref < sup:
            res["promotion"].append(row)
        if ref >= th["demotion_min_refutations"] and ref > sup:
            res["demotion"].append(row)
        age = (today - datetime.strptime(i["last_seen"], "%Y-%m-%d").date()).days
        if age > th["stale_ledger_days"]:
            res["stale"].append({**row, "age_days": age})
    return res


def memory_recent(cfg: dict, today: date) -> list[str]:
    f = path("core", "memory")
    if not f.is_file():
        return []
    cutoff = today - timedelta(days=cfg["thresholds"]["memory_window_days"])
    return [f"{m.group(1)} - {m.group(2)}" for m in MEMORY_HEAD_RE.finditer(f.read_text(encoding="utf-8"))
            if datetime.strptime(m.group(1), "%Y-%m-%d").date() >= cutoff]


def proposals_scan(cfg: dict, today: date) -> dict:
    d = path("core", "proposals")
    res = {"tally": defaultdict(int), "open_old": [], "total": 0}
    if not d.is_dir():
        return res
    for f in sorted(d.glob("PRP-*.md")):
        fm = frontmatter.read(f)
        state = str(fm.get("state") or "open")
        res["tally"][state] += 1
        res["total"] += 1
        if state == "open" and fm.get("date"):
            age = (today - datetime.strptime(str(fm["date"])[:10], "%Y-%m-%d").date()).days
            if age > cfg["thresholds"]["proposal_resurface_days"]:
                res["open_old"].append((fm.get("id") or f.stem, fm.get("title") or "", age))
    return res


def vault_health(cfg: dict, ignore: set[str]) -> dict:
    """Broken wikilinks, orphan pages and oversized pages across the curated folders."""
    out: dict[str, list] = {"broken": [], "orphans": [], "oversized": []}
    r = root()
    names: set[str] = set()
    for sub in (*cfg["scan"]["vault_dirs"], "digests", "raw", "inbox"):
        base = r / sub
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file():
                    names.add(p.name)
                    names.add(p.stem)
    texts: dict[Path, str] = {}
    for sub in cfg["scan"]["vault_dirs"]:
        base = r / sub
        for p in sorted(base.rglob("*.md")) if base.is_dir() else []:
            if not p.name.startswith("_") and readable(p, ignore):
                texts[p] = p.read_text(encoding="utf-8")
    inbound: dict[str, int] = defaultdict(int)
    outbound: dict[Path, int] = {}
    for p, text in texts.items():
        n = 0
        for raw in WIKILINK_RE.findall(text):
            target = re.split(r"[|#^]", raw, maxsplit=1)[0].strip()
            if not target:
                continue
            base_name = target.rsplit("/", 1)[-1]
            stem = base_name.rsplit(".", 1)[0]
            if base_name in names or stem in names:
                n += 1
                inbound[stem] += 1
            else:
                out["broken"].append((rel(p), raw))
        outbound[p] = n
    for p, text in texts.items():
        parts = p.relative_to(r).parts
        is_node = parts[0] == "people" or (parts[0] == "topics" and len(parts) >= 2) or \
            (parts[0] == "projects" and p.name == "README.md")
        key = p.parent.name if p.name == "README.md" else p.stem
        if is_node and outbound[p] == 0 and inbound.get(key, 0) == 0 and inbound.get(p.stem, 0) == 0:
            out["orphans"].append(rel(p))
        n_lines = text.count("\n") + 1
        if n_lines > cfg["thresholds"]["oversized_page_lines"]:
            out["oversized"].append((rel(p), n_lines))
    return out


def doctor_summary() -> str:
    exe = shutil.which("brain")
    if not exe:
        return "_Skipped: `brain` is not on PATH. Run `brain doctor` yourself._"
    try:
        res = subprocess.run([exe, "doctor"], capture_output=True, text=True, timeout=90, cwd=root())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"_`brain doctor` could not run: {exc}_"
    body = "\n".join((res.stdout or res.stderr).strip().splitlines()[:40]) or "(no output)"
    return f"Exit code {res.returncode} (non-zero means drift: that is the signal, not an error).\n\n```\n{body}\n```"


def render(week: str, today: date, cfg: dict, led: dict, proj: dict, mem: list[str], prop: dict, vault: dict,
           doctor: str) -> str:
    th = cfg["thresholds"]
    L: list[str] = [f"# System review - {week}", "",
                    f"_Generated {today.isoformat()}. Observational only: nothing has been applied. "
                    "You promote, demote or ignore._", ""]
    L += ["## Promotion candidates", ""]
    if led["promotion"]:
        L += [f"_Items supported by at least {th['promotion_min_sessions']} distinct sessions. "
              "Promote a pattern to `RULES.md`, or a hypothesis to a decision or rule, or keep watching._", ""]
        for i in led["promotion"]:
            L.append(f"- **{i['id']}** ({i['kind']}) {i['statement']}  \n  {i['supports']} sessions for, "
                     f"{i['refutes']} against; first seen {i['first_seen']}, last {i['last_seen']}")
    else:
        L.append("_None this week._")
    L += ["", "## Demotion candidates", ""]
    if led["demotion"]:
        L += [f"_Open items refuted by at least {th['demotion_min_refutations']} sessions and more than they are supported._", ""]
        for i in led["demotion"]:
            L.append(f"- **{i['id']}** {i['statement']} ({i['refutes']} against, {i['supports']} for)")
    else:
        L.append("_None this week._")
    L += ["", "## Stale items", ""]
    stale_any = led["stale"] or proj["stale_open"] or proj["inactive"]
    if not stale_any:
        L.append("_None._")
    if led["stale"]:
        L += [f"### Ledger items not seen for more than {th['stale_ledger_days']} days", ""]
        L += [f"- **{i['id']}** {i['statement']} ({i['age_days']}d)" for i in led["stale"]] + [""]
    if proj["stale_open"]:
        L += [f"### Open project entries older than {th['stale_entry_days']} days", ""]
        L += [f"- `{t}` ({facet}, {s}, {age}d): close it, update it or accept the staleness"
              for t, s, age, facet in proj["stale_open"][:25]] + [""]
    if proj["inactive"]:
        L += [f"### Projects with no entry for more than {th['inactive_project_days']} days", ""]
        L += [f"- `{name}` ({age}d)" for name, age in proj["inactive"]] + [""]
    L += [f"## MEMORY summary (last {th['memory_window_days']} days)", ""]
    L += [f"- {m}" for m in mem] or ["_No new MEMORY entries in the window._"]
    L += ["", "## Proposals", ""]
    if prop["total"]:
        tally = ", ".join(f"{k}: {v}" for k, v in sorted(prop["tally"].items()))
        L.append(f"Tally - {tally}.")
        if prop["open_old"]:
            L += ["", f"Open for more than {th['proposal_resurface_days']} days (accept or reject with `brain kb confirm PRP-NNN [--reject]`):"]
            L += [f"- {pid} {title} ({age}d)" for pid, title, age in prop["open_old"]]
    else:
        L.append("_No proposals yet._")
    if proj["unconfirmed_ai"]:
        L += ["", f"AI-written entries still unconfirmed after {th['proposal_resurface_days']} days:", ""]
        L += [f"- `{t}` ({facet}, {age}d)" for t, s, age, facet in proj["unconfirmed_ai"][:25]]
    L += ["", "## Drift", ""]
    L += [f"- {s}" for s in proj["skeleton"]] or ["_No project is missing its standard files._"]
    L += ["", "## Vault health", ""]
    if not (vault["broken"] or vault["orphans"] or vault["oversized"]):
        L.append("_Clean: no broken links, orphans or oversized pages._")
    if vault["broken"]:
        L += [f"### Broken wikilinks ({len(vault['broken'])})", ""]
        L += [f"- `{f}` -> `[[{r}]]`" for f, r in vault["broken"][:25]]
        if len(vault["broken"]) > 25:
            L.append(f"- ...and {len(vault['broken']) - 25} more.")
        L.append("")
    if vault["orphans"]:
        L += [f"### Orphan pages, no links in or out ({len(vault['orphans'])})", ""]
        L += [f"- `{f}`" for f in vault["orphans"][:25]] + [""]
    if vault["oversized"]:
        L += [f"### Pages over {th['oversized_page_lines']} lines", ""]
        L += [f"- `{f}` ({n} lines): split or compress" for f, n in vault["oversized"]] + [""]
    L += ["## Workspace health (`brain doctor`)", "", doctor, "",
          "## Not scripted: scheduled-task drift", "",
          "Compare the scheduled-task registry (`list_scheduled_tasks`) with the `scheduled` entries of the modules "
          "enabled in `.claude/brain.json`: flag tasks that run but are not declared, declared but not registered, "
          "or registered but disabled.", "",
          "---", "",
          "**What to do with this report**", "",
          "1. Skim it (about two minutes).",
          "2. For each promotion candidate, decide: promote to `RULES.md` yourself, keep watching, or reject "
          "(`ledger.py set-status --id <ID> --status promoted|rejected`).",
          "3. Answer open proposals with `brain kb confirm`.",
          "4. Touch or close the stale items, or accept them."]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", help="ISO week YYYY-Www (default: the week of --today)")
    ap.add_argument("--today", help="YYYY-MM-DD, for reproducible runs (default: today)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--dry-run", action="store_true", help="print the report instead of writing it")
    ap.add_argument("--no-doctor", action="store_true", help="do not call `brain doctor`")
    args = ap.parse_args(argv)

    try:
        cfg = load_config(Path(args.config))
    except (OSError, ValueError, KeyError) as exc:
        emit({"brick": "system-review", "status": "failed", "reason": f"bad config: {exc}"})
        return 2
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    week = args.week or iso_week(today)[1]
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        emit({"brick": "system-review", "status": "failed", "reason": f"bad ISO week {week!r}, expected YYYY-Www"})
        return 2

    ignore = ignored_dirs(cfg)
    led = ledger_scan(cfg, today)
    proj = project_scan(cfg, today, ignore)
    mem = memory_recent(cfg, today)
    prop = proposals_scan(cfg, today)
    vault = vault_health(cfg, ignore)
    doctor = "_Skipped (--no-doctor)._" if args.no_doctor else doctor_summary()
    report = render(week, today, cfg, led, proj, mem, prop, vault, doctor)

    counts = {"promotion": len(led["promotion"]), "demotion": len(led["demotion"]),
              "stale": len(led["stale"]) + len(proj["stale_open"]) + len(proj["inactive"]),
              "orphans": len(vault["orphans"]), "broken_links": len(vault["broken"]),
              "drift": len(proj["skeleton"]), "proposals_open": prop["tally"].get("open", 0),
              "proposals_open_old": len(prop["open_old"])}
    if args.dry_run:
        print(report)
        return 0
    out = path("learning", "reviews") / cfg["scan"]["output_filename_template"].format(iso_week=week)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    emit({"brick": "system-review", "status": "success", "counts": counts, "outputs": [rel(out)],
          "warnings": [], "observations": []})
    return 0


if __name__ == "__main__":
    sys.exit(main())
