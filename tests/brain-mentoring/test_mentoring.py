import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_ws_m import make_workspace, run, script  # noqa: E402

S = lambda skill, name: script("brain-mentoring", skill, name)  # noqa: E731


class MentoringBase(unittest.TestCase):
    def setUp(self):
        self.ws = make_workspace(["brain-growth", "brain-mentoring"])
        self.addCleanup(shutil.rmtree, self.ws, True)
        self.dir = self.ws / "growth/mentoring/casey-nguyen"

    def payload(self, data):
        p = self.ws / "growth/mentoring/_run/notes.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return p


class TestSetup(MentoringBase):
    def test_creates_confidential_folder_and_refuses_overwrite(self):
        rc, out, err = run(S("mentoring-setup", "mentoring_setup.py"),
                           ["--person", "taylor-brooks", "--mode", "mentee", "--cadence", "monthly", "--goal", "Learn experiment design", "--started", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        d = self.ws / "growth/mentoring/taylor-brooks"
        readme = (d / "README.md").read_text()
        self.assertIn("sensitivity: confidential", readme)
        self.assertIn("<!-- CONFIDENTIAL: redact-on-share -->", readme)
        self.assertIn("- G1: Learn experiment design", readme)
        self.assertTrue((d / "sessions").is_dir() and (d / "actions.md").is_file())
        rc, out, _ = run(S("mentoring-setup", "mentoring_setup.py"), ["--person", "taylor-brooks", "--mode", "mentee", "--goal", "x"], self.ws)
        self.assertEqual(rc, 1)
        self.assertIn("already exists", out["reason"])

    def test_requires_goal(self):
        rc, out, _ = run(S("mentoring-setup", "mentoring_setup.py"), ["--person", "jordan-lee", "--mode", "mentor"], self.ws)
        self.assertEqual(rc, 1)
        self.assertFalse((self.ws / "growth/mentoring/jordan-lee").exists())


class TestPrep(MentoringBase):
    def test_prep_lists_open_and_overdue(self):
        rc, out, err = run(S("mentoring-prep", "mentoring_prep.py"), ["--person", "casey-nguyen", "--today", "2026-11-20"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["last_session"]["date"], "2026-11-05")
        self.assertEqual({a["id"] for a in out["open_actions"]}, {"A-002", "A-003", "A-004"})
        self.assertEqual(set(out["overdue_actions"]), {"A-002", "A-003"})
        self.assertTrue(out["session_due"])
        self.assertEqual(len(out["goals"]), 3)
        self.assertTrue(any("Casey" in o["heading"] for o in out["related_objectives"]))


class TestNotes(MentoringBase):
    def test_extracts_actions_and_closes(self):
        p = self.payload({"date": "2026-11-19", "discussed": ["Rehearsed the Morgan presentation"], "insights": ["Starts with the decision, not the context"],
                          "actions": [{"owner": "casey-nguyen", "what": "Send the deck to Alex", "due": "2026-11-24"}, {"owner": "alex-morgan", "what": "Book Morgan slot"}],
                          "closed": ["A-002"]})
        rc, out, err = run(S("mentoring-notes", "mentoring_notes.py"), ["--person", "casey-nguyen", "--payload", str(p.relative_to(self.ws))], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual((out["actions_added"], out["actions_closed"], out["open_actions"]), (2, 1, 4))
        self.assertFalse(p.exists())
        acts = (self.dir / "actions.md").read_text()
        self.assertIn("- [x] A-002", acts)
        self.assertIn("A-005 · 2026-11-19 · owner: casey-nguyen · due: 2026-11-24 · Send the deck to Alex", acts)
        self.assertIn("A-006", acts)
        note = (self.dir / "sessions/2026-11-19-session.md").read_text()
        self.assertIn("sensitivity: confidential", note)
        self.assertIn("<!-- CONFIDENTIAL: redact-on-share -->", note)

    def test_invalid_leaves_everything_untouched(self):
        before = (self.dir / "actions.md").read_text()
        p = self.payload({"date": "19/11", "discussed": [], "actions": [{"owner": "nobody-here", "what": "x"}], "closed": ["A-099"]})
        rc, out, _ = run(S("mentoring-notes", "mentoring_notes.py"), ["--person", "casey-nguyen", "--payload", str(p.relative_to(self.ws))], self.ws)
        self.assertEqual(rc, 1)
        self.assertEqual(out["status"], "invalid")
        self.assertGreaterEqual(len(out["errors"]), 4)
        self.assertTrue(p.exists())
        self.assertEqual((self.dir / "actions.md").read_text(), before)
        self.assertEqual(len(list((self.dir / "sessions").glob("*.md"))), 2)

    def test_same_day_gets_suffix(self):
        for _ in range(2):
            p = self.payload({"date": "2026-11-05", "discussed": ["Follow-up call"]})
            rc, out, _ = run(S("mentoring-notes", "mentoring_notes.py"), ["--person", "casey-nguyen", "--payload", str(p.relative_to(self.ws))], self.ws)
            self.assertEqual(rc, 0)
        self.assertTrue((self.dir / "sessions/2026-11-05-session-3.md").exists())


class TestReview(MentoringBase):
    def test_quarter_counts(self):
        rc, out, err = run(S("mentoring-review", "mentoring_review.py"), ["--person", "casey-nguyen", "--quarter", "2026-Q4", "--today", "2026-11-20"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["window"], ["2026-10-01", "2026-12-31"])
        self.assertEqual((out["sessions_held"], out["actions_opened"], out["actions_closed"], out["actions_open"]), (2, 4, 1, 3))
        self.assertEqual(out["longest_gap_days"], 14)
        rc, _, _ = run(S("mentoring-review", "mentoring_review.py"), ["--person", "casey-nguyen", "--quarter", "Q4"], self.ws)
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
