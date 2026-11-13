"""Test helper: build a temp workspace from examples/sample-workspace and run module scripts against it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE_WS = REPO / "plugins" / "brain-core" / "templates" / "workspace"
SAMPLE = REPO / "examples" / "sample-workspace"
SUBS = {"{{OWNER_NAME}}": "Alex Morgan", "{{OWNER_FIRST_NAME}}": "Alex", "{{OWNER_PERSON_ID}}": "alex-morgan",
        "{{OWNER_ROLE}}": "Senior Product Manager", "{{COMPANY}}": "Fernhill", "{{TIMEZONE}}": "Europe/London"}


def _sub(text: str) -> str:
    for k, v in SUBS.items():
        text = text.replace(k, v)
    return text


def make_workspace(modules: list[str], copy: tuple[str, ...] = ("growth", "people")) -> Path:
    """Temp workspace: core config + the modules' paths merged (collisions fail), sample content, module templates."""
    tmp = Path(tempfile.mkdtemp(prefix="brain-test-"))
    (tmp / ".claude").mkdir()
    (tmp / ".claude" / "brain.json").write_text(_sub((CORE_WS / ".claude" / "brain.json").read_text()), encoding="utf-8")
    paths = json.loads((CORE_WS / ".claude" / "paths.json").read_text())
    manifests = [json.loads((REPO / "plugins" / m / "brain.module.json").read_text()) for m in modules]
    for man in manifests:
        for section, keys in man["paths"].items():
            if section in paths:
                raise AssertionError(f"paths section collision: {section}")
            paths[section] = keys
    (tmp / ".claude" / "paths.json").write_text(json.dumps(paths, indent=2), encoding="utf-8")
    for name in copy:
        if (SAMPLE / name).is_dir():
            shutil.copytree(SAMPLE / name, tmp / name)
    for man, m in zip(manifests, modules):
        for t in man.get("templates", []):
            dest = tmp / t["to"]
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(_sub((REPO / "plugins" / m / t["from"]).read_text()), encoding="utf-8")
    return tmp


def run(script: Path, args: list[str], cwd: Path, expect_json: bool = True):
    env = dict(os.environ, BRAIN_ROOT=str(cwd), PYTHONPATH=str(REPO / "lib"))
    r = subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=env, capture_output=True, text=True)
    out = None
    if expect_json and r.stdout.strip():
        out = json.loads(r.stdout)
    return r.returncode, out, r.stderr


def script(module: str, skill: str, name: str) -> Path:
    return REPO / "plugins" / module / "skills" / skill / "scripts" / name
