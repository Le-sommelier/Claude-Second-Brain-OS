#!/usr/bin/env python3
"""brain-core session hooks. One script, one sub-command per event (see hooks.json).

    session-start        tiered read-order bundle by model, plus a stale-config guard and health
    user-prompt-submit   re-anchor Haiku sessions with CRITICAL_FACTS every turn
    post-tool-use        warn-only checks on a just-edited workspace file (additionalContext JSON)
    pre-compact          archive the transcript before compaction (.claude/.session-log/transcripts)
    stop                 one JSON line per session stop (.claude/.session-log/sessions.jsonl)

Every hook is silent and exits 0 outside a claude-second-brain-os workspace (no .claude/brain.json above
the payload cwd / $CLAUDE_PROJECT_DIR), on any error, and when stdin is a terminal.
Tiering (token discipline):
    haiku         CRITICAL_FACTS + todos                                   (~300 tokens)
    sonnet        + RULES + BRAND + MEMORY head (30 lines) + health        (~3.5k)
    opus/unknown  + SOUL + INDEX + MEMORY head (80) + .claude/CLAUDE.md    (~7k)
An unknown model gets the full bundle so a session is never under-oriented by accident.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
MARKER = Path(".claude") / "brain.json"
LOG_KEEP, TRANSCRIPTS_KEEP, TIER_FLAGS_KEEP = 200, 30, 50


def read_payload() -> dict:
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def find_root(payload: dict) -> Path | None:
    starts = [payload.get("cwd"), os.environ.get("BRAIN_ROOT"), os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()]
    for s in starts:
        if not s:
            continue
        p = Path(s).expanduser()
        try:
            p = p.resolve()
        except OSError:
            continue
        for parent in (p, *p.parents):
            if (parent / MARKER).is_file():
                return parent
    return None


def load_paths(root: Path) -> dict:
    try:
        return json.loads((root / ".claude" / "paths.json").read_text(encoding="utf-8")).get("core", {})
    except Exception:
        return {}


def core_path(root: Path, key: str, default: str) -> Path:
    return root / load_paths(root).get(key, default)


def session_dir(root: Path) -> Path:
    d = root / ".claude" / ".session-log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tier_of(model: str) -> str:
    m = (model or "").lower()
    return "haiku" if "haiku" in m else "sonnet" if "sonnet" in m else "full"


def tier_flag(root: Path, session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "unknown")[:64] or "unknown"
    return session_dir(root) / "tiers" / f"{safe}.tier"


# ---------------------------------------------------------------- stale-config guard / health


def plugin_version() -> str:
    try:
        return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version", "?")
    except Exception:
        return "?"


def config_drift(root: Path) -> list[str]:
    """Cheap checks that a workspace config went stale. Full checks: `brain doctor`."""
    out = []
    try:
        cfg = json.loads((root / MARKER).read_text(encoding="utf-8"))
    except Exception:
        return [".claude/brain.json is not valid JSON"]
    if "{{" in json.dumps(cfg):
        out.append("brain.json still has {{PLACEHOLDERS}}: re-run /brain-core:setup")
    ver = cfg.get("braincore_version")
    pv = plugin_version()
    if ver and pv != "?" and ver != pv:
        out.append(f"workspace set up with brain-core {ver}, plugin is {pv}: re-run /brain-core:setup to merge new paths and bricks")
    try:
        all_paths = json.loads((root / ".claude" / "paths.json").read_text(encoding="utf-8"))
    except Exception:
        return out + [".claude/paths.json missing or invalid: re-run /brain-core:setup"]
    sys.path.insert(0, str(PLUGIN / "scripts"))
    try:
        from braincore.modules import discover
        installed = discover(PLUGIN)
    except Exception:
        installed = {}
    enabled = [m if isinstance(m, str) else m.get("name") for m in cfg.get("modules") or []]
    for m in enabled:
        man = installed.get(m)
        if man is None:
            continue
        missing = [s for s in (man.get("paths") or {}) if s not in all_paths]
        if missing:
            out.append(f"{m} paths not merged ({', '.join(missing)}): re-run /brain-core:setup")
    new = sorted(set(installed) - set(enabled) - set(cfg.get("modules_declined") or []) - {"brain-core"})
    if new:
        out.append(f"installed but not set up here: {', '.join(new)}: run /brain-core:setup")
    pipe = root / all_paths.get("core", {}).get("pipeline", "system/run/pipeline.json")
    if pipe.is_file():
        try:
            mods = json.loads(pipe.read_text(encoding="utf-8")).get("modules") or {}
            stale = [n for n, v in mods.items() if isinstance(v, dict) and v.get("root") and not Path(v["root"]).is_dir()]
            if stale:
                out.append(f"pipeline module roots moved ({', '.join(sorted(stale))}): re-run /brain-core:setup to refresh module roots")
        except Exception:
            out.append("system/run/pipeline.json is not valid JSON")
    elif "brain-ingest" in enabled:
        out.append("brain-ingest enabled but no pipeline.json: re-run /brain-core:setup")
    return out


def health(root: Path) -> list[str]:
    out = []
    att = core_path(root, "attention", "inbox/attention.md")
    if att.is_file():
        text = att.read_text(encoding="utf-8")
        m = re.search(r"^date:\s*(\S+)", text, re.M)
        counts = re.findall(r"^## ([a-z-]+) \((\d+)\)", text, re.M)
        nonzero = [f"{n} {c}" for n, c in counts if c != "0"]
        if nonzero:
            out.append(f"Attention ({m.group(1) if m else '?'}): " + ", ".join(nonzero) + f" (see {att.relative_to(root)})")
    log = core_path(root, "run_log", "system/run/run-log.json")
    if log.is_file():
        try:
            runs = json.loads(log.read_text(encoding="utf-8")).get("runs") or []
            if runs:
                r = runs[0]
                out.append(f"Last ingest: {r.get('date')} {r.get('status')}"
                           + (f", partial dates {', '.join(r['dates_partial'])}" if r.get("dates_partial") else ""))
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- events


def section(title: str, p: Path, head: int | None = None) -> str:
    if not p.is_file():
        return ""
    lines = p.read_text(encoding="utf-8").splitlines()
    if head:
        lines = lines[:head]
        title = f"{title} (first {head} lines)"
    return f"\n----- {title} ({p.name}) -----\n" + "\n".join(lines) + "\n"


def session_start(root: Path, payload: dict) -> str:
    tier = tier_of(payload.get("model") or "")
    flag = tier_flag(root, payload.get("session_id", ""))
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(tier, encoding="utf-8")
    flags = sorted(flag.parent.glob("*.tier"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in flags[TIER_FLAGS_KEEP:]:
        old.unlink(missing_ok=True)
    today = date.today()
    iso = today.isocalendar()
    parts = ["=" * 60, f"  claude-second-brain-os session bootstrap  [tier: {tier}]",
             f"  {today.isoformat()}   ISO week {iso.year}-W{iso.week:02d}", "=" * 60]
    parts.append(section("CRITICAL FACTS", core_path(root, "critical_facts", "CRITICAL_FACTS.md")))
    parts.append(section("TODOS", core_path(root, "todos", "todos/todo.md")))
    if tier in ("sonnet", "full"):
        parts.append(section("RULES", core_path(root, "rules", "RULES.md")))
        if tier == "full":
            parts.append(section("SOUL", core_path(root, "soul", "SOUL.md")))
        parts.append(section("BRAND", core_path(root, "brand", "BRAND.md")))
        if tier == "full":
            parts.append(section("INDEX", core_path(root, "index", "INDEX.md")))
        parts.append(section("MEMORY, newest first", core_path(root, "memory", "MEMORY.md"), 30 if tier == "sonnet" else 80))
        if tier == "full":
            parts.append(section("AGENT OVERRIDES", root / ".claude" / "CLAUDE.md"))
    drift = config_drift(root)
    if drift:
        parts.append("\n----- CONFIG DRIFT (run /brain-core:doctor) -----\n" + "\n".join(f"- {d}" for d in drift) + "\n")
    if tier in ("sonnet", "full"):
        h = health(root)
        if h:
            parts.append("\n----- HEALTH -----\n" + "\n".join(f"- {x}" for x in h) + "\n")
    parts.append("=" * 60 + f"\n  Bootstrap complete [tier: {tier}]. MEMORY.md is newest-first.\n" + "=" * 60)
    return "\n".join(p for p in parts if p)


def user_prompt_submit(root: Path, payload: dict) -> str:
    flag = tier_flag(root, payload.get("session_id", ""))
    if not flag.is_file() or flag.read_text(encoding="utf-8").strip() != "haiku":
        return ""
    cf = core_path(root, "critical_facts", "CRITICAL_FACTS.md")
    body = cf.read_text(encoding="utf-8") if cf.is_file() else "(CRITICAL_FACTS.md missing)"
    return f"===== ANCHOR (per turn, Haiku) =====\n{body}\n(Full conventions in RULES.md; read it if this task needs them.)\n===== END ANCHOR ====="


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
README_KEYS = {"title", "owner", "status", "last_reviewed"}


def link_targets(root: Path) -> set[str]:
    names: set[str] = set()
    skip = {".git", "node_modules", "__pycache__", ".session-log"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for f in filenames:
            names.add(f.split(".", 1)[0])
    return names


def decision_ids(root: Path) -> set[str]:
    ids = set()
    base = core_path(root, "projects", "projects")
    for f in base.glob("*/decisions/*.md") if base.is_dir() else []:
        try:
            m = re.search(r"^id:\s*(\S+)", f.read_text(encoding="utf-8"), re.M)
        except OSError:
            continue
        if m:
            ids.add(m.group(1))
    return ids


def post_tool_use(root: Path, payload: dict) -> str:
    if payload.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return ""
    inp = payload.get("tool_input") or {}
    fp = inp.get("file_path") or inp.get("notebook_path")
    if not fp:
        return ""
    p = Path(fp)
    try:
        rel = p.resolve().relative_to(root)
    except (ValueError, OSError):
        return ""
    if not p.is_file() or p.suffix != ".md":
        return ""
    text = p.read_text(encoding="utf-8", errors="replace")
    warnings = []
    projects = load_paths(root).get("projects", "projects")
    topics = load_paths(root).get("topics", "topics")
    parts = rel.parts
    in_entity = len(parts) >= 3 and "/".join(parts[:-2]) in (projects, topics)
    # 1. facet log grammar (the same parser kb build uses)
    if in_entity and p.stem in ("status", "risks", "milestones", "resources", "hypotheses"):
        try:
            sys.path.insert(0, str(PLUGIN / "scripts"))
            for lib in (PLUGIN / "lib", PLUGIN.parents[1] / "lib"):
                if (lib / "brainos").is_dir():
                    sys.path.insert(0, str(lib))
                    break
            os.environ.setdefault("BRAIN_ROOT", str(root))
            from braincore.kb import validate_file
            errs = validate_file(p)
            if errs:
                warnings.append(f"[entry-grammar] {rel}: {len(errs)} problem(s), `brain kb build` will fail: " + "; ".join(errs[:5]))
        except Exception:
            pass
    # 2. project/topic README frontmatter
    if in_entity and p.name == "README.md":
        present = set(re.findall(r"^(\w+):", text.split("\n---", 1)[0], re.M)) if text.startswith("---") else set()
        missing = README_KEYS - present
        if missing:
            warnings.append(f"[readme] {rel}: frontmatter missing {', '.join(sorted(missing))}")
    # 3. citations resolve
    targets = WIKILINK_RE.findall(text)
    if targets:
        names = link_targets(root) | decision_ids(root)
        broken = []
        for t in targets:
            t = t.strip()
            if "/" in t and re.match(r"^[a-z0-9-]+/(RSK|DEP|MS|STA|RES|HYP)-\d{3}$", t):
                if not (root / projects / t.split("/")[0]).is_dir() and not (root / topics / t.split("/")[0]).is_dir():
                    broken.append(t)
                continue
            if t.rsplit("/", 1)[-1] not in names:
                broken.append(t)
        if broken:
            warnings.append(f"[citations] {rel}: {len(broken)} [[link]](s) don't resolve: " + ", ".join(broken[:8]))
    # 4. confidential path edited: remind
    try:
        cfg = json.loads((root / MARKER).read_text(encoding="utf-8"))
        from fnmatch import fnmatch
        if any(fnmatch(rel.as_posix(), g) for g in (cfg.get("confidential") or {}).get("globs", [])):
            warnings.append(f"[confidential] {rel} is confidential: never quote it into a shared output")
    except Exception:
        pass
    if not warnings:
        return ""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(warnings)}})


def pre_compact(root: Path, payload: dict) -> str:
    src = payload.get("transcript_path")
    if not src or not Path(src).is_file():
        return ""
    dest_dir = session_dir(root) / "transcripts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sid = re.sub(r"[^A-Za-z0-9]", "", payload.get("session_id", ""))[:8] or "nosid"
    trigger = re.sub(r"[^a-z]", "", payload.get("trigger", "auto")) or "auto"
    shutil.copyfile(src, dest_dir / f"{ts}-{sid}-{trigger}.jsonl")
    for old in sorted(dest_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[TRANSCRIPTS_KEEP:]:
        old.unlink(missing_ok=True)
    return ""


def stop(root: Path, payload: dict) -> str:
    log = session_dir(root) / "sessions.jsonl"
    today = date.today().isocalendar()
    entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "iso_week": f"{today.year}-W{today.week:02d}",
             "session_id": payload.get("session_id", ""), "transcript_path": payload.get("transcript_path", "")}
    lines = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    lines = [ln for ln in lines if ln.strip()][-(LOG_KEEP - 1):] + [json.dumps(entry)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ""


EVENTS = {"session-start": session_start, "user-prompt-submit": user_prompt_submit, "post-tool-use": post_tool_use,
          "pre-compact": pre_compact, "stop": stop}


def main() -> int:
    try:
        event = sys.argv[1] if len(sys.argv) > 1 else ""
        fn = EVENTS.get(event)
        if fn is None:
            return 0
        payload = read_payload()
        root = find_root(payload)
        if root is None:
            return 0
        out = fn(root, payload)
        if out:
            print(out)
    except Exception:
        pass  # hooks never block or break a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
