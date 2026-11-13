"""Tests for brain-steal-list: init, sync (optional), record (validate-first), digest, board, decide gates, setup map."""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wsutil  # noqa: E402

S = wsutil.REPO / "plugins" / "brain-steal-list" / "skills" / "steal" / "scripts"
SAMPLE_SOURCES = wsutil.REPO / "examples" / "sample-workspace" / "steal" / "sources"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")


def sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


class StealBase(unittest.TestCase):
    def setUp(self):
        self.ws = wsutil.make_workspace("brain-steal-list")
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        (self.ws / "steal" / "sources").mkdir(parents=True, exist_ok=True)
        for f in SAMPLE_SOURCES.glob("*.md"):
            shutil.copy(f, self.ws / "steal" / "sources" / f.name)
        cfg = self.ws / ".claude" / "brain"
        cfg.mkdir(parents=True, exist_ok=True)
        shutil.copy(wsutil.REPO / "plugins/brain-steal-list/templates/steal.json", cfg / "steal.json")

    def run_s(self, name, args=(), **kw):
        return wsutil.run(S / name, list(args), self.ws, **kw)

    def db(self):
        con = sqlite3.connect(self.ws / "steal" / "steal.db")
        con.row_factory = sqlite3.Row
        return con

    def png(self, name="shot-1.png", extra=b""):
        p = self.ws / "steal" / "inbox" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(PNG + extra)
        return p

    def item(self, src: Path, **kw):
        base = {"source_file": str(src), "sha256": sha(src), "seq": 0, "platform": "example-social",
                "author_handle": "@maya.example", "title": "Decision log instead of prose summaries",
                "summary": "Append one line per decision to a project log.", "claims": ["halves prep time"],
                "named_tools": ["skill pack"], "topics": ["meetings"], "verdict": "adapt", "targets": ["wiki"],
                "why": "Close to how decisions are logged already, but ours has owner and trust fields.",
                "how": "Extend the meeting summary skill to emit log entries; first step: add a decisions section.",
                "effort": "S", "novelty": "med", "evidence": "thin", "confidence": "med",
                "pov": "Good idea, small gap. The prep-time claim is unshown."}
        base.update(kw)
        return base

    def payload(self, items, run_id="2026-11-12-2200", **kw):
        p = self.ws / "system" / "run" / "payloads" / f"steal-{run_id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"run_id": run_id, "batch_pov": "- decision logs keep recurring", "items": items, **kw}),
                     encoding="utf-8")
        return p

    def review_one_run(self):
        self.run_s("init_db.py")
        shot = self.png()
        srcs = sorted((self.ws / "steal" / "sources").glob("*.md"))
        items = [
            self.item(shot, title="Folder layout for a prompt library", verdict="watch", targets=[], how="",
                      effort=None, source_url=None),
            self.item(srcs[0], source_url="https://posts.example/maya-ortega-example/meeting-notes-skill-pack"),
            self.item(srcs[2], title="Self-rewriting instructions", verdict="skip", targets=[], how="", effort=None,
                      evidence="hype", why="No log, no diff, no review step.", pov="Hype. A bad idea without review.",
                      source_url="https://posts.example/ines-cole-example/self-rewriting-agent"),
        ]
        rc, out, _, err = self.run_s("record.py", ["--payload", str(self.payload(items))])
        self.assertEqual(rc, 0, out or err)
        return out


class Init(StealBase):
    def test_init_is_idempotent_and_creates_schema(self):
        rc, out, _, _ = self.run_s("init_db.py")
        self.assertEqual(rc, 0)
        self.assertTrue({"items", "decisions", "decision_log", "runs"} <= set(out["tables"]))
        self.assertIn("verdicts", out["tables"])
        self.assertFalse(out["drive_sync_configured"])
        rc2, out2, _, _ = self.run_s("init_db.py")
        self.assertEqual((rc2, out2["tables"]), (0, out["tables"]))


class Sync(StealBase):
    def test_sync_is_skipped_when_unconfigured(self):
        rc, out, _, _ = self.run_s("sync_drive_inbox.py")
        self.assertEqual((rc, out["status"]), (0, "skipped"))

    def test_sync_moves_verified_copies_when_configured(self):
        drop = self.ws / "_phone"
        drop.mkdir()
        (drop / "a.png").write_bytes(PNG)
        (drop / "notes.txt").write_text("not an image", encoding="utf-8")
        cfg = self.ws / ".claude" / "brain" / "steal.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["drive_inbox"] = str(drop)
        cfg.write_text(json.dumps(data), encoding="utf-8")
        rc, out, _, err = self.run_s("sync_drive_inbox.py")
        self.assertEqual((rc, out["counts"]["moved"]), (0, 1), err)
        self.assertTrue((self.ws / "steal" / "inbox" / "a.png").is_file())
        self.assertFalse((drop / "a.png").exists())
        self.assertTrue((drop / "notes.txt").exists())

    def test_sync_reports_missing_folder_as_failure(self):
        cfg = self.ws / ".claude" / "brain" / "steal.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["drive_inbox"] = str(self.ws / "does-not-exist")
        cfg.write_text(json.dumps(data), encoding="utf-8")
        rc, out, _, _ = self.run_s("sync_drive_inbox.py")
        self.assertEqual((rc, out["status"]), (1, "failed"))


