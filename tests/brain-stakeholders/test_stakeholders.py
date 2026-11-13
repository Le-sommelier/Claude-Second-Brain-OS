import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_ws_s import make_workspace, run, script  # noqa: E402

S = lambda skill, name: script("brain-stakeholders", skill, name)  # noqa: E731
OPEN, CLOSE = "<!-- CONFIDENTIAL: redact-on-share -->", "<!-- /CONFIDENTIAL -->"
BRAND = "# Brand\n\n## Words I Never Use\n\n- leverage\n- synergy (corporate)\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = make_workspace(["brain-stakeholders"], copy=("people",))
        self.addCleanup(shutil.rmtree, self.ws, True)

    def write(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def page(self, pid):
        return (self.ws / f"people/{pid}.md").read_text()


class TestOrg(Base):
    def test_sample_chart_is_valid_and_pages_match(self):
        rc, out, err = run(S("person", "org.py"), ["check"], self.ws)
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["people"], 7)
        self.assertEqual(out["warnings"], [])

    def test_dangling_manager_duplicate_and_cycle(self):
        org = (self.ws / "people/_org.yaml").read_text()
        org = org.replace("manager: sam-patel", "manager: ghost-person").replace("  - id: jordan-lee\n", "  - id: casey-nguyen\n    name: Dup\n  - id: jordan-lee\n")
        org = org.replace("  - id: morgan-diaz\n    name: Morgan Diaz\n    role: VP Product\n", "  - id: morgan-diaz\n    name: Morgan Diaz\n    role: VP Product\n    manager: riley-chen\n")
        self.write("people/_org.yaml", org)
        rc, out, _ = run(S("person", "org.py"), ["check"], self.ws)
        self.assertEqual(rc, 1)
        joined = " ".join(out["errors"])
        self.assertIn("ghost-person", joined)
        self.assertIn("duplicate id 'casey-nguyen'", joined)
        self.assertIn("cycle", joined)

    def test_add_and_refuse(self):
        rc, out, err = run(S("person", "org.py"), ["add", "--id", "devon-ray", "--name", "Devon Ray", "--role", "QA Lead", "--manager", "sam-patel"], self.ws)
        self.assertEqual(rc, 0, err)
        rc, out, _ = run(S("person", "org.py"), ["add", "--id", "devon-ray", "--name", "Devon Ray"], self.ws)
        self.assertEqual(rc, 1)
        rc, out, _ = run(S("person", "org.py"), ["add", "--id", "new-hire", "--name", "New Hire", "--manager", "nobody-here"], self.ws)
        self.assertEqual(rc, 1)
        rc, out, _ = run(S("person", "org.py"), ["check"], self.ws)
        self.assertEqual(out["people"], 8)
        self.assertTrue(any("devon-ray" in w for w in out["warnings"]))  # no page yet
        rc, out, _ = run(S("person", "org.py"), ["tree"], self.ws)
        self.assertTrue(out["tree"][0].startswith("Morgan Diaz"))


