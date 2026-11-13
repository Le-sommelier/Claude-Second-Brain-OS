import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws import REPO, SAMPLE, make_workspace, run, write  # noqa: E402

S = REPO / "plugins" / "brain-digests" / "skills"
VALIDATE = S / "weekly-digest" / "scripts" / "validate_weekly_digest.py"
RUN = S / "weekly-digest" / "scripts" / "run_weekly_recap.py"
ROLLUP = S / "monthly-digest" / "scripts" / "rollup.py"
PUBLISH = S / "publish-digest" / "scripts" / "check_publishable.py"
TITLES = "Checkout revamp,Partner API"

LOG = """# Risks

## 2026-10-12 · RSK-001 · open
by: ai · trust: high · source: mtg-2026-10-12-x · owner: sam-patel
Sandbox drops requests during end-to-end tests.

## 2026-10-20 · RSK-002 · open
by: ai · trust: low · source: slack-2026-10-20-product-leads · sensitivity: confidential
Staffing for next half is undecided, names withheld.

## 2026-09-30 · RSK-000 · closed
by: human · source: alex-morgan
September item.
"""


def fixture_projects(root):
    write(root, "projects/checkout-revamp/README.md", "---\ntitle: Checkout revamp\n---\n# Checkout revamp\n")
    write(root, "projects/checkout-revamp/risks.md", LOG)
    write(root, "projects/checkout-revamp/status.md", "# Status\n\n## 2026-10-15 · STA-001 · on-track\nby: ai · trust: high · source: mtg-1 · rag: green\nQA passed.\n")
    write(root, "projects/checkout-revamp/decisions/2026-10-14-flag.md",
          "---\nid: DEC-checkout-revamp-001\ndate: 2026-10-14\nstatus: accepted\nby: ai-confirmed\ntrust: high\ntitle: Keep old checkout behind a flag\n---\nbody\n")
    write(root, "projects/partner-api/README.md", "# Partner API\n")
    write(root, "projects/partner-api/milestones.md", "# Milestones\n\n## 2026-10-25 · MS-001 · done\nby: ai · trust: medium · source: mtg-2\nBeta partners signed.\n")


class ValidatorTests(unittest.TestCase):
    def test_sample_weekly_digest_passes(self):
        root = make_workspace(("digests/weekly/2026-W45.md",))
        r = run(VALIDATE, root, "--digest", "digests/weekly/2026-W45.md", "--project-titles", TITLES)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(json.loads(r.stdout)["errors"], [])

    def test_failures(self):
        root = make_workspace()
        bad = ("# Weekly Digest\n\n**Week:** `YYYY-Www`\n\n## Overview\nOngoing.\n\n## Project status\n| Checkout revamp | | |\n\n## Sources\n"
               "<!-- CONFIDENTIAL: redact-on-share -->\n")
        write(root, "digests/weekly/x.md", bad)
        r = run(VALIDATE, root, "--digest", "digests/weekly/x.md", "--project-titles", TITLES)
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        text = " ".join(out["errors"])
        for needle in ("placeholder", "Partner API", "confidential markers"):
            self.assertIn(needle, text)
        self.assertTrue(any("vague" in w for w in out["warnings"]))


class WeeklyRunTests(unittest.TestCase):
    def test_manifest_from_sample(self):
        root = make_workspace(("raw/meetings/2026/2026-W45", "raw/slack/2026/2026-W45"))
        fixture_projects(root)
        r = run(RUN, root, "--week", "2026-W45")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        m = json.loads(r.stdout)
        self.assertEqual(m["summaries_count"], 2)
        self.assertEqual(m["output_path"], "digests/weekly/2026-W45.md")
        self.assertTrue(any(s["confidential"] for s in m["slack_files"]))
        self.assertEqual({p["slug"] for p in m["projects"]}, {"checkout-revamp", "partner-api"})
        self.assertEqual([p for p in m["projects"] if p["slug"] == "checkout-revamp"][0]["current_rag"], "green")

    def test_hard_stop_when_empty(self):
        root = make_workspace()
        r = run(RUN, root, "--week", "2026-W45")
        self.assertEqual(r.returncode, 3)
        self.assertTrue(json.loads(r.stdout)["requires_user_confirmation"])


class RollupTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        fixture_projects(self.root)

    def test_rollup_writes_redacts_and_is_idempotent(self):
        r = run(ROLLUP, self.root, "--month", "2026-10")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["counts"]["written"], 3)
        text = (self.root / "projects/checkout-revamp/rollups/2026-10.md").read_text()
        self.assertIn("`RSK-001` 2026-10-12 open", text)
        self.assertIn("`RSK-002` 2026-10-20 open: (confidential, see source)", text)
        self.assertNotIn("names withheld", text)
        self.assertNotIn("September item", text)
        self.assertIn("Decisions: 1 (1 accepted, 0 proposed).", text)
        digest = (self.root / "digests/monthly/2026-10.md").read_text()
        self.assertIn("**Partner API**", digest)
        again = json.loads(run(ROLLUP, self.root, "--month", "2026-10").stdout)["counts"]
        self.assertEqual((again["written"], again["unchanged"]), (0, 3))

    def test_handwritten_file_is_not_replaced(self):
        write(self.root, "digests/monthly/2026-10.md", "# My own October notes\n")
        counts = json.loads(run(ROLLUP, self.root, "--month", "2026-10").stdout)["counts"]
        self.assertEqual(counts["skipped_handwritten"], 1)
        self.assertEqual((self.root / "digests/monthly/2026-10.md").read_text(), "# My own October notes\n")

    def test_default_window_and_backfill(self):
        out = json.loads(run(ROLLUP, self.root, "--today", "2026-11-13", "--dry-run").stdout)
        self.assertEqual(out["months"], ["2026-10", "2026-11"])
        out = json.loads(run(ROLLUP, self.root, "--backfill", "--dry-run").stdout)
        self.assertEqual(out["months"], ["2026-09", "2026-10"])
        self.assertFalse((self.root / "digests/monthly").exists())

    def test_sample_monthly_digest_is_rollup_shaped(self):
        text = (SAMPLE / "digests/monthly/2026-10.md").read_text()
        self.assertIn("<!-- generated by brain rollup; do not edit -->", text)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace(("digests/weekly/2026-W45.md",))

    def cfg(self, dest="confluence", parent="123"):
        write(self.root, ".claude/brain/digests.json", json.dumps({"publish": {"destination": dest, "confluence": {"space": "PROD", "parent_page_id": parent,
              "title_template": "Weekly digest {period} (week ending {week_end})"}}}))

    def test_ok(self):
        self.cfg()
        r = run(PUBLISH, self.root, "--period", "2026-W45")
        out = json.loads(r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(out["title"], "Weekly digest 2026-W45 (week ending 2026-11-08)")

    def test_blocks(self):
        r = run(PUBLISH, self.root, "--period", "2026-W45")  # no destination configured
        self.assertEqual(r.returncode, 1)
        self.assertIn("No publish destination", r.stdout)
        self.cfg(parent="")
        self.assertIn("parent_page_id", run(PUBLISH, self.root, "--period", "2026-W45").stdout)
        self.cfg()
        self.assertEqual(run(PUBLISH, self.root, "--period", "2026-W46").returncode, 1)
        write(self.root, "digests/weekly/2026-W45.md", "---\nsensitivity: confidential\n---\n# Weekly Digest 2026-W45\n")
        self.assertIn("confidential", run(PUBLISH, self.root, "--period", "2026-W45").stdout)


if __name__ == "__main__":
    unittest.main()