class Review(StealBase):
    def test_record_digest_board_and_archive(self):
        out = self.review_one_run()
        self.assertEqual(out["inserted"], 3)
        con = self.db()
        self.assertEqual(con.execute("SELECT COUNT(*) FROM items").fetchone()[0], 3)
        statuses = {r["title"]: r["status"] for r in con.execute(
            "SELECT i.title, d.status FROM items i JOIN decisions d ON d.item_id=i.id")}
        self.assertEqual(statuses["Self-rewriting instructions"], "skipped")
        self.assertEqual(statuses["Decision log instead of prose summaries"], "proposed")
        # the screenshot moved to _processed, the text source stayed where it was
        self.assertFalse((self.ws / "steal/inbox/shot-1.png").exists())
        self.assertEqual(len(list((self.ws / "steal/inbox/_processed").rglob("shot-1.png"))), 1)
        self.assertEqual(len(list((self.ws / "steal/sources").glob("*.md"))), 3)

        rc, dg, _, _ = self.run_s("build_digest.py", ["--run-id", "2026-11-12-2200"])
        self.assertEqual((rc, dg["counts"]), (0, {"steal": 0, "adapt": 1, "watch": 1, "skip": 1}))
        digest = (self.ws / dg["digest"]).read_text(encoding="utf-8")
        self.assertIn("/brain-steal-list:steal adopt", digest)
        self.assertIn("decision logs keep recurring", digest)
        self.assertNotIn("python3 system", digest)

        rc, board, _, _ = self.run_s("build_board.py")
        self.assertEqual((rc, board["items"], board["board"]), (0, 3, "steal/board.md"))
        md = (self.ws / board["board"]).read_text(encoding="utf-8")
        self.assertIn("## New (2)", md)
        self.assertIn("## Skipped (1)", md)
        self.assertIn("`/brain-steal-list:steal adopt ", md)
        self.assertIn("Self-rewriting instructions", md)
        self.assertNotIn("<", md.replace("<br>", ""))

    def test_validation_failure_writes_nothing_and_leaves_inbox(self):
        self.run_s("init_db.py")
        shot = self.png()
        bad = self.item(shot, how="", targets=[], effort=None)  # adapt without how/target/effort
        worse = self.item(shot, seq=0, verdict="maybe")
        rc, out, _, _ = self.run_s("record.py", ["--payload", str(self.payload([bad, worse]))])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        self.assertTrue(any("concrete 'how'" in e for e in out["errors"]))
        self.assertTrue(any("verdict must be" in e for e in out["errors"]))
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        self.assertTrue(shot.exists())

    def test_unknown_target_and_empty_payload_are_rejected(self):
        self.run_s("init_db.py")
        shot = self.png()
        rc, out, _, _ = self.run_s("record.py", ["--payload", str(self.payload([self.item(shot, targets=["gardening"])]))])
        self.assertEqual(rc, 1)
        self.assertTrue(any("unknown targets" in e for e in out["errors"]))
        rc, out, _, _ = self.run_s("record.py", ["--payload", str(self.payload([], run_id="2026-11-12-2300"))])
        self.assertEqual(rc, 1)

    def test_duplicates_are_listed_and_source_url_dedupes(self):
        self.review_one_run()
        self.png("shot-copy.png")  # same bytes as the reviewed screenshot
        rc, out, _, _ = self.run_s("list_inbox.py")
        self.assertEqual((out["counts"]["new"], out["counts"]["dupes"]), (0, 1))
        src = sorted((self.ws / "steal/sources").glob("*.md"))[0]
        again = self.item(src, seq=7, source_url="https://posts.example/maya-ortega-example/meeting-notes-skill-pack")
        rc, rec, _, _ = self.run_s("record.py", ["--payload", str(self.payload([again], run_id="2026-11-13-2200"))])
        self.assertEqual((rec["inserted"], rec["dupes"]), (0, 1))

    def test_purge_only_deletes_recorded_images_past_the_age(self):
        self.review_one_run()
        processed = next((self.ws / "steal/inbox/_processed").rglob("shot-1.png"))
        stray = processed.parent / "never-recorded.png"
        stray.write_bytes(PNG + b"stray")
        old = time.time() - 40 * 86400
        for p in (processed, stray):
            os.utime(p, (old, old))
        rc, out, _, _ = self.run_s("purge_processed.py")
        self.assertEqual((rc, out["deleted"]), (0, 1))
        self.assertFalse(processed.exists())
        self.assertTrue(stray.exists())
        self.assertEqual(len(out["kept_unrecorded"]), 1)


