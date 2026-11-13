#!/usr/bin/env python3
"""brain-core tests against a temp copy of examples/sample-workspace.

    python3 -m unittest discover -s tests/brain-core -v
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "brain-core"
BRAIN = PLUGIN / "bin" / "brain"
SETUP = PLUGIN / "skills" / "setup" / "scripts" / "setup_workspace.py"
HOOK = PLUGIN / "hooks" / "brain_hook.py"
SAMPLE = REPO / "examples" / "sample-workspace"

ANSWERS = {
    "owner": {"name": "Alex Morgan", "first_name": "Alex", "person_id": "alex-morgan", "role": "Senior Product Manager",
              "company": "Fernhill", "timezone": "Europe/London", "week_starts": "monday"},
    "modules": ["brain-ingest", "brain-ingest-slack", "brain-ingest-notes"],
    "confidential": {"globs": ["growth/**"], "channel_patterns": ["*-leads", "*-exec*"]},
    "today": "2026-10-19",
}


def snapshot(base: Path) -> dict:
    if not base.exists():
        return {}
    return {str(p.relative_to(base)): (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir")
            for p in sorted(base.rglob("*"))}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="braincore-test-"))
        self.ws = self.tmp / "ws"
        shutil.copytree(SAMPLE, self.ws, ignore=shutil.ignore_patterns("kb.db", "__pycache__"))
        self.env = {k: v for k, v in os.environ.items() if k != "BRAIN_ROOT"}
        self.env["PYTHONPATH"] = str(REPO / "lib")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brain(self, *args, cwd=None, env=None, check=True):
        r = subprocess.run([sys.executable, str(BRAIN), *args], cwd=cwd or self.ws, env=env or self.env,
                           capture_output=True, text=True)
        if check:
            self.assertEqual(r.returncode, 0, f"brain {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
        return r

    def js(self, *args, **kw):
        out = self.brain(*args, **kw).stdout
        return json.loads(out[out.index("{"):]) if "{" in out else None

    def setup_ws(self, mode, target, answers=None, check=True):
        a = self.tmp / "answers.json"
        a.write_text(json.dumps(answers or ANSWERS))
        r = subprocess.run([sys.executable, str(SETUP), f"--{mode}", "--answers", str(a), "--target", str(target)],
                           capture_output=True, text=True, env=self.env)
        if check:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)


class RootResolution(Base):
    def test_brain_root_env(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        out = self.brain("root", cwd=elsewhere, env={**self.env, "BRAIN_ROOT": str(self.ws)}).stdout.strip()
        self.assertEqual(Path(out), self.ws.resolve())

    def test_cwd_walk_up(self):
        out = self.brain("root", cwd=self.ws / "projects" / "checkout-revamp").stdout.strip()
        self.assertEqual(Path(out), self.ws.resolve())

    def test_outside_fails_loudly(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        r = self.brain("root", cwd=elsewhere, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("No claude-second-brain-os workspace", r.stderr)

    def test_bad_brain_root(self):
        r = self.brain("root", env={**self.env, "BRAIN_ROOT": str(self.tmp)}, check=False)
        self.assertNotEqual(r.returncode, 0)


class Setup(Base):
    def test_plan_writes_nothing(self):
        fresh = self.tmp / "fresh"
        plan = self.setup_ws("plan", fresh)
        self.assertEqual(plan["status"], "planned")
        self.assertFalse(fresh.exists())
        self.assertGreater(plan["counts"]["write"], 10)
        before = snapshot(self.ws)
        self.setup_ws("plan", self.ws)
        self.assertEqual(before, snapshot(self.ws))

    def test_apply_never_overwrites_and_is_idempotent(self):
        target = self.tmp / "target"
        (target / ".claude").mkdir(parents=True)
        sentinel = "SENTINEL: my own soul file\n"
        (target / "SOUL.md").write_text(sentinel)
        (target / ".claude" / "paths.json").write_text(json.dumps({"core": {"projects": "work/projects"}, "mine": {"x": "y"}}))
        res = self.setup_ws("apply", target)
        self.assertEqual(res["status"], "applied")
        self.assertEqual((target / "SOUL.md").read_text(), sentinel)
        paths = json.loads((target / ".claude" / "paths.json").read_text())
        self.assertEqual(paths["core"]["projects"], "work/projects")  # owner's value kept
        self.assertEqual(paths["mine"], {"x": "y"})
        self.assertIn("slack", paths)  # module section added
        cfg = json.loads((target / ".claude" / "brain.json").read_text())
        self.assertEqual(cfg["owner"]["person_id"], "alex-morgan")
        self.assertIn("brain-ingest-slack", cfg["modules"])
        self.assertTrue((target / "system" / "schema" / "kb.sql").is_file())
        pipe = json.loads((target / "system" / "run" / "pipeline.json").read_text())
        bricks = [s["brick"] for st in pipe["stages"] for s in [*sum((st.get("lanes") or {}).values(), []), *st.get("steps", [])]]
        self.assertIn("brain-core:kb-build", bricks)
        self.assertIn("brain-ingest-slack:ingest-slack-channels", bricks)
        self.assertNotIn("{{", (target / "CRITICAL_FACTS.md").read_text())
        before = snapshot(target)
        again = self.setup_ws("apply", target)
        self.assertEqual(again["written"], [])
        self.assertEqual(before, snapshot(target))

    def test_defaults_survive_and_drift_is_clean_after_setup(self):
        target = self.tmp / "target"
        self.setup_ws("apply", target)
        cfg = json.loads((target / ".claude" / "brain.json").read_text())
        for pat in ("*-leadership*", "*-leads", "*-lead-*", "*-exec*", "exec-*", "leads-*"):
            self.assertIn(pat, cfg["confidential"]["channel_patterns"])
        self.assertIn("brain-wiki", cfg["modules_declined"])
        sys.path.insert(0, str(PLUGIN / "hooks"))
        import brain_hook
        self.assertEqual(brain_hook.config_drift(target), [])

    def test_collision_aborts_before_writing(self):
        target = self.tmp / "target"
        (target / ".claude").mkdir(parents=True)
        (target / ".claude" / "paths.json").write_text(json.dumps({"slack": {"raw": "somewhere/else"}}))
        before = snapshot(target)
        res = self.setup_ws("apply", target, check=False)
        self.assertEqual(res["status"], "error")
        self.assertTrue(res["collisions"])
        self.assertEqual(before, snapshot(target))

    def test_bad_answers(self):
        bad = {**ANSWERS, "owner": {**ANSWERS["owner"], "person_id": "Alex", "timezone": "Mars/Base"}}
        res = self.setup_ws("plan", self.tmp / "x", answers=bad, check=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(len(res["problems"]), 2)


class KnowledgeBase(Base):
    def test_sample_builds_with_zero_errors(self):
        out = self.js("kb", "build")
        self.assertEqual(out["status"], "built")
        self.assertGreater(out["counts"]["entries"], 20)
        n = json.loads(self.brain("kb", "query", "select count(*) n from entries where source is null or source=''").stdout)["n"]
        self.assertEqual(n, 0)
        self.assertEqual(self.js("kb", "build")["status"], "unchanged")
        att = self.js("kb", "attention", "--today", "2026-11-13")
        self.assertGreaterEqual(att["counts"]["overdue-open-items"], 1)
        self.assertIn("checkout-revamp/RSK-002", self.brain("kb", "show", "checkout-revamp/RSK-002").stdout)

    def test_invalid_entry_fails_and_writes_nothing(self):
        with (self.ws / "projects/partner-api/risks.md").open("a") as fh:
            fh.write("\n## 2026-11-13 · RSK-009 · open\nby: ai · trust: high\nno source\n")
        r = self.brain("kb", "build", check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("source is mandatory", r.stderr)
        self.assertFalse((self.ws / "system/kb.db").exists())

    def test_append_validates_then_assigns_ids(self):
        risks = self.ws / "projects/checkout-revamp/risks.md"
        before = risks.read_text()
        payload = self.ws / "system/run/payloads/p.json"
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_text(json.dumps({"project": "checkout-revamp", "entries": [
            {"id_prefix": "RSK", "status": "open", "by": "ai", "source": "mtg-2026-11-04-checkout-weekly", "body": "New."},
            {"id_prefix": "RSK", "status": "open", "by": "ai", "body": "No source."}]}))
        self.assertEqual(self.brain("kb", "append", "--project", "checkout-revamp", "--file", str(payload), check=False).returncode, 1)
        self.assertEqual(risks.read_text(), before)
        payload.write_text(json.dumps({"project": "checkout-revamp", "entries": [
            {"id_prefix": "RSK", "status": "open", "by": "ai", "source": "mtg-2026-11-04-checkout-weekly", "body": "New."},
            {"id_prefix": "DEC", "title": "Use the hosted tax service", "by": "ai", "source": "slack-2026-11-03-proj-checkout",
             "body": "Use the hosted tax service."},
            {"id_prefix": "RSK", "id": "RSK-002", "status": "closed", "by": "ai", "source": "slack-2026-11-03-proj-checkout",
             "body": "Sandbox stable for a week."}]}))
        out = self.js("kb", "append", "--project", "checkout-revamp", "--file", str(payload))
        ids = [x["id"] for x in out["ids"]]
        self.assertEqual(ids, ["RSK-003", "DEC-checkout-revamp-003", "RSK-002"])
        self.assertTrue(risks.read_text().startswith(before))  # append-only
        self.js("kb", "build")
        d = json.loads(self.brain("kb", "query", "select status, trust from decisions where id='DEC-checkout-revamp-003'").stdout)
        self.assertEqual((d["status"], d["trust"]), ("proposed", "medium"))  # Slack never auto-confirms

    def test_owner_source_never_auto_confirms_ai_decision(self):
        payload = self.ws / "p.json"
        payload.write_text(json.dumps({"entries": [
            {"id_prefix": "DEC", "title": "AI says go", "by": "ai", "source": "owner", "body": "Go."},
            {"id_prefix": "DEC", "title": "Owner says go", "by": "human", "source": "owner", "body": "Go."}]}))
        out = self.js("kb", "append", "--project", "partner-api", "--file", str(payload))
        self.assertEqual([x["status"] for x in out["ids"]], ["proposed", "accepted"])
        self.assertEqual(self.js("kb", "build")["status"], "built")

    def test_confidential_source_is_tagged(self):
        payload = self.ws / "p.json"
        payload.write_text(json.dumps({"entries": [{"id_prefix": "RSK", "status": "open", "source": "slack-2026-11-04-product-leads",
                                                    "body": "Leadership flagged sequencing."}]}))
        self.js("kb", "append", "--project", "partner-api", "--file", str(payload))
        self.assertIn("sensitivity: confidential", (self.ws / "projects/partner-api/risks.md").read_text())

    def test_propose_and_confirm(self):
        out = self.js("kb", "propose", "--audience", "owner", "--title", "Try it", "--source", "owner", "--body", "Body.")
        self.js("kb", "build")
        self.js("kb", "confirm", out["id"], "--reject")
        self.js("kb", "build")
        self.js("kb", "confirm", "DEC-checkout-revamp-002")
        self.js("kb", "build")
        d = json.loads(self.brain("kb", "query", "select status, by from decisions where id='DEC-checkout-revamp-002'").stdout)
        self.assertEqual((d["status"], d["by"]), ("accepted", "ai-confirmed"))

    def test_new_project_builds(self):
        self.js("new", "project", "billing-portal")
        self.assertTrue((self.ws / "projects/billing-portal/risks.md").is_file())
        self.assertNotEqual(self.brain("new", "project", "billing-portal", check=False).returncode, 0)
        self.js("new", "person", "pat-quinn")
        self.assertEqual(self.js("kb", "build")["status"], "built")


class PendingQueue(Base):
    def test_pending_flag_round_trip(self):
        pend = self.js("pending", "--flag", "wiki_processed")
        self.assertGreater(pend["count"], 0)
        first = pend["items"][0]["path"]
        self.js("flag", "--set", "wiki_processed=true", "--file", first)
        after = self.js("pending", "--flag", "wiki_processed")
        self.assertNotIn(first, [i["path"] for i in after["items"]])
        self.assertEqual(after["count"], pend["count"] - 1)
        rest = [i["path"] for i in after["items"]][:2]
        payload = self.ws / "system/run/payloads/flags.json"
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_text(json.dumps({"files": rest}))
        self.js("flag", "--set", "wiki_processed=true", "--files-from", str(payload))
        self.assertFalse(payload.exists())  # consumed
        self.assertEqual(self.js("pending")["count"], pend["count"] - 1 - len(rest))
        self.js("flag", "--set", "wiki_processed=false", "--file", first)
        self.assertIn(first, [i["path"] for i in self.js("pending")["items"]])


class RunState(Base):
    def write_pipeline(self):
        p = self.ws / "system/run/pipeline.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"settings": {"max_catchup_days": 5}, "stages": [
            {"id": "fetch", "lanes": {"slack": [{"brick": "brain-ingest-slack:ingest-slack-channels", "model": "haiku", "per_date": True}]}},
            {"id": "index", "steps": [{"brick": "brain-core:kb-build", "command": "brain kb build --as-brick brain-core:kb-build"}]},
            {"id": "derive", "parallel": True, "steps": [{"brick": "brain-wiki:wiki-update", "model": "sonnet", "enabled": False}]},
        ]}))

    def test_plan_and_finalise(self):
        self.write_pipeline()
        ctx = self.js("run", "plan", "--today", "2026-11-13", "--catch-up", "3")
        self.assertEqual(ctx["dates_to_process"], ["2026-11-11", "2026-11-12", "2026-11-13"])
        self.assertEqual(set(ctx["window"]["2026-11-13"]), {"start_iso", "end_iso", "oldest_ts", "latest_ts"})
        self.assertIn("flagged_after", ctx["slack"])
        steps = ctx["dispatch"][0]["lanes"]["slack"]
        self.assertEqual([s["target_date"] for s in steps], ctx["dates_to_process"])
        self.assertEqual(ctx["dispatch"][1]["steps"][0]["kind"], "script")
        self.assertEqual(len(ctx["dispatch"]), 2)  # disabled derive brick dropped
        returns = [{"brick": "brain-ingest-slack:ingest-slack-channels", "status": "success", "target_date": "2026-11-11", "counts": {"messages": 4}},
                   {"brick": "brain-ingest-slack:ingest-slack-channels", "status": "failed", "target_date": "2026-11-12", "counts": {}},
                   {"brick": "brain-ingest-slack:ingest-slack-channels", "status": "success", "target_date": "2026-11-13", "counts": {"messages": 2},
                    "observations": ["#partner-api got busy"]},
                   {"brick": "brain-core:kb-build", "status": "success", "counts": {}}]
        (self.ws / "system/run/returns.json").write_text(json.dumps(returns))
        out = self.brain("run", "finalise", "--returns", "system/run/returns.json").stdout
        res = json.loads(out[out.index("\n{") + 1:])
        self.assertEqual(res["status"], "partial")
        self.assertEqual(res["dates_partial"], ["2026-11-12"])
        self.assertFalse(res["observations_written"])
        log = json.loads((self.ws / "system/run/run-log.json").read_text())
        self.assertEqual(log["runs"][0]["bricks"]["brain-ingest-slack:ingest-slack-channels"]["counts"]["messages"], 6)
        nxt = self.js("run", "plan", "--today", "2026-11-14")
        self.assertIn("2026-11-12", nxt["dates_to_process"])  # partial date re-included
        capped = self.js("run", "plan", "--today", "2026-11-13", "--catch-up", "8")
        self.assertEqual(len(capped["dates_to_process"]), 5)
        self.assertEqual(capped["dates_dropped_by_cap"], ["2026-11-06", "2026-11-07", "2026-11-08"])

    def test_stale_module_root_fails_loudly(self):
        self.write_pipeline()
        p = self.ws / "system/run/pipeline.json"
        data = json.loads(p.read_text())
        data["modules"] = {"brain-ingest-notes": {"root": str(self.tmp / "gone"), "version": "0.1.0"}}
        p.write_text(json.dumps(data))
        r = self.brain("run", "plan", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("re-run /brain-core:setup to refresh module roots", r.stderr)


class Hooks(Base):
    def hook(self, event, payload):
        return subprocess.run([sys.executable, str(HOOK), event], input=json.dumps(payload), capture_output=True,
                              text=True, env={**self.env, "CLAUDE_PROJECT_DIR": ""})

    def test_silent_outside_workspace(self):
        out = self.tmp / "nowhere"
        out.mkdir()
        for ev in ("session-start", "user-prompt-submit", "post-tool-use", "pre-compact", "stop"):
            r = self.hook(ev, {"cwd": str(out), "session_id": "x"})
            self.assertEqual((r.returncode, r.stdout), (0, ""), ev)

    def test_tiered_session_start(self):
        haiku = self.hook("session-start", {"cwd": str(self.ws), "model": "claude-haiku", "session_id": "h1"}).stdout
        self.assertIn("CRITICAL FACTS", haiku)
        self.assertNotIn("----- RULES", haiku)
        full = self.hook("session-start", {"cwd": str(self.ws), "session_id": "o1"}).stdout
        self.assertIn("----- SOUL", full)
        self.assertIn("ANCHOR",
                      self.hook("user-prompt-submit", {"cwd": str(self.ws), "session_id": "h1"}).stdout)
        self.assertEqual(self.hook("user-prompt-submit", {"cwd": str(self.ws), "session_id": "o1"}).stdout, "")

    def test_post_tool_use_flags_bad_entry(self):
        f = self.ws / "projects/partner-api/milestones.md"
        with f.open("a") as fh:
            fh.write("\n## 2026-11-13 · MS-003 · nope\nby: ai\nx\n")
        out = self.hook("post-tool-use", {"cwd": str(self.ws), "tool_name": "Edit", "tool_input": {"file_path": str(f)}}).stdout
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("entry-grammar", ctx)


if __name__ == "__main__":
    unittest.main()
