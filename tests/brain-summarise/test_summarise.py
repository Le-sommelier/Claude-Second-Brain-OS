import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws import REPO, make_workspace, run, write  # noqa: E402

PLUGIN = REPO / "plugins" / "brain-summarise" / "skills"
DETECT = PLUGIN / "meeting-summarise" / "scripts" / "detect_new_meetings.py"
ADD = PLUGIN / "todo-extract" / "scripts" / "add_todos.py"


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        w = "raw/meetings/2026/2026-W45/"
        write(self.root, w + "mtg-2026-11-04-checkout-weekly.txt", "Alex Morgan: hello\n")
        write(self.root, w + "mtg-2026-11-05-partner-api-sync.md", "---\nid: mtg-2026-11-05-partner-api-sync\nwiki_processed: false\ntodo_processed: false\n---\nText\n")
        write(self.root, w + "mtg-2026-11-03-done.txt", "x")
        write(self.root, w + "mtg-2026-11-03-done.summary.md", "---\nid: mtg-2026-11-03-done\n---\n")
        write(self.root, w + "mtg-2026-11-02-linked.txt", "x")
        write(self.root, w + "other-note.summary.md", f'---\nsource_transcript: "{w}mtg-2026-11-02-linked.txt"\n---\n')

    def test_finds_only_unsummarised(self):
        r = run(DETECT, self.root, "--today", "2026-11-13")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        ids = sorted(m["id"] for m in out["meetings"])
        self.assertEqual(ids, ["mtg-2026-11-04-checkout-weekly", "mtg-2026-11-05-partner-api-sync"])
        by = {m["id"]: m for m in out["meetings"]}
        self.assertTrue(by["mtg-2026-11-05-partner-api-sync"]["raw_has_flags"])
        self.assertFalse(by["mtg-2026-11-04-checkout-weekly"]["raw_has_flags"])
        self.assertTrue(by["mtg-2026-11-04-checkout-weekly"]["note_path"].endswith("mtg-2026-11-04-checkout-weekly.summary.md"))
        self.assertFalse(out["fan_out"])

    def test_empty_when_all_summarised(self):
        write(self.root, "raw/meetings/2026/2026-W45/mtg-2026-11-04-checkout-weekly.summary.md", "---\nid: x\n---\n")
        write(self.root, "raw/meetings/2026/2026-W45/mtg-2026-11-05-partner-api-sync.summary.md", "---\nid: y\n---\n")
        out = json.loads(run(DETECT, self.root, "--today", "2026-11-13").stdout)
        self.assertEqual(out["count"], 0)

    def test_lookback_window(self):
        out = json.loads(run(DETECT, self.root, "--today", "2026-12-20", "--lookback-weeks", "1").stdout)
        self.assertEqual(out["count"], 0)

    def test_sample_summaries_have_required_frontmatter(self):
        sys.path.insert(0, str(REPO / "lib"))
        from brainos import frontmatter
        base = REPO / "examples" / "sample-workspace" / "raw" / "meetings" / "2026" / "2026-W45"
        files = sorted(base.glob("*.summary.md"))
        self.assertGreaterEqual(len(files), 2)
        for f in files:
            fm = frontmatter.read(f)
            for key in ("id", "date", "attendees", "attendance", "project", "meeting_type", "wiki_processed"):
                self.assertIn(key, fm, f"{f.name} lacks {key}")
            self.assertEqual(fm["id"], f.name.removesuffix(".summary.md"))
            self.assertIs(fm["wiki_processed"], False)


class TodoTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        write(self.root, "todos/todo.md", "# Todos\n\n## Doing\n- [ ] My own card\n\n## Inbox (from meetings)\n- [ ] Existing #checkout-revamp [[mtg-2026-11-04-checkout-weekly]]\n\n## Later\n- [ ] Someday\n")

    def payload(self, cards):
        return write(self.root, "system/run/payloads/todos.json", json.dumps(cards))

    def test_adds_owner_cards_and_rejects_others(self):
        self.payload([
            {"title": "Confirm the rollout plan", "owner": "Alex", "source": "mtg-2026-11-04-checkout-weekly", "due": "2026-11-09", "tag": "checkout-revamp"},
            {"title": "Fix sandbox retries", "owner": "Sam Patel", "source": "mtg-2026-11-04-checkout-weekly"},
            {"title": "Name an owner for the playbook", "owner": "unclear", "source": "mtg-2026-11-04-checkout-weekly"},
            {"title": "Existing", "owner": "alex-morgan", "source": "mtg-2026-11-04-checkout-weekly"},
        ])
        r = run(ADD, self.root, "--file", "system/run/payloads/todos.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual((out["added"], out["skipped_duplicate"], len(out["rejected"])), (2, 1, 1))
        text = (self.root / "todos/todo.md").read_text()
        self.assertIn("- [ ] Confirm the rollout plan #checkout-revamp (due 2026-11-09) [[mtg-2026-11-04-checkout-weekly]]", text)
        self.assertIn("Confirm owner of: Name an owner for the playbook", text)
        self.assertNotIn("Fix sandbox", text)
        # other sections untouched and ordered
        self.assertLess(text.index("Confirm the rollout"), text.index("## Later"))
        self.assertIn("- [ ] My own card", text)
        self.assertFalse((self.root / "system/run/payloads/todos.json").exists())

    def test_idempotent(self):
        card = [{"title": "Send the beta list", "owner": "Alex", "source": "mtg-2026-11-05-partner-api-sync"}]
        self.payload(card)
        run(ADD, self.root, "--file", "system/run/payloads/todos.json")
        self.payload(card)
        out = json.loads(run(ADD, self.root, "--file", "system/run/payloads/todos.json").stdout)
        self.assertEqual(out["added"], 0)
        self.assertEqual((self.root / "todos/todo.md").read_text().count("Send the beta list"), 1)

    def test_bad_payload_writes_nothing(self):
        before = (self.root / "todos/todo.md").read_text()
        self.payload([{"title": "ok", "owner": "Alex", "source": "s"}, {"title": "no source", "owner": "Alex"}])
        r = run(ADD, self.root, "--file", "system/run/payloads/todos.json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual((self.root / "todos/todo.md").read_text(), before)

    def test_creates_file_and_section(self):
        (self.root / "todos/todo.md").unlink()
        self.payload([{"title": "First card", "owner": "alex-morgan", "source": "mtg-x"}])
        r = run(ADD, self.root, "--file", "system/run/payloads/todos.json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## Inbox (from meetings)\n- [ ] First card [[mtg-x]]", (self.root / "todos/todo.md").read_text())


if __name__ == "__main__":
    unittest.main()