class TestPerson(Base):
    def payload(self, d):
        return str(self.write("growth/one-on-ones/payloads/person.json", json.dumps(d)).relative_to(self.ws))

    def test_update_preserves_human_fence_and_wraps_notes(self):
        before = self.page("sam-patel")
        fence = before[before.index("<!-- human -->"):before.index("<!-- /human -->")]
        p = self.payload({"fields": {"influence": 5, "health": "strong", "last_contact": "2026-11-12"},
                          "notes": [{"date": "2026-11-12", "text": "Wants estimates reviewed earlier."}],
                          "evidence": [{"date": "2026-11-12", "text": "Pre-wired the Q1 trade-offs", "source": "mtg-2026-11-12-q1"}]})
        rc, out, err = run(S("person", "person_page.py"), ["--id", "sam-patel", "--payload", p], self.ws)
        self.assertEqual(rc, 0, err)
        after = self.page("sam-patel")
        self.assertIn(fence, after)
        self.assertIn("influence: 5", after)
        self.assertIn("last_contact: 2026-11-12", after)
        note = "- 2026-11-12 · Wants estimates reviewed earlier."
        i = after.index(note)
        self.assertLess(after.rindex(OPEN, 0, i), i)
        self.assertGreater(after.index(CLOSE, i), i)
        self.assertIn("source: [[mtg-2026-11-12-q1]]", after)
        # idempotent on evidence/notes
        self.write("growth/one-on-ones/payloads/person.json", json.dumps({"notes": [{"date": "2026-11-12", "text": "Wants estimates reviewed earlier."}],
                                                                         "evidence": [{"date": "2026-11-12", "text": "Pre-wired the Q1 trade-offs", "source": "mtg-2026-11-12-q1"}]}))
        rc, out, _ = run(S("person", "person_page.py"), ["--id", "sam-patel", "--payload", "growth/one-on-ones/payloads/person.json"], self.ws)
        self.assertEqual((out["notes_added"], out["evidence_added"]), (0, 0))
        self.assertEqual(self.page("sam-patel"), after)

    def test_invalid_field_writes_nothing(self):
        before = self.page("riley-chen")
        p = self.payload({"fields": {"influence": 9, "role": "CEO"}})
        rc, out, _ = run(S("person", "person_page.py"), ["--id", "riley-chen", "--payload", p], self.ws)
        self.assertEqual(rc, 1)
        self.assertEqual(out["status"], "invalid")
        self.assertEqual(len(out["errors"]), 2)
        self.assertEqual(self.page("riley-chen"), before)

    def test_missing_page_points_to_brain_new(self):
        p = self.payload({"fields": {"health": "ok"}})
        rc, out, _ = run(S("person", "person_page.py"), ["--id", "no-page", "--payload", p], self.ws)
        self.assertEqual(rc, 1)
        self.assertIn("brain new person", out["reason"])


