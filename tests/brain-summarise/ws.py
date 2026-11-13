"""Test helper: a throwaway workspace seeded from the brain-core templates and the sample workspace."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "plugins" / "brain-core" / "templates" / "workspace" / ".claude"
SAMPLE = REPO / "examples" / "sample-workspace"


def make_workspace(copy_sample: tuple[str, ...] = ()) -> Path:
    root = Path(tempfile.mkdtemp(prefix="brain-test-"))
    (root / ".claude").mkdir()
    subs = {"{{OWNER_NAME}}": "Alex Morgan", "{{OWNER_FIRST_NAME}}": "Alex", "{{OWNER_PERSON_ID}}": "alex-morgan",
            "{{OWNER_ROLE}}": "Senior PM", "{{COMPANY}}": "Fernhill", "{{TIMEZONE}}": "Europe/London"}
    for name in ("brain.json", "paths.json"):
        text = (TEMPLATE / name).read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        json.loads(text)
        (root / ".claude" / name).write_text(text, encoding="utf-8")
    for rel in copy_sample:
        src = SAMPLE / rel
        dst = root / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return root


def run(script: Path, root: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "BRAIN_ROOT": str(root), "PYTHONPATH": str(REPO / "lib")}
    return subprocess.run([sys.executable, str(script), *args], cwd=root, env=env, capture_output=True, text=True)


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p
