"""Tests for brain-ingest-notes: header parsing, normalisation, never-overwrite, duplicates, drop helper."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wsutil_notes as W  # noqa: E402

sys.path.insert(0, str(W.REPO / "lib"))
from brainos import frontmatter  # noqa: E402

_spec = importlib.util.spec_from_file_location("normalise", W.script("ingest-notes", "normalise.py"))
normalise = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(normalise)

NORMALISE = W.script("ingest-notes", "normalise.py")
DROP = W.script("note", "drop.py")
SAMPLE_NOTE = "inbox/notes/2026-11-06 retro-takeaways.md"


class HeaderParsing(unittest.TestCase):
    def test_header_lines_then_body(self):
        h, body = normalise.parse_header("Title: A\nproject: partner-api\npeople: Casey Nguyen, sam-patel\ntags: x, y\n\nBody line\nsecond")
        self.assertEqual(h, {"title": "A", "project": "partner-api", "people": "Casey Nguyen, sam-patel", "tags": "x, y"})
        self.assertEqual(body, "Body line\nsecond")

    def test_no_header_keeps_text_exactly(self):
        text = "Just a thought.\nproject management is hard: discuss\n"
        self.assertEqual(normalise.parse_header(text), ({}, text))

    def test_header_stops_at_first_non_header_line(self):
        h, body = normalise.parse_header("tags: a\nNot a header\nproject: late")
        self.assertEqual(h, {"tags": "a"})
        self.assertEqual(body, "Not a header\nproject: late")

    def test_yaml_frontmatter_header(self):
        h, body = normalise.parse_header("---\ntitle: T\ntags: [a, b]\nproject: p\n---\n\nBody")
        self.assertEqual((h["title"], h["tags"], h["project"]), ("T", "a, b", "p"))
        self.assertEqual(body, "Body")

    def test_people_slugging_and_lists(self):
        self.assertEqual([normalise.person_slug(x) for x in normalise.split_list("Casey Nguyen (Fernhill); @sam-patel")], ["casey-nguyen", "sam-patel"])
        self.assertEqual(normalise.split_list("a, b; c"), ["a", "b", "c"])
        self.assertEqual(normalise.person_slug("Casey Nguyen"), "casey-nguyen")


class Normalise(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name, copy=(SAMPLE_NOTE,))

    def run_norm(self, *args):
        return W.run_json(self.root, NORMALISE, *args)

    def drop(self, name: str, text: str) -> Path:
        p = self.root / "inbox/notes" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def notes(self):
        return sorted(self.root.glob("raw/notes/*/*/note-*.md"))

    def test_sample_note_normalised(self):
        r = self.run_norm()
        self.assertEqual(r["status"], "success")
        out = self.root / r["outputs"][0]
        self.assertEqual(out.relative_to(self.root).as_posix(), "raw/notes/2026/2026-W45/note-2026-11-06-checkout-retro-takeaways.md")
        fm = frontmatter.read(out)
        self.assertEqual(fm["source_type"], "note")
        self.assertEqual(fm["date"], "2026-11-06")
        self.assertEqual(fm["tags"], ["retro", "process"])
        self.assertEqual(fm["people"], ["jordan-lee", "casey-nguyen"])
        self.assertEqual(fm["project"], "checkout-revamp")
        self.assertEqual(fm["wiki_processed"], False)
        self.assertEqual(fm["todo_processed"], False)
        self.assertEqual(fm["id"], out.stem)
        text = out.read_text()
        self.assertIn("Three things from the checkout-revamp retro", text)
        self.assertNotIn("project: checkout-revamp\npeople", text.split("---", 2)[2])  # header lines are not in the body
        self.assertFalse((self.root / SAMPLE_NOTE).exists())
        self.assertTrue((self.root / "inbox/notes/_processed/2026-11-06 retro-takeaways.md").exists())

    def test_headerless_note_leaves_project_null_and_uses_heading_and_filename_date(self):
        self.drop("2026-11-02 scratch.md", "# Pricing thoughts\n\nNothing decided yet.\n")
        self.run_norm()
        fm = frontmatter.read(next(f for f in self.notes() if "pricing" in f.name))
        self.assertEqual(fm["title"], "Pricing thoughts")
        self.assertEqual(fm["date"], "2026-11-02")
        self.assertIsNone(fm["project"])
        self.assertEqual(fm["people"], [])

    def test_header_date_wins_over_filename(self):
        self.drop("2026-11-02 scratch.txt", "date: 2026-10-20\ntitle: Old idea\n\nText")
        self.run_norm()
        self.assertTrue(any(f.name.startswith("note-2026-10-20-old-idea") for f in self.notes()))

    def test_body_is_verbatim(self):
        body = "Line one  \n\n  indented *markdown* with `code`\n- a\n- b"
        self.drop("2026-11-02 verbatim.md", f"title: V\n\n{body}\n")
        self.run_norm()
        out = next(f for f in self.notes() if f.name.endswith("-v.md"))
        self.assertTrue(out.read_text().endswith("\n" + body + "\n"))

    def test_never_overwrites_existing_note(self):
        week = self.root / "raw/notes/2026/2026-W45"
        week.mkdir(parents=True)
        existing = week / "note-2026-11-06-checkout-retro-takeaways.md"
        existing.write_text("owner edited this file by hand")
        self.run_norm()
        self.assertEqual(existing.read_text(), "owner edited this file by hand")
        self.assertTrue((week / "note-2026-11-06-checkout-retro-takeaways-2.md").exists())

    def test_two_notes_same_title_same_day_get_suffix(self):
        self.drop("2026-11-02 a.md", "title: Same\n\nfirst body")
        self.drop("2026-11-02 b.md", "title: Same\n\nsecond body")
        self.run_norm()
        names = sorted(f.name for f in self.notes() if "same" in f.name)
        self.assertEqual(names, ["note-2026-11-02-same-2.md", "note-2026-11-02-same.md"])

    def test_identical_redrop_is_archived_not_duplicated(self):
        self.run_norm()
        self.drop("2026-11-06 retro-again.md", (self.root / "inbox/notes/_processed/2026-11-06 retro-takeaways.md").read_text())
        r = self.run_norm()
        self.assertEqual(r["counts"]["duplicates"], 1)
        self.assertEqual(r["counts"]["written"], 0)
        self.assertEqual(len(self.notes()), 1)
        self.assertEqual(list((self.root / "inbox/notes").glob("*.md")), [])

    def test_confidential_note_is_wrapped(self):
        self.drop("2026-11-02 sens.md", "sensitivity: confidential\ntitle: Hiring thoughts\n\nPrivate content")
        self.run_norm()
        out = next(f for f in self.notes() if "hiring" in f.name)
        self.assertEqual(frontmatter.read(out)["sensitivity"], "confidential")
        self.assertIn("<!-- CONFIDENTIAL: redact-on-share -->\nPrivate content\n<!-- /CONFIDENTIAL -->", out.read_text())

    def test_empty_note_left_in_inbox_underscore_files_ignored(self):
        empty = self.drop("2026-11-02 empty.md", "title: Nothing\n\n")
        ignored = self.drop("_template.md", "Real looking text")
        r = self.run_norm()
        self.assertTrue(empty.exists())
        self.assertTrue(ignored.exists())
        self.assertTrue(any("empty note" in w for w in r["warnings"]))

    def test_dry_run_and_idle_run(self):
        r = self.run_norm("--dry-run")
        self.assertTrue(r["dry_run"])
        self.assertEqual(self.notes(), [])
        self.assertTrue((self.root / SAMPLE_NOTE).exists())
        self.run_norm()
        self.assertEqual(self.run_norm()["status"], "skipped")


class DropHelper(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name)
        (self.root / "system/run/payloads").mkdir(parents=True)

    def payload(self, text: str) -> str:
        (self.root / "system/run/payloads/note.md").write_text(text, encoding="utf-8")
        return "system/run/payloads/note.md"

    def test_drop_writes_header_and_unchanged_text_then_normalises(self):
        text = "We agreed to freeze copy one sprint earlier.\nOwner: Jordan."
        r = W.run_json(self.root, DROP, "--payload", self.payload(text), "--title", "Copy freeze", "--project", "checkout-revamp",
                       "--people", "Jordan Lee", "--tags", "process", "--date", "2026-11-09")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["file"], "inbox/notes/2026-11-09 copy-freeze.md")
        self.assertFalse((self.root / "system/run/payloads/note.md").exists())
        n = W.run_json(self.root, NORMALISE)
        out = self.root / n["outputs"][0]
        fm = frontmatter.read(out)
        self.assertEqual((fm["title"], fm["project"], fm["people"]), ("Copy freeze", "checkout-revamp", ["jordan-lee"]))
        self.assertIn(text, out.read_text())

    def test_drop_never_overwrites_and_refuses_empty(self):
        r1 = W.run_json(self.root, DROP, "--payload", self.payload("one"), "--title", "Same", "--date", "2026-11-09")
        r2 = W.run_json(self.root, DROP, "--payload", self.payload("two"), "--title", "Same", "--date", "2026-11-09")
        self.assertEqual(r2["file"], "inbox/notes/2026-11-09 same-2.md")
        self.assertTrue((self.root / r1["file"]).read_text().rstrip().endswith("\none"))
        bad = W.run_json(self.root, DROP, "--payload", self.payload("   \n"), "--title", "Nothing")
        self.assertFalse(bad["ok"])


if __name__ == "__main__":
    unittest.main()
