"""Tests for brain-ingest-confluence: plan, diff, write, version-change reset, guards."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wsutil_confluence as W  # noqa: E402

sys.path.insert(0, str(W.REPO / "lib"))
from brainos import frontmatter  # noqa: E402

SYNC = W.script("ingest-confluence", "sync.py")
TEMPLATE = W.REPO / "plugins" / "brain-ingest-confluence" / "templates" / "confluence-watch.json"
BODY_V1 = "## Summary\n\nPartner API sandbox goes live on 18 November for the pilot partners, with rate limits set per partner.\n"
BODY_V2 = BODY_V1 + "\n## Update\n\nSandbox date confirmed by engineering; token expiry spike completed.\n"


def page(**kw) -> dict:
    base = {"id": "5500231", "title": "Partner API rollout plan", "url": "https://fernhill.example/wiki/spaces/PROD/pages/5500231",
            "space": "PROD", "version": 1, "last_modified": "2026-11-03T09:00:00Z", "labels": ["prd"], "body": BODY_V1}
    base.update(kw)
    return base


class SyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name)
        shutil.copy(TEMPLATE, self.root / ".claude/brain/confluence-watch.json")
        (self.root / "system/run/payloads").mkdir(parents=True)

    def payload(self, name: str, data) -> str:
        rel = f"system/run/payloads/{name}.json"
        (self.root / rel).write_text(json.dumps(data), encoding="utf-8")
        return rel

    def write(self, **kw) -> dict:
        return W.run_json(self.root, SYNC, "write", "--payload", self.payload("p", page(**kw)))

    def state(self) -> dict:
        return json.loads((self.root / "system/run/confluence-state.json").read_text())

    # ----- write -----

    def test_write_creates_week_file_with_metadata(self):
        r = self.write()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["status"], "created")
        out = self.root / r["file"]
        self.assertEqual(out.relative_to(self.root).as_posix(), "raw/confluence/2026/2026-W45/conf-2026-11-03-partner-api-rollout-plan.md")
        fm = frontmatter.read(out)
        self.assertEqual(fm["confluence_page_id"], "5500231")
        self.assertEqual(fm["confluence_version"], "1")
        self.assertEqual(fm["confluence_space"], "PROD")
        self.assertEqual(fm["labels"], ["prd"])
        self.assertEqual(fm["wiki_processed"], False)
        self.assertIn(BODY_V1.strip(), out.read_text())  # verbatim body
        self.assertFalse((self.root / "system/run/payloads/p.json").exists())  # payload consumed

    def test_version_change_rewrites_same_file_and_resets_flag(self):
        first = self.write()
        out = self.root / first["file"]
        frontmatter.update_file(out, {"wiki_processed": True})  # the wiki step consumed v1
        self.assertEqual(frontmatter.read(out)["wiki_processed"], True)
        r = self.write(version=2, body=BODY_V2, last_modified="2026-11-06T16:00:00Z")
        self.assertEqual(r["status"], "rewritten")
        self.assertEqual(r["file"], first["file"])  # ID and path are stable across versions
        fm = frontmatter.read(out)
        self.assertEqual(fm["wiki_processed"], False)
        self.assertEqual(fm["confluence_version"], "2")
        self.assertIn("token expiry spike completed", out.read_text())
        self.assertEqual(len(list(self.root.glob("raw/confluence/*/*/conf-*.md"))), 1)
        self.assertEqual(self.state()["pages"]["5500231"]["version"], 2)

    def test_same_version_same_body_is_unchanged_and_keeps_flag(self):
        out = self.root / self.write()["file"]
        frontmatter.update_file(out, {"wiki_processed": True})
        r = self.write()
        self.assertEqual(r["status"], "unchanged")
        self.assertFalse(r["changed"])
        self.assertEqual(frontmatter.read(out)["wiki_processed"], True)

    def test_placeholder_and_stub_bodies_never_overwrite_real_content(self):
        out = self.root / self.write()["file"]
        before = out.read_text()
        for bad in ("", "[Body content for Partner API rollout plan]", "TBD", "too short"):
            r = self.write(version=9, body=bad)
            self.assertFalse(r["ok"], bad)
        self.assertEqual(out.read_text(), before)
        self.assertEqual(self.state()["pages"]["5500231"]["version"], 1)

    def test_missing_fields_rejected(self):
        proc = W.run_json(self.root, SYNC, "write", "--payload", self.payload("p", {"id": "1", "title": "x"}))
        self.assertFalse(proc["ok"])

    def test_decision_page_tag_from_title_and_label(self):
        by_title = self.write(id="1", title="Decision: sandbox date", body=BODY_V1)
        by_label = self.write(id="2", title="Rate limit design", body=BODY_V1 + "x", labels=["adr"])
        plain = self.write(id="3", title="Roadmap notes", body=BODY_V1 + "y")
        for r, expected in ((by_title, ["decision-page"]), (by_label, ["decision-page"]), (plain, [])):
            self.assertEqual(frontmatter.read(self.root / r["file"])["tags"], expected)

    def test_confidential_label_wraps_body(self):
        r = self.write(id="9", title="Reorg plan", labels=["confidential"])
        text = (self.root / r["file"]).read_text()
        self.assertEqual(frontmatter.read(self.root / r["file"])["sensitivity"], "confidential")
        self.assertIn("<!-- CONFIDENTIAL: redact-on-share -->", text)
        self.assertIn("<!-- /CONFIDENTIAL -->", text)

    # ----- diff -----

    def test_diff_new_changed_and_unchanged(self):
        self.write()
        listing = [
            {"id": "5500231", "title": "Partner API rollout plan", "version": 1, "lastModified": "2026-11-03T09:00:00Z"},
            {"id": "5500999", "title": "Brand new page", "version": 1, "lastModified": "2026-11-04T09:00:00Z"},
        ]
        r = W.run_json(self.root, SYNC, "diff", "--listing", self.payload("l", listing))
        self.assertEqual([(p["id"], p["reason"]) for p in r["to_fetch"]], [("5500999", "new")])
        self.assertEqual(r["unchanged"], 1)
        listing[0]["version"] = 2
        r = W.run_json(self.root, SYNC, "diff", "--listing", self.payload("l", listing))
        self.assertEqual([(p["id"], p["reason"]) for p in r["to_fetch"]], [("5500231", "version_changed"), ("5500999", "new")])

    def test_diff_falls_back_to_last_modified_without_version(self):
        self.write()
        listing = [{"id": "5500231", "title": "x", "lastModified": "2026-11-06T16:00:00Z"}]
        r = W.run_json(self.root, SYNC, "diff", "--listing", self.payload("l", listing))
        self.assertEqual(r["to_fetch"][0]["reason"], "modified")

    def test_diff_caps_at_max_pages_and_dedupes_listing(self):
        cfg = json.loads(TEMPLATE.read_text())
        cfg["max_pages_per_run"] = 2
        (self.root / ".claude/brain/confluence-watch.json").write_text(json.dumps(cfg))
        listing = [{"id": str(i), "title": f"p{i}", "version": 1, "lastModified": "2026-11-04T09:00:00Z"} for i in (1, 2, 3, 3)]
        r = W.run_json(self.root, SYNC, "diff", "--listing", self.payload("l", listing))
        self.assertEqual(len(r["to_fetch"]), 2)
        self.assertEqual(r["deferred"], 1)

    # ----- plan / finish -----

    def test_plan_builds_queries_from_config(self):
        r = W.run_json(self.root, SYNC, "plan")
        names = [q["name"] for q in r["queries"]]
        self.assertEqual(names, ["space-PROD", "labels", "partner-api-docs"])
        self.assertTrue(r["first_run"])
        self.assertIn(f'lastmodified >= "{r["since"]}"', r["queries"][0]["cql"])
        self.assertNotIn("{since}", r["queries"][2]["cql"])
        self.assertIn('label in ("prd", "decision")', r["queries"][1]["cql"])

    def test_finish_stamps_last_sync_and_plan_narrows(self):
        self.write()
        W.run_json(self.root, SYNC, "finish")
        r = W.run_json(self.root, SYNC, "plan")
        self.assertFalse(r["first_run"])
        self.assertIsNotNone(self.state()["last_sync"])

    def test_write_does_not_stamp_last_sync(self):
        self.write()
        self.assertIsNone(self.state()["last_sync"])  # only `finish` marks a fully successful run

    def test_empty_watch_config_gives_no_queries(self):
        (self.root / ".claude/brain/confluence-watch.json").write_text("{}")
        self.assertEqual(W.run_json(self.root, SYNC, "plan")["queries"], [])


if __name__ == "__main__":
    unittest.main()
