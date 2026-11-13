"""Tests for brain-grill: the skill is well-formed, the context gatherer reads only what it may, the holes payload
fits the entry grammar and refuses what it must."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wsutil  # noqa: E402

sys.path.insert(0, str(wsutil.REPO / "lib"))
from brainos import frontmatter  # noqa: E402

PLUGIN = wsutil.REPO / "plugins" / "brain-grill"
SKILL_DIR = PLUGIN / "skills" / "grill-me"
SCRIPTS = SKILL_DIR / "scripts"
MODES = ["prd", "roadmap", "decision", "objectives", "exec-update"]

FAKE_BRAIN = """#!{py}
import json, sys
sql = sys.argv[3] if len(sys.argv) > 3 else ""
rows = []
if "from current_entries" in sql:
    rows = [
     {{"id": "RSK-001", "facet": "risks", "state": "open", "by": "human", "trust": None, "rag": None, "due": "2026-12-01", "date": "2026-10-20", "path": "projects/checkout-revamp/risks.md", "body": "Payment provider cut-over may slip past the holiday freeze."}},
     {{"id": "HYP-001", "facet": "hypotheses", "state": "open", "by": "ai", "trust": "low", "rag": None, "due": None, "date": "2026-11-02", "path": "projects/checkout-revamp/hypotheses.md", "body": "One-page checkout lifts conversion."}},
     {{"id": "RSK-777", "facet": "risks", "state": "open", "by": "human", "trust": None, "rag": None, "due": None, "date": "2026-11-02", "path": "growth/private.md", "body": "HIDDEN-CONFIDENTIAL-ENTRY"}},
    ]
elif "from decisions" in sql:
    rows = [{{"id": "DEC-checkout-revamp-001", "title": "Keep the legacy cart for partners", "status": "accepted", "by": "human", "trust": None, "date": "2026-10-05", "owner": "riley-chen", "path": "projects/checkout-revamp/decisions/001.md"}}]
elif "from project_members" in sql:
    rows = [{{"person": "sam-patel", "name": "Sam Patel", "role": "Engineering Manager", "project_role": "engineering lead", "is_owner": 0, "is_decision_maker": 0}}]
elif "from raw_items" in sql:
    rows = [{{"id": "mtg-2026-11-03-checkout-sync", "date": "2026-11-03", "title": "Checkout sync", "meeting_type": "sync", "path": "raw/meetings/2026/2026-W45/x.md", "redact_content": 0}},
            {{"id": "mtg-2026-11-04-leads", "date": "2026-11-04", "title": "SECRET-LEADS-MEETING", "meeting_type": "sync", "path": "raw/meetings/2026/2026-W45/y.md", "redact_content": 1}}]
for r in rows:
    print(json.dumps(r))
