#!/usr/bin/env python3
"""Deterministic back end of /brain-core:setup. Plans or applies a workspace; never overwrites.

    python3 ${CLAUDE_SKILL_DIR}/scripts/setup_workspace.py --plan  --answers <answers.json> [--target DIR]
    python3 ${CLAUDE_SKILL_DIR}/scripts/setup_workspace.py --apply --answers <answers.json> [--target DIR]

answers.json (written by the skill with the Write tool):

    {
      "target": "~/brain-workspace",                    # optional; --target wins, else the current directory
      "owner": {"name": "Alex Morgan", "first_name": "Alex", "person_id": "alex-morgan",
                "role": "Senior PM", "company": "Fernhill", "timezone": "Europe/London",
                "week_starts": "monday"},
      "modules": ["brain-ingest", "brain-ingest-slack"],    # brain-core is implied
      "confidential": {"globs": ["growth/**"], "channel_patterns": ["*-leads", "#private-exec-room"]}
    }

Confidential patterns are the defaults plus these additions (`"replace_defaults": true` opts out).
brain.json also gets a setup stamp, refreshed on every run: `braincore_version` and
`modules_declined` (installed modules the owner chose not to enable; drift checks skip them).

--plan prints every action (mkdir, write, merge, skip) and writes nothing at all.
--apply performs the same plan. Rules:
  - a template is copied only when its target is missing (checked again right before writing);
  - brain.json, paths.json and the pipeline are merged add-only: new modules, new path keys and
    new bricks are added; existing values are kept. Any path collision aborts before the first write;
  - module plugin roots are refreshed in the pipeline on every run (cache paths carry versions);
  - scheduled tasks are only proposed (the skill registers them after the owner says yes);
  - re-running with the same answers is a no-op.
Prints one JSON object.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "scripts"))
from braincore.modules import discover, merge_paths, merge_pipeline  # noqa: E402

WS_TEMPLATES = PLUGIN / "templates" / "workspace"
RENAMES = {"workspace.gitignore": ".gitignore"}
SPECIAL = {".claude/brain.json", ".claude/paths.json"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
BRAINCORE_VERSION = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
DEFAULT_CHANNELS = ["*-leadership*", "*-leads", "*-lead-*", "*-exec*", "exec-*", "leads-*"]


def fail(msg: str, **extra) -> int:
    print(json.dumps({"status": "error", "error": msg, **extra}, indent=2))
    return 1


def validate(answers: dict) -> list[str]:
    errs = []
    own = answers.get("owner") or {}
    for k in ("name", "first_name", "person_id", "role", "company", "timezone"):
        if not str(own.get(k) or "").strip():
            errs.append(f"owner.{k} is required")
    if own.get("person_id") and not ID_RE.match(own["person_id"]):
        errs.append("owner.person_id must be <first>-<last> in kebab-case, e.g. alex-morgan")
    if own.get("timezone"):
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(own["timezone"])
        except Exception:
            errs.append(f"owner.timezone {own['timezone']!r} is not an IANA zone (e.g. Europe/London)")
    if not isinstance(answers.get("modules", []), list):
        errs.append("modules must be a list of module names")
    conf = answers.get("confidential") or {}
    for k in ("globs", "channel_patterns"):
        if k in conf and not isinstance(conf[k], list):
            errs.append(f"confidential.{k} must be a list")
    return errs


def _union(*lists) -> list[str]:
    out: list[str] = []
    for lst in lists:
        for x in lst or []:
            if x not in out:
                out.append(x)
    return out


def confidential_lists(answers: dict) -> tuple[list[str], list[str]]:
    """Defaults plus the owner's additions. `"replace_defaults": true` opts out of the defaults."""
    conf = answers.get("confidential") or {}
    if conf.get("replace_defaults"):
        return list(conf.get("globs") or []), list(conf.get("channel_patterns") or [])
    return _union(["growth/**"], conf.get("globs")), _union(DEFAULT_CHANNELS, conf.get("channel_patterns"))


def values_for(answers: dict, modules: list[str]) -> dict:
    own = answers["owner"]
    globs, chans = confidential_lists(answers)
    return {
        "OWNER_NAME": own["name"], "OWNER_FIRST_NAME": own["first_name"], "OWNER_PERSON_ID": own["person_id"],
        "OWNER_ROLE": own["role"], "COMPANY": own["company"], "TIMEZONE": own["timezone"],
        "TODAY": answers.get("today") or date.today().isoformat(),
        "MODULES_LIST": ", ".join(modules),
        "CONFIDENTIAL_GLOBS": ", ".join(f"`{g}`" for g in globs),
        "CONFIDENTIAL_CHANNELS": ", ".join(f"`{c}`" for c in chans),
    }


def fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def load_json(p: Path, default=None):
    if not p.is_file():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def build_plan(answers: dict, target: Path, extra_dirs: list[Path]) -> dict:
    found = discover(PLUGIN, extra_dirs)
    wanted = ["brain-core"] + [m for m in answers.get("modules", []) if m != "brain-core"]
    missing = [m for m in wanted if m not in found]
    selected = [found[m] for m in wanted if m in found]
    for m in list(selected):  # pull in declared requirements that are installed
        for req in m.get("requires") or []:
            if req in found and found[req] not in selected:
                selected.append(found[req])
    names = [m["module"] for m in selected]
    declined = sorted(set(found) - set(names))
    values = values_for(answers, names)
    actions: list[dict] = []
    writes: dict[str, str] = {}  # rel path -> content, only for missing targets
    warnings = [f"module {m} requested but not installed; install it, then re-run setup" for m in missing]

    def want_write(rel_path: str, content: str, origin: str) -> None:
        if rel_path in writes:
            return
        if (target / rel_path).exists():
            actions.append({"op": "skip", "path": rel_path, "detail": f"exists, kept as is ({origin})"})
        else:
            writes[rel_path] = content
            actions.append({"op": "write", "path": rel_path, "detail": origin})

    # folders
    folders = []
    for m in selected:
        for f in m.get("folders") or []:
            if f not in folders:
                folders.append(f)
    mkdirs = [f for f in folders if not (target / f).is_dir()]
    actions += [{"op": "mkdir", "path": f, "detail": "folder"} for f in mkdirs]

    # brain.json (add-only merge)
    brain_rel = ".claude/brain.json"
    existing_cfg = load_json(target / brain_rel)
    conf = answers.get("confidential") or {}
    if existing_cfg is None:
        cfg = json.loads((WS_TEMPLATES / brain_rel).read_text(encoding="utf-8"))
        own = answers["owner"]
        cfg["owner"] = {"name": own["name"], "first_name": own["first_name"], "person_id": own["person_id"],
                        "role": own["role"], "company": own["company"], "timezone": own["timezone"],
                        "week_starts": own.get("week_starts", "monday")}
        cfg["modules"] = names
        cfg["confidential"]["globs"], cfg["confidential"]["channel_patterns"] = confidential_lists(answers)
        cfg["braincore_version"] = BRAINCORE_VERSION
        cfg["modules_declined"] = declined
        for m in selected:
            for g in m.get("confidential_globs") or []:
                if g not in cfg["confidential"]["globs"]:
                    cfg["confidential"]["globs"].append(g)
        writes[brain_rel] = json.dumps(cfg, indent=2) + "\n"
        actions.append({"op": "write", "path": brain_rel, "detail": "owner profile, modules, confidential patterns"})
    else:
        cfg = existing_cfg
        have = [x if isinstance(x, str) else x.get("name") for x in cfg.get("modules") or []]
        new_mods = [n for n in names if n not in have]
        new_globs = [g for m in selected for g in m.get("confidential_globs") or []
                     if g not in (cfg.get("confidential") or {}).get("globs", [])]
        stamp_changed = cfg.get("braincore_version") != BRAINCORE_VERSION or cfg.get("modules_declined") != declined
        if new_mods or new_globs or stamp_changed:
            cfg = json.loads(json.dumps(cfg))
            cfg["modules"] = (cfg.get("modules") or []) + new_mods
            cfg.setdefault("confidential", {}).setdefault("globs", [])
            cfg["confidential"]["globs"] += sorted(set(new_globs))
            cfg["braincore_version"] = BRAINCORE_VERSION
            cfg["modules_declined"] = declined
            writes[brain_rel] = json.dumps(cfg, indent=2) + "\n"
            actions.append({"op": "merge", "path": brain_rel,
                            "detail": f"add modules {new_mods}" + (f", confidential globs {sorted(set(new_globs))}" if new_globs else "")
                            + "; setup stamp (braincore_version, modules_declined) refreshed; owner profile kept"})
        else:
            actions.append({"op": "skip", "path": brain_rel, "detail": "exists, nothing to add"})

    # paths.json (add-only merge; collisions abort)
    paths_rel = ".claude/paths.json"
    base_paths = load_json(target / paths_rel) or json.loads((WS_TEMPLATES / paths_rel).read_text(encoding="utf-8"))
    merged_paths, added_keys, collisions = merge_paths(base_paths, selected)
    if not (target / paths_rel).exists():
        writes[paths_rel] = json.dumps(merged_paths, indent=2) + "\n"
        actions.append({"op": "write", "path": paths_rel, "detail": f"core paths + {len(added_keys)} module key(s)"})
    elif added_keys:
        writes[paths_rel] = json.dumps(merged_paths, indent=2) + "\n"
        actions.append({"op": "merge", "path": paths_rel, "detail": f"add {added_keys}"})
    else:
        actions.append({"op": "skip", "path": paths_rel, "detail": "exists, nothing to add"})
    core = merged_paths.get("core") or {}

    # pipeline: brain-ingest's base template, then every module's bricks
    pipe_rel = core.get("pipeline", "system/run/pipeline.json")
    ingest = next((m for m in selected if m["module"] == "brain-ingest"), None)
    if ingest:
        existing_pipe = load_json(target / pipe_rel)
        if existing_pipe is None:
            tpl = next((t for t in ingest.get("templates") or [] if t.get("to") == pipe_rel), None)
            src = Path(ingest["_root"]) / (tpl["from"] if tpl else "templates/pipeline.base.json")
            existing_pipe = load_json(src) or {}
        pipe, added_bricks, pipe_collisions = merge_pipeline(existing_pipe, selected)
        collisions += pipe_collisions
        new_text = json.dumps(pipe, indent=2) + "\n"
        old_text = (target / pipe_rel).read_text(encoding="utf-8") if (target / pipe_rel).is_file() else None
        if old_text != new_text:
            writes[pipe_rel] = new_text
            actions.append({"op": "write" if old_text is None else "merge", "path": pipe_rel,
                            "detail": f"add bricks {added_bricks}; module roots refreshed" if added_bricks
                            else "module roots refreshed; owner edits kept"})
        else:
            actions.append({"op": "skip", "path": pipe_rel, "detail": "pipeline current"})
    elif any(m.get("bricks") for m in selected if m["module"] != "brain-core"):
        warnings.append("modules with ingest bricks are selected but brain-ingest is not; their bricks won't run")

    # workspace templates (brain-core)
    for src in sorted(p for p in WS_TEMPLATES.rglob("*") if p.is_file()):
        rel_src = src.relative_to(WS_TEMPLATES).as_posix()
        if rel_src in SPECIAL:
            continue
        dest = "/".join(RENAMES.get(part, part) for part in rel_src.split("/"))
        want_write(dest, fill(src.read_text(encoding="utf-8"), values), "brain-core template")

    # module templates
    for m in selected:
        if m["module"] == "brain-core":
            continue
        for t in m.get("templates") or []:
            if t.get("to") == pipe_rel:
                continue  # handled by the pipeline merge
            src = Path(m["_root"]) / t["from"]
            if not src.is_file():
                warnings.append(f"{m['module']}: template {t['from']} missing in the plugin")
                continue
            want_write(t["to"], fill(src.read_text(encoding="utf-8"), values), f"{m['module']} template")

    scheduled = [{"module": m["module"], "name": s["name"], "cron": s.get("cron"),
                  "prompt_file": str(Path(m["_root"]) / s["prompt"]) if s.get("prompt") else None}
                 for m in selected for s in m.get("scheduled") or []]
    connectors = [{"module": m["module"], **c} for m in selected for c in m.get("connectors") or []]
    return {"target": str(target), "modules": names, "modules_missing": missing, "actions": actions,
            "mkdirs": mkdirs, "writes": writes, "collisions": collisions, "warnings": warnings,
            "scheduled_proposals": scheduled, "connectors": connectors}