class TestMap(Base):
    def test_map_outputs_confidential_and_stale(self):
        rc, out, err = run(S("stakeholder-map", "build_map.py"), ["--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["rated"], 6)  # alex is self
        md = (self.ws / "people/_stakeholder-map.md").read_text()
        self.assertIn("quadrantChart", md)
        self.assertIn("sensitivity: confidential", md)
        self.assertIn("Morgan Diaz", md)
        self.assertNotIn("Nervous about presenting", md)  # ratings only, never notes
        self.assertEqual(out["outputs"], ["people/_stakeholder-map.md"])
        self.assertGreaterEqual(out["stale"], 1)  # morgan-diaz last contact 2026-10-10, cadence 30


class TestOneOnOnes(Base):
    def setUp(self):
        super().setUp()
        self.write("BRAND.md", BRAND)
        self.write(".claude/paths.json", json.dumps({**json.loads((self.ws / ".claude/paths.json").read_text())}))
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-12-casey-1-1.txt", "transcript")
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-12-casey-1-1.summary.md", "summary")
        self.write("raw/meetings/2026/2026-W46/mtg-2026-11-12-product-sync.txt", "not a roster meeting")
        self.write("raw/meetings/2026/2026-W40/mtg-2026-10-01-casey-1-1.txt", "before go-live")
        rc, _, err = run(S("one-on-ones", "detect.py"), ["--init", "--since", "2026-11-01"], self.ws)
        self.assertEqual(rc, 0, err)

    def draft(self, **over):
        d = {"id": "mtg-2026-11-12-casey-1-1", "person_id": "casey-nguyen", "date": "2026-11-12", "title": "Q1 roadmap and review prep",
             "sections": {"discussed": ["Roadmap review moved to Thursday", "Trade-offs pre-wired with Sam"], "decisions": ["Use the one-page format"],
                          "career": ["Casey owns the Q1 roadmap"]},
             "actions": [{"who": "Casey", "what": "Send the pre-read", "due": "2026-11-19"}], "withheld": 1, "source": "mtg-2026-11-12-casey-1-1.txt"}
        d.update(over)
        return str(self.write("growth/one-on-ones/payloads/1on1.json", json.dumps(d)).relative_to(self.ws))

    def test_detect_respects_go_live_roster_and_summary(self):
        rc, out, err = run(S("one-on-ones", "detect.py"), [], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual([i["id"] for i in out["items"]], ["mtg-2026-11-12-casey-1-1"])
        self.assertTrue(out["items"][0]["summary"].endswith(".summary.md"))
        rc, _, _ = run(S("one-on-ones", "detect.py"), ["--init"], self.ws)
        self.assertNotEqual(rc, 0)  # ledger is never recreated

    def test_invalid_draft_leaves_payload_and_ledger(self):
        long = " ".join(["word"] * 40)
        p = self.draft(sections={"discussed": [long, "We should leverage this"], "career": ["x"]}, person_id="casey-nguyen")
        rc, out, _ = run(S("one-on-ones", "queue_draft.py"), ["--payload", p], self.ws)
        self.assertEqual(rc, 1)
        self.assertEqual(out["status"], "invalid")
        joined = " ".join(out["errors"])
        self.assertIn("bullet too long", joined)
        self.assertIn("banned word", joined)
        self.assertTrue((self.ws / p).exists())
        self.assertEqual(json.loads((self.ws / "growth/one-on-ones/ledger.json").read_text())["drafted"], {})
        self.assertEqual(list((self.ws / "growth/one-on-ones/queue").glob("*/*.json")), [])
        rc, out, _ = run(S("one-on-ones", "queue_draft.py"), ["--payload", self.draft(person_id="jordan-lee")], self.ws)
        self.assertIn("not on the roster", " ".join(out["errors"]))

    def test_queue_then_push_needs_approval_and_wraps(self):
        rc, out, err = run(S("one-on-ones", "queue_draft.py"), ["--payload", self.draft()], self.ws)
        self.assertEqual((rc, out["status"]), (0, "queued"), err)
        rc, out, _ = run(S("one-on-ones", "queue_status.py"), [], self.ws)
        self.assertEqual(out["queued"], 1)
        before = self.page("casey-nguyen")
        rc, out, _ = run(S("one-on-ones", "push_draft.py"), ["--id", "mtg-2026-11-12-casey-1-1"], self.ws)
        self.assertEqual((rc, out["status"]), (1, "refused"))
        self.assertEqual(self.page("casey-nguyen"), before)
        rc, out, err = run(S("one-on-ones", "push_draft.py"), ["--id", "mtg-2026-11-12-casey-1-1", "--approved"], self.ws)
        self.assertEqual((rc, out["status"]), (0, "pushed"), err)
        after = self.page("casey-nguyen")
        entry = "### 2026-11-12 · Q1 roadmap and review prep"
        i = after.index(entry)
        self.assertLess(after.rindex(OPEN, 0, i), i)
        self.assertGreater(after.index(CLOSE, i), i)
        self.assertLess(i, after.index("### 2026-11-05"))  # newest first
        self.assertIn("- [ ] Casey: Send the pre-read (due 2026-11-19)", after)
        self.assertIn("last_contact: 2026-11-12", after)
        self.assertIn("Writes well; hesitates", after)  # human fence intact
        ledger = json.loads((self.ws / "growth/one-on-ones/ledger.json").read_text())
        self.assertIn("mtg-2026-11-12-casey-1-1", ledger["pushed"])
        self.assertEqual(list((self.ws / "growth/one-on-ones/queue").glob("*/*.json")), [])

    def test_prep_reads_log_and_open_actions(self):
        rc, out, err = run(S("one-on-one-prep", "prep.py"), ["--person", "casey-nguyen", "--today", "2026-11-14"], self.ws)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["recent_entries"][0]["date"], "2026-11-05")
        self.assertEqual(out["open_actions"][0]["action"], "Casey: pre-wire the Q1 trade-offs with Sam (due 2026-11-19)")
        self.assertEqual(out["days_since_contact"], 9)


if __name__ == "__main__":
    unittest.main()
