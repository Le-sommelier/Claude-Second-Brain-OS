"""`brain new project|topic|person <slug>`: scaffold from brain-core's templates. Never overwrites."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from brainos.workspace import emit, owner, path, rel

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def plan_tree(src: Path, dest: Path, values: dict) -> list[tuple[Path, str]]:
    out = []
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        out.append((dest / f.relative_to(src), fill(f.read_text(encoding="utf-8"), values)))
    return out


def cmd_new(args) -> int:
    slug = args.slug.strip().lower()
    if not SLUG_RE.match(slug):
        raise SystemExit(f"{args.slug!r} is not kebab-case (a-z, 0-9, hyphens)")
    if args.kind == "person" and "-" not in slug:
        raise SystemExit("person IDs are <first>-<last>, e.g. riley-chen")
    title = args.title or " ".join(w.capitalize() for w in slug.split("-"))
    values = {"SLUG": slug, "TITLE": title, "TODAY": date.today().isoformat(),
              "OWNER_PERSON_ID": owner().get("person_id") or "owner"}
    if args.kind == "person":
        target = path("core", "people") / f"{slug}.md"
        files = [(target, fill((TEMPLATES / "person" / "person.md").read_text(encoding="utf-8"), values))]
        next_steps = [f"add `- {{id: {slug}, name: {title}}}` to {rel(path('core', 'org'))} so trust tiers see them"]
    else:
        base = path("core", "projects" if args.kind == "project" else "topics") / slug
        if base.exists():
            raise SystemExit(f"{rel(base)} already exists; nothing written")
        files = plan_tree(TEMPLATES / args.kind, base, values)
        next_steps = ["fill the human-fenced sections of README.md",
                      "run `brain kb build` then `brain kb index` to refresh the current-state block"]
        if args.kind == "project":
            next_steps.insert(1, "list the team in teams.md (person IDs from people/_org.yaml)")
    existing = [rel(p) for p, _ in files if p.exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite: {', '.join(existing)}")
    if not args.dry_run:
        for p, text in files:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    emit({"status": "success", "kind": args.kind, "id": slug, "dry_run": args.dry_run,
          "files": [rel(p) for p, _ in files], "next_steps": next_steps})
    return 0