class Decide(StealBase):
    def test_gate_order_and_plan_scaffold(self):
        self.review_one_run()
        adapt_id = self.db().execute("SELECT item_id FROM verdicts WHERE verdict='adapt'").fetchone()[0]
        i = str(adapt_id)
        rc, out, _, _ = self.run_s("decide.py", ["--id", i, "--status", "plan_approved"])
        self.assertEqual((rc, out["status"]), (1, "failed"))  # cannot jump the gate
        self.assertEqual(self.run_s("decide.py", ["--id", i, "--status", "adopted", "--note", "worth a try"])[0], 0)
        rc, out, _, _ = self.run_s("decide.py", ["--id", i, "--status", "plan_drafted", "--plan", "plans/none.md"])
        self.assertEqual(rc, 1)  # plan file must exist
        rc, plan, _, _ = self.run_s("new_plan.py", ["--id", i])
        self.assertEqual(rc, 0)
        self.assertIn("Not approved", (self.ws / plan["path"]).read_text(encoding="utf-8"))
        self.assertEqual(self.run_s("new_plan.py", ["--id", i])[0], 1)  # never overwrites
        rel_plan = plan["plan"]
        self.assertEqual(self.run_s("decide.py", ["--id", i, "--status", "plan_drafted", "--plan", rel_plan])[0], 0)
        self.assertEqual(self.run_s("decide.py", ["--id", i, "--status", "plan_approved"])[0], 0)
        self.assertEqual(self.run_s("decide.py", ["--id", i, "--status", "done"])[0], 1)  # needs --link
        self.assertEqual(self.run_s("decide.py", ["--id", i, "--status", "done", "--link", "skills/meeting-log"])[0], 0)
        log = [r[0] for r in self.db().execute("SELECT status FROM decision_log WHERE item_id=? ORDER BY id", (adapt_id,))]
        self.assertEqual(log, ["proposed", "adopted", "plan_drafted", "plan_approved", "done"])

    def test_plan_requires_adopted(self):
        self.review_one_run()
        any_id = self.db().execute("SELECT item_id FROM verdicts WHERE verdict='watch'").fetchone()[0]
        rc, out, _, _ = self.run_s("new_plan.py", ["--id", str(any_id)])
        self.assertEqual(rc, 1)


class MySetup(StealBase):
    def test_map_is_generated_from_the_workspace_and_skips_confidential(self):
        skills = self.ws / ".claude" / "skills"
        (skills / "weekly-digest").mkdir(parents=True)
        (skills / "weekly-digest" / "SKILL.md").write_text(
            "---\nname: weekly-digest\ndescription: Builds the weekly digest from project logs.\n---\nbody\n", encoding="utf-8")
        (skills / "private-review").mkdir()
        (skills / "private-review" / "SKILL.md").write_text(
            "---\nname: private-review\ndescription: SECRET-DESC\nsensitivity: confidential\n---\n", encoding="utf-8")
        (self.ws / "RULES.md").write_text("# Rules\n\n## Digests stay short\n\n## Never publish without a yes\n", encoding="utf-8")
        (self.ws / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        (self.ws / ".claude" / "agents" / "prd-writer.md").write_text("---\nname: prd-writer\ndescription: Drafts PRDs.\n---\n", encoding="utf-8")
        cfg_path = self.ws / ".claude" / "brain.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["modules"] = ["brain-core", "brain-steal-list"]
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        rc, out, _, err = self.run_s("build_my_setup.py", ["--today", "2026-11-12"])
        self.assertEqual(rc, 0, err)
        text = (self.ws / out["my_setup"]).read_text(encoding="utf-8")
        for expected in ("generated: true", "- brain-steal-list", "- Digests stay short",
                         "**weekly-digest**: Builds the weekly digest", "**prd-writer**: Drafts PRDs."):
            self.assertIn(expected, text)
        self.assertNotIn("SECRET-DESC", text)
        self.assertNotIn("private-review", text)
        self.assertEqual(out["counts"]["skills"], 1)
        before = text
        self.run_s("build_my_setup.py", ["--today", "2026-11-12"])
        self.assertEqual((self.ws / out["my_setup"]).read_text(encoding="utf-8"), before)  # deterministic


if __name__ == "__main__":
    unittest.main()
