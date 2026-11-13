#!/usr/bin/env python3
"""Regenerate examples/sample-workspace/raw/slack by running the formatters on the fixtures.

    python3 tests/brain-ingest-slack/generate_sample.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers  # noqa: E402

ws = helpers.make_workspace()
try:
    helpers.build_sample(ws)
    if helpers.SAMPLE_SLACK.exists():
        shutil.rmtree(helpers.SAMPLE_SLACK)
    shutil.copytree(ws / "raw" / "slack", helpers.SAMPLE_SLACK)
    print(f"wrote {helpers.SAMPLE_SLACK}")
finally:
    shutil.rmtree(ws, ignore_errors=True)
