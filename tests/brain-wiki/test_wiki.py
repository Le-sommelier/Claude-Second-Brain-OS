import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ws import REPO, make_workspace, run, write  # noqa: E402

S = REPO / "plugins" / "brain-wiki" / "skills"
VALIDATE = S / "wiki-update" / "scripts" / "validate_facets.py"
STALE = S / "stale-pruner" / "scripts" / "find_stale.py"
CONFLICTS = S / "contradiction-resolver" / "scripts" / "find_conflicts.py"

RISKS = """# Risks

## 2026-08-01 · RSK-001 · open
by: ai · trust: high · source: mtg-2026-08-01-x · owner: sam-patel
Partner rate limits are undefined and could block the beta launch.

## 2026-10-30 · RSK-002 · open
by: human · source: alex-morgan
Payment sandbox drops requests during end-to-end tests.

## 2026-09-01 · RSK-003 · open
by: ai · trust: high · source: mtg-2026-09-01-y
Rate limits for partners are not defined, which could block the beta launch.

## 2026-10-02 · RSK-003 · closed
by: ai · trust: high · source: mtg-2026-10-02-y
Resolved.

<!-- human -->
## 2026-01-01 · RSK-009 · open
by: human · source: alex-morgan
Fenced private note.
<!-- /human -->
"""
STATUS = """# Status

## 2026-11-02 · STA-001 · on-track
by: ai · trust: high · source: mtg-a · rag: green
Design done.

## 2026-11-04 · STA-002 · at-risk
by: ai · trust: medium · source: mtg-b · rag: amber
Design blocked on legal.
"""


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        write(self.root, "projects/partner-api/risks.md", RISKS)
        write(self.root, "projects/partner-api/status.md", STATUS)
        write(self.root, "projects/partner-api/decisions/2026-10-01-limit.md",
              "---\nid: DEC-partner-api-001\ndate: 2026-10-01\nstatus: proposed\nby: ai\ntitle: Default rate limit\n---\nbody\n")

    def payload(self, items):
        return write(self.root, "system/run/payloads/f.json", json.dumps(items))

    def test_validate_ok_and_errors(self):
        good = [{"facet": "risks", "prefix": "RSK", "date": "2026-11-05", "state": "open", "body": "New risk.", "source": ["mtg-1"]},
                {"type": "decision", "date": "2026-11-05", "title": "T", "body": "B", "source": ["mtg-1"]}]
        self.payload(good)
        r = run(VALIDATE, self.root, "--project", "partner-api", "--file", "system/run/payloads/f.json")
        self.assertEqual(r.returncode, 0, r.stdout)
        bad = [{"facet": "risks", "prefix": "MS", "date": "2026-11-05", "state": "weird", "body": "x", "source": []},
               {"facet": "status", "prefix": "STA", "date": "2026-11-05", "state": "open", "body": "x", "source": ["a"]},
               {"facet": "risks", "prefix": "RSK", "id": "RSK-099", "date": "2026-11-05", "state": "open", "body": "x", "source": ["a"]},
               {"facet": "risks", "prefix": "RSK", "date": "2026-11-05", "state": "open", "body": 'He said "no hires"', "source": ["slack-leads"]},
               {"type": "decision", "date": "2026-11-05", "title": "T", "body": "B", "source": ["slack-leads"]}]
        self.payload(bad)
        r = run(VALIDATE, self.root, "--project", "partner-api", "--file", "system/run/payloads/f.json", "--confidential-sources", "slack-leads")
        self.assertEqual(r.returncode, 1)
        errs = " ".join(json.loads(r.stdout)["errors"])
        for needle in ("facet/prefix", "bad state", "source is mandatory", "rag", "unknown ID", "quotes text", "confidential source"):
            self.assertIn(needle, errs)

    def test_stale_uses_latest_state_and_skips_fences(self):
        out = json.loads(run(STALE, self.root, "--today", "2026-11-13", "--days", "21").stdout)
        ids = {c["id"] for c in out["candidates"]}
        self.assertIn("RSK-001", ids)          # open since August
        self.assertNotIn("RSK-003", ids)       # latest state closed
        self.assertNotIn("RSK-002", ids)       # recent
        self.assertNotIn("RSK-009", ids)       # human fence
        self.assertIn("DEC-partner-api-001", ids)  # proposed decision aged out

    def test_conflicts(self):
        out = json.loads(run(CONFLICTS, self.root).stdout)
        kinds = {(c["kind"], tuple(c["ids"])) for c in out["candidates"]}
        self.assertIn(("rag-split", ("STA-001", "STA-002")), kinds)
        # logs are never modified
        self.assertEqual((self.root / "projects/partner-api/risks.md").read_text(), RISKS)

    def test_resolved_open(self):
        write(self.root, "projects/partner-api/risks.md", RISKS + "\n## 2026-11-03 · RSK-010 · closed\nby: ai · trust: high · source: mtg-z · refs: RSK-002\nDone.\n")
        out = json.loads(run(CONFLICTS, self.root).stdout)
        self.assertTrue(any(c["kind"] == "resolved-open" and c["ids"] == ["RSK-002", "RSK-010"] for c in out["candidates"]))


if __name__ == "__main__":
    unittest.main()