def apply(plan: dict, target: Path) -> tuple[list[str], list[str]]:
    written, skipped = [], []
    for f in plan["mkdirs"]:
        (target / f).mkdir(parents=True, exist_ok=True)
    for rel_path, content in plan["writes"].items():
        dest = target / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        merge = next((a["op"] for a in plan["actions"] if a["path"] == rel_path), "write") == "merge"
        if merge:
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(dest)
            written.append(rel_path)
            continue
        try:
            with dest.open("x", encoding="utf-8") as fh:  # exclusive: never clobber a file that appeared meanwhile
                fh.write(content)
            written.append(rel_path)
        except FileExistsError:
            skipped.append(rel_path)
    return written, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    ap.add_argument("--answers", required=True)
    ap.add_argument("--target")
    ap.add_argument("--modules-dir", action="append", default=[], help="extra folder holding plugin dirs")
    args = ap.parse_args()
    try:
        answers = json.loads(Path(args.answers).expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"cannot read answers: {exc}")
    errs = validate(answers)
    if errs:
        return fail("answers are incomplete", problems=errs)
    target = Path(args.target or answers.get("target") or ".").expanduser().resolve()
    if target.exists() and not target.is_dir():
        return fail(f"target {target} is a file")
    plan = build_plan(answers, target, [Path(d).expanduser() for d in args.modules_dir])
    public = {k: v for k, v in plan.items() if k not in ("writes", "mkdirs")}
    counts = {op: sum(1 for a in plan["actions"] if a["op"] == op) for op in ("mkdir", "write", "merge", "skip")}
    if plan["collisions"]:
        print(json.dumps({"status": "error", "error": "collisions: nothing written", "counts": counts, **public}, indent=2))
        return 1
    if args.plan:
        print(json.dumps({"status": "planned", "counts": counts, **public}, indent=2))
        return 0
    target.mkdir(parents=True, exist_ok=True)
    written, skipped = apply(plan, target)
    print(json.dumps({"status": "applied", "counts": counts, "written": written, "skipped_appeared_meanwhile": skipped,
                      **public}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
