import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_ws import make_workspace, run, script  # noqa: E402

MODS = ["brain-growth"]
S = lambda skill, name: script("brain-growth", skill, name)  # noqa: E731


def classified(sha="d4e5f6a1b2c3", cid="p3-evi-experiments", **kw):
    item = {"source_path": "raw/meetings/2026/2026-W46/mtg-2026-11-11-x.md", "snippet": "Alex ran an A/B test on the payment step.",
            "line_range": [1, 2], "content_sha256": sha, "pattern_id": "data-measurement", "actor_evidence": "Alex",
            "title": "2026-11-11 — Payment step A/B test", "confidence": "Medium",
            "classifications": [{"criterion_id": cid, "target_level": "P3"}]}
    item.update(kw)
    return item


class GrowthBase(unittest.TestCase):
    def setUp(self):
        self.ws = make_workspace(MODS)
        self.addCleanup(shutil.rmtree, self.ws, True)

    def write(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def evidence(self):
        return (self.ws / "growth/development/evidence-candidates.md").read_text()


class TestPathMerge(unittest.TestCase):
    def test_no_collisions_and_keys(self):
        ws = make_workspace(["brain-growth", "brain-mentoring", "brain-stakeholders"])
        self.addCleanup(shutil.rmtree, ws, True)
        paths = json.loads((ws / ".claude/paths.json").read_text())
        for section in ("growth", "mentoring", "stakeholders"):
            self.assertIn(section, paths)


class TestMine(GrowthBase):
    def test_mines_actor_lines_and_skips_confidential(self):
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-11-metrics.md",
                   "---\nid: x\n---\n# Metrics sync\nAlex defined the funnel metric and set up a dashboard for the team.\nTaylor agreed.\n")
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-11-secret.md",
                   "---\nsensitivity: confidential\n---\nAlex defined a metric and a dashboard.\n")
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-11-nobody.md", "Somebody built a dashboard and a metric.\n")
        rc, out, err = run(S("growth-signals", "mine_signals.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertGreaterEqual(out["candidates"], 1)
        cands = json.loads((self.ws / out["output"]).read_text())
        sources = {c["source_path"] for c in cands}
        self.assertTrue(all("metrics" in s or s.startswith("growth/") for s in sources), sources)
        self.assertTrue(out["output"].startswith("growth/"))
        self.assertNotIn("snippet", json.dumps(out))

    def test_senior_pattern_needs_a_senior_name(self):
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-12-steerco.md",
                   "Morgan Diaz said Alex wrote the clearest decision paper.\n")
        rc, out, _ = run(S("growth-signals", "mine_signals.py"), ["--today", "2026-11-14"], self.ws)
        cands = json.loads((self.ws / out["output"]).read_text())
        self.assertIn("senior-tier-feedback", {c["pattern_id"] for c in cands})

    def test_second_run_filters_known_hashes(self):
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-11-metrics.md", "Alex defined the funnel metric and dashboard.\n")
        rc, out, _ = run(S("growth-signals", "mine_signals.py"), ["--today", "2026-11-14"], self.ws)
        cands = json.loads((self.ws / out["output"]).read_text())
        items = [classified(sha=c["content_sha256"]) for c in cands]
        self.write("growth/development/run/classified.json", json.dumps(items))
        rc, out2, err = run(S("growth-signals", "append_evidence.py"), ["--classified", "growth/development/run/classified.json"], self.ws)
        self.assertEqual(rc, 0, err)
        rc, out3, _ = run(S("growth-signals", "mine_signals.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(out3["candidates"], 0)
        self.assertGreaterEqual(out3["already_known"], 1)


class TestAppend(GrowthBase):
    def test_unknown_criterion_rejected_and_nothing_written(self):
        before = self.evidence()
        self.write("growth/development/run/c.json", json.dumps([classified(cid="made-up-id")]))
        rc, out, _ = run(S("growth-signals", "append_evidence.py"), ["--classified", "growth/development/run/c.json"], self.ws)
        self.assertEqual(rc, 1)
        self.assertEqual(out["status"], "failed")
        self.assertIn("unknown criterion id", " ".join(out["errors"]))
        self.assertEqual(self.evidence(), before)
        self.assertFalse((self.ws / "growth/development/run/run-log.json").exists())

    def test_appends_section_and_dedups(self):
        self.write("growth/development/run/c.json", json.dumps([classified(), classified(sha="a1b2c3d4e5f6")]))
        rc, out, err = run(S("growth-signals", "append_evidence.py"), ["--classified", "growth/development/run/c.json", "--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["candidates_added"], 1)
        self.assertEqual(out["duplicates_skipped"], 1)
        text = self.evidence()
        self.assertLess(text.index("## 2026-11-14"), text.index("## 2026-11-09"))
        self.assertIn("`hash: d4e5f6a1b2c3`", text)
        self.assertNotIn("MEMORY", json.dumps(out))
        self.assertFalse((self.ws / "MEMORY.md").exists())

    def test_hypothesis_opens_at_three_hits(self):
        items = [classified(sha=f"{i:012x}", cid="p3-evi-experiments") for i in range(1, 4)]
        self.write("growth/development/run/c.json", json.dumps(items))
        rc, out, _ = run(S("growth-signals", "append_evidence.py"), ["--classified", "growth/development/run/c.json"], self.ws)
        self.assertEqual(out["hypotheses_updated"], 1)
        self.assertIn("p3-evi-experiments", (self.ws / "growth/development/level-hypotheses.md").read_text())


class TestPromote(GrowthBase):
    def tick(self, title_part, box):
        text = self.evidence().splitlines()
        out, in_block = [], False
        for ln in text:
            if ln.startswith("#### "):
                in_block = title_part in ln
            if in_block and ln.startswith("- **Triage:**"):
                ln = ln.replace(f"`[ ]` {box}", f"`[x]` {box}")
            out.append(ln)
        (self.ws / "growth/development/evidence-candidates.md").write_text("\n".join(out) + "\n")

    def test_accept_promotes_and_is_idempotent(self):
        self.tick("decision paper as a template", "Accept")
        self.tick("onboarding funnel", "Reject")
        rc, out, err = run(S("growth-signals", "promote.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual((out["accepted"], out["rejected"]), (1, 1))
        self.assertTrue(out["matrix_rebuilt"], out)
        tracker = (self.ws / "growth/development/performance-tracker.md").read_text()
        self.assertIn("<!-- crit: p3-inf-exec-narrative -->", tracker)
        self.assertIn("## Influence and Narrative", tracker)
        snap = (tracker, self.evidence())
        rc, out2, _ = run(S("growth-signals", "promote.py"), ["--today", "2026-11-15"], self.ws)
        self.assertEqual((out2["accepted"], out2["rejected"], out2["matrix_rebuilt"]), (0, 0, False))
        self.assertEqual(snap, ((self.ws / "growth/development/performance-tracker.md").read_text(), self.evidence()))
        self.assertIn("Promoted on 2026-11-14", self.evidence())

    def test_matrix_reflects_evidence(self):
        rc, out, err = run(S("growth-signals", "build_matrix.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        md = (self.ws / "growth/development/coverage-matrix.md").read_text()
        self.assertIn("p3-team-coaching", md)
        self.assertIn("| Criterion | Evidence | Latest evidence |", md)
        self.assertIn("sensitivity: confidential", md)
        self.assertIn("| gap |", md)
        self.assertNotIn("<", md)
        self.assertGreater(out["gaps"], 0)


class TestObjectivesAndReview(GrowthBase):
    def test_lint_sample_passes_and_bad_fails(self):
        rc, out, err = run(S("objectives", "lint_objectives.py"), ["--file", "growth/objectives/2027-H1.md"], self.ws)
        self.assertEqual(rc, 0, out)
        self.write("growth/objectives/bad.md", "---\nperiod: x\n---\n## Objective 1: Vague\nShort.\n**Done looks like:**\n- [ ] Ongoing good work\n<!-- framework-criteria: nope -->\n")
        rc, out, _ = run(S("objectives", "lint_objectives.py"), ["--file", "growth/objectives/bad.md"], self.ws)
        self.assertEqual(rc, 1)
        joined = " ".join(out["errors"])
        for needle in ("3 to 5", "narrative", "at least 2", "vague", "unknown criterion"):
            self.assertIn(needle, joined)

    def test_progress_signals(self):
        rc, out, err = run(S("objective-review", "objective_progress.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        by = {o["n"]: o for o in out["objectives"]}
        self.assertEqual(by[3]["boxes_done"], 1)
        self.assertIn("p3-team-coaching", by[3]["criteria"])
        self.assertEqual(len(by[3]["promoted_evidence"]), 1)
        self.assertTrue(by[3]["signal"] in ("on-track", "thin"))
        self.assertGreater(len(by[1]["pending_candidates"]), 0)

    def test_gap_report_and_evidence_map(self):
        rc, out, err = run(S("career", "gap_report.py"), [], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["target_level"], "P4")
        rc, out, _ = run(S("career", "gap_report.py"), ["--level", "P9"], self.ws)
        self.assertEqual(rc, 1)
        rc, out, err = run(S("self-review", "evidence_map.py"), [], self.ws)
        self.assertEqual(rc, 0, err)
        ids = {v["id"]: v["count"] for v in out["values"]}
        self.assertEqual(ids["lift-others"], 1)
        self.assertIn("customers-first", out["values_without_evidence"])


if __name__ == "__main__":
    unittest.main()