"""


def install_fake_brain(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    exe = directory / "brain"
    exe.write_text(FAKE_BRAIN.format(py=sys.executable), encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return {"PATH": f"{directory}{os.pathsep}{os.environ['PATH']}"}


class Structure(unittest.TestCase):
    def test_plugin_manifest(self):
        meta = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["name"], meta["version"], meta["license"]), ("brain-grill", "0.1.0", "MIT"))
        self.assertEqual(meta["dependencies"], ["brain-core"])
        mod = json.loads((PLUGIN / "brain.module.json").read_text(encoding="utf-8"))
        self.assertEqual(mod["module"], "brain-grill")

    def test_skill_frontmatter_and_modes(self):
        fm = frontmatter.parse((SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(fm["name"], "grill-me")
        self.assertTrue(len(str(fm["description"])) > 60)
        self.assertIn("Bash(brain *)", fm["allowed-tools"])
        body = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for mode in MODES:
            ref = SKILL_DIR / "references" / f"{mode}.md"
            self.assertTrue(ref.is_file(), mode)
            self.assertIn(f"references/{mode}.md", body)
            text = ref.read_text(encoding="utf-8")
            self.assertIn("## Branches to walk", text)
            self.assertIn("## Where holes go", text)
        self.assertIn("One question at a time", body)

    def test_attribution_present(self):
        for f in (PLUGIN / "ATTRIBUTION.md", PLUGIN / "README.md"):
            text = f.read_text(encoding="utf-8")
            self.assertIn("Matt Pocock", text)
            self.assertIn("MIT", text)


class Scripts(unittest.TestCase):
    def setUp(self):
        self.ws = wsutil.make_workspace("brain-grill")
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        (self.ws / "projects" / "checkout-revamp").mkdir(parents=True, exist_ok=True)
        (self.ws / "projects" / "checkout-revamp" / "README.md").write_text("# Checkout revamp\n", encoding="utf-8")
        self.env = install_fake_brain(self.ws / "_bin")

    def run_s(self, name, args, env=None):
        return wsutil.run(SCRIPTS / name, args, self.ws, env=env if env is not None else self.env)

    def test_context_briefing_skips_confidential_rows(self):
        rc, out, _, err = self.run_s("gather_context.py", ["--project", "checkout-revamp"])
        self.assertEqual(rc, 0, out or err)
        self.assertEqual(out["counts"], {"entries": 2, "decisions": 1, "members": 1, "meetings": 1})
        text = (self.ws / out["outputs"][0]).read_text(encoding="utf-8")
        for expected in ("RSK-001", "HYP-001", "DEC-checkout-revamp-001", "Sam Patel", "Checkout sync"):
            self.assertIn(expected, text)
        for hidden in ("HIDDEN-CONFIDENTIAL-ENTRY", "SECRET-LEADS-MEETING"):
            self.assertNotIn(hidden, text)

    def test_context_fails_cleanly(self):
        rc, out, _, _ = self.run_s("gather_context.py", ["--project", "no-such-project"])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        rc, out, _, _ = self.run_s("gather_context.py", ["--project", "Bad Slug; drop"])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        rc, out, _, _ = self.run_s("gather_context.py", ["--project", "checkout-revamp"], env={"PATH": "/nonexistent"})
        self.assertEqual((rc, out["status"]), (1, "failed"))
        self.assertIn("brain", out["reason"])

    def test_confidential_project_is_refused(self):
        (self.ws / "projects" / "private-bet").mkdir()
        (self.ws / "projects" / "private-bet" / "README.md").write_text("---\nsensitivity: confidential\n---\n# x\n", encoding="utf-8")
        cfg_path = self.ws / ".claude" / "brain.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["confidential"]["globs"] = ["growth/**", "projects/private-bet/**"]
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        rc, out, _, _ = self.run_s("gather_context.py", ["--project", "private-bet"])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        self.assertIn("confidential", out["reason"])

    def hole(self, **kw):
        base = {"facet": "risks", "severity": "major", "kind": "unowned", "title": "No owner for partner migration",
                "body": "The draft moves partners to the new cart but no one is named. Name an owner and a date.",
                "refs": ["checkout-revamp/RSK-001"], "owner": "sam-patel", "due": "2026-12-01"}
        base.update(kw)
        return base

    def write_payload(self, **kw):
        p = {"project": "checkout-revamp", "mode": "decision", "session_date": "2026-11-12", "holes": [self.hole()]}
        p.update(kw)
        f = self.ws / "system" / "run" / "payloads" / "grill-test.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(p), encoding="utf-8")
        return f

    def test_holes_payload_normalises_to_entry_grammar(self):
        f = self.write_payload(holes=[self.hole(), self.hole(facet="hypotheses", kind="assumption", severity="blocker",
                                                             title="One-page checkout lifts conversion", owner=None, due=None)])
        out_path = self.ws / "system" / "run" / "payloads" / "grill-test.entries.json"
        rc, out, _, err = self.run_s("holes_payload.py", ["--payload", str(f), "--normalize", str(out_path)])
        self.assertEqual(rc, 0, out or err)
        norm = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(norm["project"], "checkout-revamp")
        for e in norm["entries"]:
            self.assertEqual((e["state"], e["by"], e["trust"]), ("proposed", "ai", "low"))
            self.assertEqual(e["source"], "grill:decision:2026-11-12")
        self.assertEqual([e["id_prefix"] for e in norm["entries"]], ["RSK", "HYP"])
        header = re.compile(r"^## \d{4}-\d{2}-\d{2} · (RSK|HYP)-NNN · proposed$", re.M)
        self.assertEqual(len(header.findall(out["preview"])), 2)
        self.assertIn("by: ai · trust: low · source: grill:decision:2026-11-12", out["preview"])

    def test_holes_payload_refusals(self):
        cases = [
            ({"mode": "objectives"}, "confidential"),
            ({"project": "ghost-project"}, "no project folder"),
            ({"holes": []}, "non-empty"),
            ({"holes": [self.hole(facet="status")]}, "facet"),
            ({"holes": [self.hole(body="fine\n## 2026-01-01 · RSK-001 · closed")]}, "entry parser"),
            ({"holes": [self.hole(refs=["not a ref"])]}, "ref"),
            ({"holes": [self.hole(title="x" * 101)]}, "title"),
            ({"holes": [self.hole() for _ in range(13)]}, "at most"),
            ({"session_date": "12/11/2026"}, "session_date"),
        ]
        for override, needle in cases:
            f = self.write_payload(**override)
            rc, out, _, _ = self.run_s("holes_payload.py", ["--payload", str(f)])
            self.assertEqual((rc, out["status"]), (1, "failed"), override)
            self.assertTrue(any(needle in e for e in out["errors"]), (override, out["errors"]))


if __name__ == "__main__":
    unittest.main()
