"""Shared test helpers: build a throwaway workspace and run the plugin scripts against it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "brain-ingest-slack"
CORE_PATHS = REPO / "plugins" / "brain-core" / "templates" / "workspace" / ".claude" / "paths.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_SLACK = REPO / "examples" / "sample-workspace" / "raw" / "slack"

SCRIPTS = {
    "channel": PLUGIN / "skills" / "ingest-slack-channels" / "scripts" / "format_channel_file.py",
    "ledger": PLUGIN / "skills" / "ingest-slack-channels" / "scripts" / "ledger.py",
    "plan": PLUGIN / "skills" / "ingest-slack-channels" / "scripts" / "fetch_channels.py",
    "flagged": PLUGIN / "skills" / "ingest-slack-flagged" / "scripts" / "format_flagged_file.py",
    "owed": PLUGIN / "skills" / "ingest-owed-replies" / "scripts" / "format_owed_replies.py",
}


def make_workspace() -> Path:
    """A minimal workspace: brain.json, merged paths.json, the module's templates in place."""
    ws = Path(tempfile.mkdtemp(prefix="brain-slack-test-"))
    (ws / ".claude" / "brain").mkdir(parents=True)
    (ws / ".claude" / "brain.json").write_text(json.dumps({
        "owner": {"name": "Alex Morgan", "first_name": "Alex", "person_id": "alex-morgan",
                  "role": "Senior PM", "company": "Fernhill", "timezone": "UTC"},
        "confidential": {"globs": ["growth/**"],
                         "channel_patterns": ["*-leadership*", "*-leads", "*-lead-*", "*-exec*", "exec-*", "leads-*"]},
    }), encoding="utf-8")
    paths = json.loads(CORE_PATHS.read_text(encoding="utf-8"))
    paths.update(json.loads((PLUGIN / "brain.module.json").read_text(encoding="utf-8"))["paths"])
    (ws / ".claude" / "paths.json").write_text(json.dumps(paths), encoding="utf-8")
    for t in json.loads((PLUGIN / "brain.module.json").read_text(encoding="utf-8"))["templates"]:
        dest = ws / t["to"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(PLUGIN / t["from"], dest)
    (ws / "system" / "run" / "payloads").mkdir(parents=True)
    return ws


def run(script: str, ws: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO / "lib"), "BRAIN_ROOT": str(ws)}
    proc = subprocess.run([sys.executable, str(SCRIPTS[script]), *args], cwd=ws, env=env,
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{script} exited {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
    return proc


def stage_payload(ws: Path, fixture: str, dest_name: str | None = None) -> str:
    """Copy a fixture into the workspace payload dir; returns the workspace-relative path."""
    rel = f"system/run/payloads/{dest_name or fixture}"
    shutil.copy(FIXTURES / fixture, ws / rel)
    return rel


def result(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout)


CHANNEL_FIXTURES = [
    ("proj-checkout-2026-11-03.json", "proj-checkout-2026-11-03.json"),
    ("partner-api-2026-11-04.json", None),
    ("product-team-2026-11-05.json", None),
    ("product-leads-2026-11-04.json", None),
]


def build_sample(ws: Path) -> None:
    """Run every formatter on the fictional fixtures; the output is the committed sample data."""
    for fixture, _ in CHANNEL_FIXTURES:
        run("channel", ws, "--payload", stage_payload(ws, fixture))
    run("flagged", ws, "--payload", stage_payload(ws, "flagged-2026-11-06.json"), "--date", "2026-11-06")
