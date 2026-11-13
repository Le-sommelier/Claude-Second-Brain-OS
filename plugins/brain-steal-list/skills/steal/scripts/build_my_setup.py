"""Generate steal/my-setup.md: a map of the owner's own setup, so a steal review can judge novelty against it.

Built from metadata only, never hand-written: the modules enabled in .claude/brain.json, the rule files, the
headings of RULES.md, and the names and one-line descriptions of the skills, commands, agents and hooks found in
the folders listed in steal.json -> setup_scan. Files that are confidential (frontmatter or globs) are skipped.
The output is fully determined by the workspace, so re-running it on an unchanged workspace changes nothing.

Usage: python3 ${CLAUDE_SKILL_DIR}/scripts/build_my_setup.py [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _steal  # noqa: E402
from brainos import frontmatter  # noqa: E402
from brainos.confidential import is_confidential_path  # noqa: E402
from brainos.workspace import config, path, rel, root  # noqa: E402

DESC_MAX = 140


def clip(text: str) -> str:
    one = " ".join(str(text or "").split())
    return one if len(one) <= DESC_MAX else one[: DESC_MAX - 1].rstrip() + "..."


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return None


def describe(p: Path) -> tuple[str, str] | None:
    """(name, description) for a skill/command/agent/rule file, or None when it must not be read."""
    r = rel(p)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm = frontmatter.parse(text)
    if is_confidential_path(r, fm):
        return None
    name = str(fm.get("name") or (p.parent.name if p.name == "SKILL.md" else p.stem))
    desc = fm.get("description")
    if not desc:
        _, body = frontmatter.split(text)
        desc = first_heading(body) or ""
    return name, clip(desc)


def scan_dir(base: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*")):
        if not p.is_file() or any(part.startswith(".") for part in p.relative_to(base).parts):
            continue
        if base.name == "skills" and p.name != "SKILL.md":
            continue
        if base.name != "hooks" and p.suffix.lower() != ".md":
            continue
        if base.name == "hooks":
            if not is_confidential_path(rel(p)):
                out.append((p.name, ""))
            continue
        d = describe(p)
        if d:
            out.append(d)
    return sorted(set(out))


def rules_headings() -> list[str]:
    f = path("core", "rules")
    if not f.is_file() or is_confidential_path(rel(f)):
        return []
    return [m.group(1) for m in re.finditer(r"^#{2,3}\s+(.+?)\s*$", f.read_text(encoding="utf-8"), re.M)][:60]


def build(today: str) -> tuple[str, dict]:
    cfg = config()
    owner = cfg.get("owner", {})
    L = ["---", "type: steal-my-setup", "generated: true", f"date: {today}", "---", "",
         "# My setup (generated, do not edit)", "",
         "_Written by `build_my_setup.py` from the workspace: modules, rule headings and the names and descriptions "
         "of skills, commands, agents and hooks. Re-run it instead of editing. The steal review reads it to judge "
         "novelty: an idea already covered here scores low._", ""]
    counts = {"modules": 0, "rules": 0, "skills": 0, "commands": 0, "agents": 0, "hooks": 0, "rule_headings": 0}
    if owner.get("role"):
        L += [f"**Role:** {owner['role']}", ""]
    mods = sorted(m if isinstance(m, str) else m.get("name", "") for m in cfg.get("modules", []))
    mods = [m for m in mods if m]
    counts["modules"] = len(mods)
    L += ["## Installed modules", ""] + ([f"- {m}" for m in mods] or ["_None recorded in brain.json._"]) + [""]
    heads = rules_headings()
    counts["rule_headings"] = len(heads)
    L += ["## Rules I already follow (headings of RULES.md)", ""] + ([f"- {h}" for h in heads] or ["_None._"]) + [""]
    for folder in _steal.settings()["setup_scan"]:
        items = scan_dir(root() / folder)
        label = Path(folder).name
        counts[label if label in counts else "rules"] += len(items)
        L += [f"## {folder}", ""]
        L += [f"- **{n}**{': ' + d if d else ''}" for n, d in items] or ["_Nothing found._"]
        L.append("")
    return "\n".join(L), counts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", help="YYYY-MM-DD for reproducible output (default: today)")
    args = ap.parse_args()
    text, counts = build(args.today or date.today().isoformat())
    dest = path("steal", "my_setup")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    _steal.emit({"status": "success", "my_setup": rel(dest), "counts": counts})


if __name__ == "__main__":
    main()
