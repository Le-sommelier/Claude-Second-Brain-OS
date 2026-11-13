"""Tests for brain-learning-loop: transcript extraction, session records, the ledger and the weekly review."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wsutil  # noqa: E402

PLUGIN = wsutil.REPO / "plugins" / "brain-learning-loop" / "skills"
CONSOLIDATE = PLUGIN / "consolidate" / "scripts"
REVIEW = PLUGIN / "system-review" / "scripts"
FIX = Path(__file__).resolve().parent / "fixtures"
OLD = time.time() - 3600  # an hour ago: past the live-session guard


def install_transcripts(ws: Path) -> Path:
    tdir = ws / "_transcripts"
    tdir.mkdir()
    for name, sid in (("session-routine", "11111111-aaaa-4bbb-8ccc-000000000001"),
                      ("session-confidential", "22222222-aaaa-4bbb-8ccc-000000000002"),
                      ("session-toolonly", "33333333-aaaa-4bbb-8ccc-000000000003")):
        text = (FIX / f"{name}.jsonl.tmpl").read_text(encoding="utf-8").replace("{{ROOT}}", str(ws))
        f = tdir / f"{sid}.jsonl"
        f.write_text(text, encoding="utf-8")
        os.utime(f, (OLD, OLD))
    return tdir


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = wsutil.make_workspace("brain-learning-loop")
        cfg_path = self.ws / ".claude" / "brain.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["learning"] = {"noise_markers": ["SESSION-BOOTSTRAP"]}
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def run_s(self, script, args, **kw):
        return wsutil.run(script, args, self.ws, **kw)


class ExtractSessions(Base):
    def test_digest_strips_noise_redacts_and_withholds_confidential(self):
        tdir = install_transcripts(self.ws)
        rc, out, _, err = self.run_s(CONSOLIDATE / "extract_sessions.py",
                                     ["--transcripts-dir", str(tdir), "--since", "2026-01-01T00:00:00Z"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["sessions"], 2)  # the tool-only session is dropped
        text = (self.ws / out["input_file"]).read_text(encoding="utf-8")
        self.assertIn("Cut it to three sentences", text)
        self.assertIn("Done: the intro is now three sentences.", text)
        for forbidden in ("TOOL OUTPUT MUST NOT SURVIVE", "private reasoning", "reminder text",
                          "SESSION-BOOTSTRAP", "hunter2", "CONFIDENTIAL-DETAIL", "review feedback from the growth"):
            self.assertNotIn(forbidden, text)
        self.assertIn("content withheld", text)

    def test_watermark_commit_and_skip_of_live_sessions(self):
        tdir = install_transcripts(self.ws)
        live = tdir / "44444444-aaaa-4bbb-8ccc-000000000004.jsonl"
        live.write_text('{"type":"user","message":{"role":"user","content":"still typing"}}\n', encoding="utf-8")
        _, out, _, _ = self.run_s(CONSOLIDATE / "extract_sessions.py",
                                  ["--transcripts-dir", str(tdir), "--since", "2026-01-01T00:00:00Z"])
        self.assertNotIn("44444444", out["session_ids"])
        rc, done, _, _ = self.run_s(CONSOLIDATE / "extract_sessions.py", ["--commit", out["proposed_watermark"]])
        self.assertEqual(rc, 0)
        wm = json.loads((self.ws / "system/learning/consolidate-watermark.json").read_text(encoding="utf-8"))
        self.assertEqual(wm["last_run_iso"], out["proposed_watermark"])
        # Second run without --since sees nothing new.
        _, again, _, _ = self.run_s(CONSOLIDATE / "extract_sessions.py", ["--transcripts-dir", str(tdir)])
        self.assertEqual(again["sessions"], 0)

    def test_bad_commit_value_and_missing_folder_fail_loudly(self):
        rc, out, _, _ = self.run_s(CONSOLIDATE / "extract_sessions.py", ["--commit", "yesterday-ish"])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        rc, out, _, _ = self.run_s(CONSOLIDATE / "extract_sessions.py", ["--transcripts-dir", str(self.ws / "nope")])
        self.assertEqual((rc, out["status"]), (1, "failed"))

    def test_default_transcript_folder_is_encoded_from_the_workspace_root(self):
        encoded = re.sub(r"[^A-Za-z0-9]", "-", str(self.ws.resolve()))
        home = self.ws / "_home" / ".claude" / "projects" / encoded
        home.mkdir(parents=True)
        f = home / "55555555-aaaa-4bbb-8ccc-000000000005.jsonl"
        f.write_text('{"type":"user","message":{"role":"user","content":"hello from home"}}\n', encoding="utf-8")
        os.utime(f, (OLD, OLD))
        rc, out, _, err = self.run_s(CONSOLIDATE / "extract_sessions.py", ["--since", "2026-01-01T00:00:00Z"])
        self.assertEqual((rc, out["sessions"]), (0, 1), err)


class SessionRecords(Base):
    def test_records_dedupe_and_redact(self):
        tdir = install_transcripts(self.ws)
        summ = self.ws / "summ.json"
        summ.write_text(json.dumps({"11111111": "Shortened the weekly digest intro"}), encoding="utf-8")
        args = ["--transcripts-dir", str(tdir), "--since", "2026-01-01T00:00:00Z", "--summaries", str(summ)]
        rc, out, _, err = self.run_s(CONSOLIDATE / "session_records.py", args)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["counts"]["new"], 2)
        self.assertEqual(out["counts"]["confidential"], 1)
        lines = [json.loads(x) for x in (self.ws / "system/sessions/2026/11.jsonl").read_text(encoding="utf-8").splitlines()]
        by_id = {r["id"][:8]: r for r in lines}
        self.assertEqual(by_id["11111111"]["summary"], "Shortened the weekly digest intro")
        self.assertEqual(by_id["11111111"]["files_touched"], ["digests/weekly/2026-W45.md"])
        self.assertEqual(by_id["22222222"]["files_touched"], [])
        self.assertIn("redacted", by_id["22222222"]["summary"])
        rc, again, _, _ = self.run_s(CONSOLIDATE / "session_records.py", args)
        self.assertEqual(again["counts"]["new"], 0)
        self.assertEqual(again["counts"]["already_recorded"], 2)

    def test_bad_summaries_file_writes_nothing(self):
        tdir = install_transcripts(self.ws)
        month = self.ws / "system/sessions/2026/11.jsonl"
        self.before = month.read_bytes() if month.exists() else b""
        bad = self.ws / "bad.json"
        bad.write_text("[1, 2]", encoding="utf-8")
        rc, out, _, _ = self.run_s(CONSOLIDATE / "session_records.py",
                                   ["--transcripts-dir", str(tdir), "--since", "2026-01-01T00:00:00Z", "--summaries", str(bad)])
        self.assertEqual((rc, out["status"]), (1, "failed"))
        month = self.ws / "system/sessions/2026/11.jsonl"
        self.assertEqual(month.read_bytes() if month.exists() else b"", self.before)


class Ledger(Base):
    def observe(self, observations, expect_rc=0):
        p = self.ws / "payload.json"
        p.write_text(json.dumps({"observations": observations}), encoding="utf-8")
        rc, out, _, err = self.run_s(CONSOLIDATE / "ledger.py", ["observe", "--payload", str(p)])
        self.assertEqual(rc, expect_rc, err)
        return out

    def obs(self, session, **kw):
        return {"kind": "pattern", "statement": "The owner shortens AI-drafted digest intros by hand",
                "session": session, "date": "2026-11-10", **kw}

    def test_distinct_sessions_drive_the_threshold(self):
        first = self.observe([self.obs("aaaa0001"), self.obs("aaaa0002")])
        self.assertEqual(first["counts"]["new_items"], 1)
        self.assertEqual(first["crossed"], [])
        again = self.observe([self.obs("aaaa0002")])  # same session again: no new evidence
        self.assertEqual(again["counts"]["duplicate_evidence"], 1)
        third = self.observe([self.obs("bbbb0003", date="2026-11-12")])
        self.assertEqual(third["crossed"], ["PAT-001"])
        listing = self.run_s(CONSOLIDATE / "ledger.py", ["list"])[1]["items"][0]
        self.assertEqual((listing["supports"], listing["last_seen"]), (3, "2026-11-12"))
        view = (self.ws / "system/learning/hypotheses.md").read_text(encoding="utf-8")
        self.assertIn("PAT-001", view)
        self.assertIn("generated: true", view)

    def test_hypothesis_ids_refutation_and_set_status(self):
        self.observe([{"kind": "hypothesis", "statement": "Drafts should be shorter", "session": "cccc0001",
                       "date": "2026-11-02"}])
        out = self.observe([{"id": "HYP-001", "session": "cccc0002", "date": "2026-11-05", "polarity": "refutes",
                             "note": "owner kept the long draft"}])
        self.assertEqual(out["counts"]["evidence_added"], 1)
        item = self.run_s(CONSOLIDATE / "ledger.py", ["list", "--status", "open"])[1]["items"][0]
        self.assertEqual((item["supports"], item["refutes"]), (1, 1))
        rc, done, _, _ = self.run_s(CONSOLIDATE / "ledger.py", ["set-status", "--id", "HYP-001", "--status", "rejected"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.run_s(CONSOLIDATE / "ledger.py", ["list", "--status", "open"])[1]["items"], [])

    def test_validation_failure_writes_nothing(self):
        out = self.observe([{"kind": "pattern", "statement": "ok", "session": "x", "date": "11/10/2026"}], expect_rc=1)
        self.assertEqual(out["status"], "failed")
        self.assertFalse((self.ws / "system/learning/ledger.json").exists())
        out = self.observe([{"id": "PAT-404", "session": "dddd0001", "date": "2026-11-10"}], expect_rc=1)
        self.assertEqual(out["unknown_ids"], ["PAT-404"])


class SystemReview(Base):
    def setUp(self):
        super().setUp()
        proj = self.ws / "projects" / "checkout-revamp"
        proj.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIX / "projects-facets.md", proj / "risks.md")
        (proj / "README.md").write_text("# Checkout revamp\n\nSee [[ghost-page]].\n", encoding="utf-8")
        (self.ws / "projects" / "skeleton-only").mkdir(parents=True, exist_ok=True)
        (self.ws / "MEMORY.md").write_text("# Memory\n\n## 2026-11-10 - digest intro length\n- x\n\n## 2026-09-01 - old\n- y\n",
                                           encoding="utf-8")
        growth = self.ws / "growth"
        growth.mkdir(exist_ok=True)
        (growth / "notes.md").write_text("# Private\n\n[[definitely-broken-confidential-link]]\n", encoding="utf-8")
        led = self.ws / "system" / "learning"
        led.mkdir(parents=True, exist_ok=True)
        ev = lambda s, pol="supports": {"session": s, "date": "2026-11-10", "polarity": pol, "note": ""}  # noqa: E731
        (led / "ledger.json").write_text(json.dumps({"version": 1, "items": {
            "PAT-001": {"id": "PAT-001", "kind": "pattern", "statement": "Owner shortens digest intros", "status": "open",
                        "first_seen": "2026-10-20", "last_seen": "2026-11-10",
                        "evidence": [ev("a1"), ev("a2"), ev("a3")]},
            "HYP-001": {"id": "HYP-001", "kind": "hypothesis", "statement": "Longer drafts are preferred", "status": "open",
                        "first_seen": "2026-09-01", "last_seen": "2026-09-05",
                        "evidence": [ev("b1"), ev("b2", "refutes"), ev("b3", "refutes")]}}}), encoding="utf-8")
        prop = self.ws / "inbox" / "proposals"
        prop.mkdir(parents=True, exist_ok=True)
        (prop / "PRP-009-old-open.md").write_text(
            "---\nid: PRP-009\naudience: system\ndate: 2026-10-01\nstate: open\ntitle: \"Old idea\"\nsource: PAT-001\nby: ai\n---\n# Old idea\n",
            encoding="utf-8")

    def test_report_sections_and_counts(self):
        rc, out, _, err = self.run_s(REVIEW / "run_system_review.py", ["--today", "2026-11-13", "--no-doctor"])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["counts"]["promotion"], 1)
        self.assertEqual(out["counts"]["demotion"], 1)
        report = (self.ws / out["outputs"][0]).read_text(encoding="utf-8")
        self.assertTrue(out["outputs"][0].endswith("_system-review-2026-W46.md"))
        self.assertIn("**PAT-001**", report)
        self.assertIn("RSK-001", report)  # open and older than 60 days
        self.assertNotIn("RSK-999", report)  # fenced human block skipped
        self.assertNotIn("RSK-003", report)  # closed later
        self.assertIn("2026-11-10 - digest intro length", report)
        self.assertNotIn("2026-09-01 - old", report)
        self.assertIn("PRP-009", report)
        self.assertIn("skeleton-only/ - missing README.md", report)
        self.assertIn("[[ghost-page]]", report)
        self.assertNotIn("definitely-broken-confidential-link", report)  # growth/ is never read

    def test_never_modifies_other_files(self):
        before = {p: p.read_bytes() for p in self.ws.rglob("*") if p.is_file()}
        self.run_s(REVIEW / "run_system_review.py", ["--today", "2026-11-13", "--no-doctor"])
        for p, data in before.items():
            self.assertEqual(p.read_bytes(), data, p)

    def test_bad_week_is_rejected(self):
        rc, out, _, _ = self.run_s(REVIEW / "run_system_review.py", ["--week", "W46", "--no-doctor"])
        self.assertEqual((rc, out["status"]), (2, "failed"))

    def test_sample_proposals_parse(self):
        sample = wsutil.REPO / "examples" / "sample-workspace" / "inbox" / "proposals"
        states = [re.search(r"^state: (\w+)", f.read_text(encoding="utf-8"), re.M).group(1) for f in sorted(sample.glob("PRP-*.md"))]
        self.assertEqual(sorted(set(states)), ["accepted", "open", "rejected"])


if __name__ == "__main__":
    unittest.main()
