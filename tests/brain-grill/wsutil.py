"""Test helper: build a throwaway claude-second-brain-os workspace and run module scripts against it.

Layout assumed: <repo>/tests/<module>/wsutil.py. The workspace is assembled from the brain-core templates, then the
sample workspace (when present), then the module's own `paths` merged into paths.json, as /brain-core:setup would do.
Scripts run as subprocesses with BRAIN_ROOT set and the repo's lib/ on PYTHONPATH (plugins/*/lib is vendored later).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "plugins" / "brain-core" / "templates" / "workspace"
SAMPLE = REPO / "examples" / "sample-workspace"


def make_workspace(module: str, with_sample: bool = True) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="brain-test-"))
    claude = tmp / ".claude"
    claude.mkdir()
    cfg = json.loads((TEMPLATE / ".claude" / "brain.json").read_text(encoding="utf-8"))
    cfg["owner"].update({"name": "Alex Morgan", "first_name": "Alex", "person_id": "alex-morgan",
                         "role": "Senior PM", "company": "Fernhill", "timezone": "UTC"})
    (claude / "brain.json").write_text(json.dumps(cfg), encoding="utf-8")
    shutil.copy(TEMPLATE / ".claude" / "paths.json", claude / "paths.json")
    if with_sample and SAMPLE.is_dir():
        shutil.copytree(SAMPLE, tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.db"))
    meta = json.loads((REPO / "plugins" / module / "brain.module.json").read_text(encoding="utf-8"))
    paths = json.loads((claude / "paths.json").read_text(encoding="utf-8"))
    for section, entries in meta.get("paths", {}).items():
        paths.setdefault(section, {}).update(entries)
    (claude / "paths.json").write_text(json.dumps(paths), encoding="utf-8")
    for folder in meta.get("folders", []):
        (tmp / folder).mkdir(parents=True, exist_ok=True)
    return tmp


def run(script: Path, args: list[str], ws: Path, env: dict | None = None, stdin: str | None = None):
    """Run a script with cwd=ws. Returns (returncode, parsed JSON of stdout or None, stdout, stderr)."""
    e = dict(os.environ)
    e.update({"BRAIN_ROOT": str(ws), "PYTHONPATH": str(REPO / "lib"), "HOME": str(ws / "_home")})
    e.pop("CLAUDE_CONFIG_DIR", None)
    e.pop("BRAIN_TRANSCRIPTS_DIR", None)
    e.update(env or {})
    r = subprocess.run([sys.executable, str(script), *args], cwd=ws, env=e, capture_output=True, text=True, input=stdin)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        data = None
    return r.returncode, data, r.stdout, r.stderr
