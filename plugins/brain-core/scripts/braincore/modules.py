"""Module discovery and the add-only merges setup performs (paths, pipeline, brain.json modules).

Nothing here touches disk except `discover()` (read-only). Merges return new objects plus a
list of collisions; the caller refuses to write anything when collisions exist.
"""
from __future__ import annotations

import copy
import json
import re
import shlex
from pathlib import Path

CORE_STAGES = ["fetch", "transform", "index", "derive", "finalise"]


def _version_key(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", str(v or "0")))


def read_manifest(plugin_root: Path) -> dict | None:
    f = plugin_root / "brain.module.json"
    if not f.is_file():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    version = "0.0.0"
    pj = plugin_root / ".claude-plugin" / "plugin.json"
    if pj.is_file():
        try:
            version = json.loads(pj.read_text(encoding="utf-8")).get("version", version)
        except json.JSONDecodeError:
            pass
    if (plugin_root / ".orphaned_at").exists():
        return None
    return {**data, "_root": str(plugin_root.resolve()), "_version": version}


def discover(core_root: Path, extra_dirs: list[Path] | None = None) -> dict[str, dict]:
    """Find installed modules next to brain-core.

    Two layouts: a marketplace checkout (plugins/<name>/brain.module.json, siblings of brain-core)
    and the plugin cache (cache/<marketplace>/<name>/<version>/, so brain-core's ../.. holds
    the other plugins). The highest version of each module wins."""
    found: dict[str, dict] = {}
    candidates: list[Path] = []
    for base in [core_root.parent, *(extra_dirs or [])]:
        if base.is_dir():
            candidates += [p for p in base.iterdir() if p.is_dir()]
    grand = core_root.parent.parent
    if grand.is_dir() and not (core_root.parent / ".claude-plugin").exists():
        for plugin in grand.iterdir():
            if plugin.is_dir():
                candidates += [v for v in plugin.iterdir() if v.is_dir()]
    candidates.append(core_root)
    for c in candidates:
        m = read_manifest(c)
        if not m or not m.get("module"):
            continue
        prev = found.get(m["module"])
        if prev is None or _version_key(m["_version"]) > _version_key(prev["_version"]):
            found[m["module"]] = m
    return found


def merge_paths(base: dict, modules: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Add each module's path sections. Returns (merged, added_keys, collisions)."""
    out = copy.deepcopy(base)
    added, collisions = [], []
    for m in modules:
        for section, keys in (m.get("paths") or {}).items():
            if section.startswith("_") or not isinstance(keys, dict):
                continue
            sec = out.setdefault(section, {})
            for k, v in keys.items():
                if k in sec and sec[k] != v:
                    collisions.append(f"paths.{section}.{k}: {m['module']} wants {v!r}, workspace has {sec[k]!r}")
                elif k not in sec:
                    sec[k] = v
                    added.append(f"{section}.{k}")
    return out, added, collisions


def script_command(m: dict, brick: dict) -> str:
    script = Path(m["_root"]) / brick["script"]
    args = " ".join(shlex.quote(str(a)) for a in brick.get("args") or [])
    return f"python3 {shlex.quote(str(script))}" + (f" {args}" if args else "")


def merge_pipeline(base: dict, modules: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Add every module's bricks to the pipeline, record module roots. Returns (pipeline, added, collisions).

    A brick already present (same name) keeps the owner's edits (enabled, model). Script bricks
    get an absolute `command` built from the module's current root, refreshed on every run of
    setup because plugin cache paths carry versions."""
    out = copy.deepcopy(base) if base else {"_version": "1.0", "settings": {}, "stages": []}
    out.setdefault("stages", [])
    stages = {s["id"]: s for s in out["stages"]}
    added, collisions = [], []
    mods = out.setdefault("modules", {})
    for m in modules:
        mods[m["module"]] = {"root": m["_root"], "version": m["_version"]}
        for b in m.get("bricks") or []:
            stage_id = b.get("stage")
            if stage_id not in CORE_STAGES and stage_id not in stages:
                collisions.append(f"brick {b.get('brick')}: unknown stage {stage_id!r}")
                continue
            if stage_id not in stages:
                st = {"id": stage_id, "lanes": {}} if stage_id == "fetch" else {"id": stage_id, "steps": []}
                if stage_id == "derive":
                    st["parallel"] = True
                out["stages"].append(st)
                stages[stage_id] = st
            st = stages[stage_id]
            entry = {k: v for k, v in b.items() if k not in ("stage", "lane")}
            if entry.get("script") and not entry.get("command"):
                entry["kind"] = "script"
                entry["command"] = script_command(m, entry)
            if "lanes" in st:
                lane = st["lanes"].setdefault(b.get("lane") or m["module"].removeprefix("brain-"), [])
            else:
                lane = st.setdefault("steps", [])
            existing = next((x for x in lane if x.get("brick") == entry.get("brick")), None)
            if existing is None:
                lane.append(entry)
                added.append(entry["brick"])
            elif entry.get("command") and existing.get("script") == entry.get("script"):
                existing["command"] = entry["command"]  # refresh the root, keep the owner's flags
    rank = {s: i for i, s in enumerate(CORE_STAGES)}
    out["stages"].sort(key=lambda s: rank.get(s["id"], len(CORE_STAGES)))
    return out, added, collisions
