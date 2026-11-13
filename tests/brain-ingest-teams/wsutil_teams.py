"""Test helper: build a throw-away workspace for one module and run its scripts inside it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE = "brain-ingest-teams"
SAMPLE = REPO / "examples" / "sample-workspace"
CORE = json.loads((REPO / "plugins" / "brain-core" / "templates" / "workspace" / ".claude" / "paths.json").read_text())["core"]
MODULE_JSON = json.loads((REPO / "plugins" / MODULE / "brain.module.json").read_text())

BRAIN_JSON = {
    "version": "0.1.0",
    "owner": {"name": "Alex Morgan", "first_name": "Alex", "person_id": "alex-morgan", "role": "Senior PM",
              "company": "Fernhill", "timezone": "Europe/London", "week_starts": "monday"},
    "modules": [MODULE],
    "confidential": {"globs": ["growth/**"], "channel_patterns": ["*-leads"]},
}


def make_workspace(tmp: str, copy: tuple[str, ...] = ()) -> Path:
    """Workspace root in tmp; `copy` lists sample-workspace sub-paths to copy in (files or folders)."""
    root = Path(tmp)
    (root / ".claude" / "brain").mkdir(parents=True)
    (root / ".claude" / "brain.json").write_text(json.dumps(BRAIN_JSON), encoding="utf-8")
    (root / ".claude" / "paths.json").write_text(json.dumps({"core": CORE, **MODULE_JSON["paths"]}), encoding="utf-8")
    for rel in copy:
        src, dst = SAMPLE / rel, root / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return root


def run(root: Path, script: Path | str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
    env["PYTHONPATH"] = str(REPO / "lib")
    return subprocess.run([sys.executable, str(script), *args], cwd=root, env=env, capture_output=True, text=True)


def run_json(root: Path, script: Path | str, *args: str) -> dict:
    proc = run(root, script, *args)
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise AssertionError(f"no JSON from {script}: rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")


def script(skill: str, name: str) -> Path:
    return REPO / "plugins" / MODULE / "skills" / skill / "scripts" / name
