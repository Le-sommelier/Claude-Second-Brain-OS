"""`brain doctor`: catch silent drift loudly. Read-only; exits 1 when any check errors.

Checks: config (placeholders left, owner filled), path map (every key resolves), modules
(enabled vs installed, their path sections merged, pipeline module roots still on disk),
schema (present, same version as the plugin), Python deps, context-layer references
(rules and styles routed from .claude/CLAUDE.md exist), stale project READMEs, and a kb
validation pass. Connectors and scheduled tasks can't be seen from the filesystem: they are
listed under `verify_in_session` for the doctor skill to check through its tools.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from brainos.workspace import config, emit, paths, root

PLUGIN = Path(__file__).resolve().parents[2]
REQUIRED_CORE = ["critical_facts", "claude_md", "rules", "schema", "projects", "inbox"]
STALE_README_DAYS = 60
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")


class Report:
    def __init__(self):
        self.checks: list[dict] = []

    def add(self, name: str, level: str, detail: str | list) -> None:
        self.checks.append({"check": name, "level": level, "detail": detail})

    @property
    def status(self) -> str:
        levels = {c["level"] for c in self.checks}
        return "error" if "error" in levels else "warn" if "warn" in levels else "ok"


def check_config(r: Report) -> dict:
    cfg = config()
    raw = json.dumps(cfg)
    left = sorted(set(PLACEHOLDER_RE.findall(raw)))
    own = cfg.get("owner") or {}
    missing = [k for k in ("name", "person_id", "timezone") if not own.get(k)]
    if left or missing:
        r.add("config", "error", f"brain.json: placeholders left {left} / owner fields missing {missing}; re-run /brain-core:setup")
    else:
        r.add("config", "ok", f"owner {own.get('person_id')}, {len(cfg.get('modules') or [])} module(s) enabled")
    for name in ("CRITICAL_FACTS.md", "CLAUDE.md", "RULES.md"):
        f = root() / name
        if f.is_file() and PLACEHOLDER_RE.search(f.read_text(encoding="utf-8")):
            r.add("placeholders", "warn", f"{name} still has {{{{PLACEHOLDERS}}}}: fill them in")
    return cfg


def check_paths(r: Report) -> None:
    data = paths()
    on_demand = set((data.get("_notes") or {}).get("create_on_demand", []))
    missing, required_missing = [], []
    for section, keys in data.items():
        if section.startswith("_") or not isinstance(keys, dict):
            continue
        for k, v in keys.items():
            if k.startswith("_") or not isinstance(v, str) or v in on_demand:
                continue
            target = root() / v
            if target.exists():
                continue
            if section == "core" and k in REQUIRED_CORE:
                required_missing.append(f"{section}.{k} -> {v}")
            elif not target.parent.exists():
                # A missing module file whose folder exists is created on first run (ledgers,
                # state files, rendered pages): not worth a warning straight after setup.
                missing.append(f"{section}.{k} -> {v}")
    if required_missing:
        r.add("paths", "error", required_missing)
    if missing:
        r.add("paths", "warn", missing + ["(create them, or list them under _notes.create_on_demand)"])
    if not missing and not required_missing:
        r.add("paths", "ok", "every paths.json key resolves")


def check_modules(r: Report, cfg: dict) -> dict:
    from braincore.modules import discover
    installed = discover(PLUGIN)
    enabled = [m if isinstance(m, str) else m.get("name") for m in cfg.get("modules") or []]
    enabled = [m for m in enabled if m]
    not_installed = sorted(set(enabled) - set(installed))
    not_enabled = sorted(set(installed) - set(enabled) - set(cfg.get("modules_declined") or []) - {"brain-core"})
    if not_installed:
        r.add("modules", "error", f"enabled in brain.json but not installed: {not_installed}")
    if not_enabled:
        r.add("modules", "warn", f"installed but not set up in this workspace: {not_enabled} (run /brain-core:setup)")
    pj = paths()
    unmerged = sorted(f"{m}: {s}" for m in enabled if m in installed
                      for s in (installed[m].get("paths") or {}) if s not in pj)
    if unmerged:
        r.add("module-paths", "error", f"path sections not merged into paths.json: {unmerged}; re-run /brain-core:setup")
    if not (not_installed or unmerged):
        r.add("modules", "ok", f"{len(enabled)} enabled module(s) installed and merged")
    return {m: installed[m] for m in enabled if m in installed}


def check_pipeline(r: Report, enabled: dict) -> None:
    from braincore.run import stale_module_roots
    pfile = root() / (paths().get("core") or {}).get("pipeline", "system/run/pipeline.json")
    if not pfile.is_file():
        level = "error" if "brain-ingest" in enabled else "ok"
        r.add("pipeline", level, "no pipeline.json" + (" although brain-ingest is enabled; re-run /brain-core:setup" if level == "error" else " (brain-ingest not enabled)"))
        return
    try:
        pipeline = json.loads(pfile.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        r.add("pipeline", "error", f"pipeline.json is not valid JSON: {exc}")
        return
    stale = stale_module_roots(pipeline)
    if stale:
        r.add("pipeline", "error", f"module roots no longer exist: {stale}; re-run /brain-core:setup to refresh module roots")
    orphan = []
    for st in pipeline.get("stages") or []:
        specs = [s for lane in (st.get("lanes") or {}).values() for s in lane] + (st.get("steps") or [])
        for s in specs:
            mod = str(s.get("brick", "")).split(":")[0]
            if ":" in str(s.get("brick", "")) and mod not in enabled and mod != "brain-core":
                orphan.append(s["brick"])
    if orphan:
        r.add("pipeline", "warn", f"bricks from modules not enabled: {orphan} (set enabled: false or re-run setup)")
    if not stale and not orphan:
        r.add("pipeline", "ok", f"{sum(1 for _ in pipeline.get('stages') or [])} stage(s), roots current")


def check_schema(r: Report) -> None:
    ws = root() / (paths().get("core") or {}).get("schema", "system/schema")
    plugin = PLUGIN / "templates" / "workspace" / "system" / "schema"
    problems = []
    for name in ("kb.sql", "attention.yaml", "entry-grammar.md", "_schema.md"):
        if not (ws / name).is_file():
            problems.append(f"{name} missing (plugin copy used as fallback)")
    if (ws / "kb.sql").is_file():
        ver = lambda p: (re.search(r"user_version\s*=\s*(\d+)", p.read_text(encoding="utf-8")) or [None, "?"])[1]
        if ver(ws / "kb.sql") != ver(plugin / "kb.sql"):
            problems.append(f"kb.sql version {ver(ws / 'kb.sql')} differs from the plugin's {ver(plugin / 'kb.sql')}")
    r.add("schema", "warn" if problems else "ok", problems or "schema present and current")


def check_deps(r: Report) -> bool:
    try:
        import yaml  # noqa: F401
        r.add("python", "ok", "PyYAML available")
        return True
    except ImportError:
        r.add("python", "error", "PyYAML missing: python3 -m pip install pyyaml (brain kb needs it)")
        return False


def check_context_layer(r: Report) -> None:
    agent_md = root() / ".claude" / "CLAUDE.md"
    if not agent_md.is_file():
        r.add("context", "warn", ".claude/CLAUDE.md missing")
        return
    text = agent_md.read_text(encoding="utf-8")
    missing = sorted({m for m in re.findall(r"\.claude/(?:rules|output-styles)/[a-z0-9-]+\.md", text)
                      if not (root() / m).is_file()})
    r.add("context", "error" if missing else "ok", f"routed but missing: {missing}" if missing else "rule and style routes resolve")


def check_stale_readmes(r: Report) -> None:
    base = root() / (paths().get("core") or {}).get("projects", "projects")
    stale = []
    for readme in sorted(base.glob("*/README.md")) if base.is_dir() else []:
        m = re.search(r"^last_reviewed:\s*(\d{4}-\d{2}-\d{2})", readme.read_text(encoding="utf-8"), re.M)
        if m:
            age = (date.today() - datetime.strptime(m.group(1), "%Y-%m-%d").date()).days
            if age > STALE_README_DAYS:
                stale.append(f"{readme.parent.name}: last_reviewed {m.group(1)} ({age}d)")
    if stale:
        r.add("stale-readmes", "warn", stale)


def check_kb(r: Report) -> None:
    from braincore.kb import collect
    _, errors, warnings, _ = collect()
    if errors:
        r.add("kb", "error", [f"{len(errors)} validation error(s); first:"] + errors[:10])
    else:
        r.add("kb", "warn" if len(warnings) > 20 else "ok", f"markdown validates; {len(warnings)} warning(s)")


def cmd_doctor(args) -> int:
    r = Report()
    r.add("root", "ok", str(root()))
    cfg = check_config(r)
    check_paths(r)
    enabled = check_modules(r, cfg)
    check_pipeline(r, enabled)
    check_schema(r)
    has_yaml = check_deps(r)
    check_context_layer(r)
    check_stale_readmes(r)
    if has_yaml and not args.quick:
        check_kb(r)
    verify = {
        "connectors": [{"module": m, **c} for m, man in enabled.items() for c in man.get("connectors") or []],
        "scheduled": [{"module": m, **s} for m, man in enabled.items() for s in man.get("scheduled") or []],
    }
    emit({"status": r.status, "checks": r.checks, "verify_in_session": verify})
    return 1 if r.status == "error" else 0
