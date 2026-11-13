import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helpers  # noqa: E402

W45 = Path("raw/slack/2026/2026-W45")


class SlackBricks(unittest.TestCase):
    def setUp(self):
        self.ws = helpers.make_workspace()

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def format_channel(self, fixture):
        return helpers.result(helpers.run("channel", self.ws, "--payload", helpers.stage_payload(self.ws, fixture)))

    def test_formatter_output_matches_committed_sample(self):
        helpers.build_sample(self.ws)
        committed = sorted(p.relative_to(helpers.SAMPLE_SLACK) for p in helpers.SAMPLE_SLACK.rglob("*.md"))
        produced = sorted(p.relative_to(self.ws / "raw" / "slack") for p in (self.ws / "raw" / "slack").rglob("*.md"))
        self.assertEqual(committed, produced)
        self.assertEqual(len(produced), 5)
        for rel in produced:
            self.assertEqual((helpers.SAMPLE_SLACK / rel).read_text(), (self.ws / "raw" / "slack" / rel).read_text(), rel)

    def test_channel_file_shape_and_payload_consumed(self):
        out = self.format_channel("proj-checkout-2026-11-03.json")
        self.assertEqual((out["messages_added"], out["files_written"]),
                         (3, ["raw/slack/2026/2026-W45/slack-2026-11-03-proj-checkout.md"]))
        text = (self.ws / W45 / "slack-2026-11-03-proj-checkout.md").read_text()
        self.assertIn("wiki_processed: false", text)
        self.assertIn("message_count: 3", text)
        self.assertIn("thread_count: 1", text)
        self.assertIn("> permalink: https://fernhill.slack.com/archives/C0FERN0001/p1793697240000100", text)
        self.assertIn("## 09:14 — Sam Patel", text)
        self.assertIn("### Thread (2 replies)", text)
        self.assertFalse((self.ws / "system/run/payloads/proj-checkout-2026-11-03.json").exists())

    def test_verbatim_warnings_fire_on_summarised_payload(self):
        out = self.format_channel("summarised-2026-11-03.json")
        self.assertEqual(len(out["verbatim_warnings"]), 2)
        self.assertTrue(any("bracketed" in w for w in out["verbatim_warnings"]))
        self.assertTrue(any("ellipsis" in w for w in out["verbatim_warnings"]))

    def test_clean_payload_has_no_warnings(self):
        self.assertEqual(self.format_channel("proj-checkout-2026-11-03.json")["verbatim_warnings"], [])

    def test_payload_missing_ts_rejected_and_nothing_written(self):
        bad = self.ws / "system/run/payloads/bad.json"
        bad.write_text(json.dumps({"channel_name": "#proj-checkout", "date": "2026-11-03",
                                   "messages": [{"text": "only text"}]}))
        proc = helpers.run("channel", self.ws, "--payload", "system/run/payloads/bad.json", check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("missing required fields", proc.stderr)
        self.assertFalse((self.ws / "raw/slack").exists() and any((self.ws / "raw/slack").rglob("*.md")))

    def test_rerun_dedupes_by_message_ts(self):
        self.format_channel("proj-checkout-2026-11-03.json")
        again = self.format_channel("proj-checkout-2026-11-03.json")
        self.assertEqual(again["messages_added"], 0)
        text = (self.ws / W45 / "slack-2026-11-03-proj-checkout.md").read_text()
        self.assertEqual(text.count("## 09:14 — Sam Patel"), 1)

    def test_merge_appends_and_resets_flag(self):
        self.format_channel("proj-checkout-2026-11-03.json")
        f = self.ws / W45 / "slack-2026-11-03-proj-checkout.md"
        f.write_text(f.read_text().replace("wiki_processed: false", "wiki_processed: true"))
        data = json.loads((helpers.FIXTURES / "proj-checkout-2026-11-03.json").read_text())
        data["messages"] = [{"ts": "1793725000.000900", "user_name": "Sam Patel", "text": "One more."}]
        p = self.ws / "system/run/payloads/more.json"
        p.write_text(json.dumps(data))
        out = helpers.result(helpers.run("channel", self.ws, "--payload", "system/run/payloads/more.json"))
        self.assertEqual(out["messages_added"], 1)
        text = f.read_text()
        self.assertIn("wiki_processed: false", text)
        self.assertIn("message_count: 4", text)
        self.assertIn("## Additional messages", text)

    def test_overlap_message_filed_under_its_own_day(self):
        data = {"channel_name": "#partner-api", "date": "2026-11-05", "messages": [
            {"ts": "1793802120.000200", "user_name": "Riley Chen", "text": "posted on the 4th"}]}
        (self.ws / "system/run/payloads/p.json").write_text(json.dumps(data))
        out = helpers.result(helpers.run("channel", self.ws, "--payload", "system/run/payloads/p.json"))
        self.assertEqual(out["files_written"], ["raw/slack/2026/2026-W45/slack-2026-11-04-partner-api.md"])
        ledger = json.loads((self.ws / "system/run/slack-channel-ledger.json").read_text())
        self.assertEqual(ledger["2026-11-05"]["partner-api"]["messages"], 0)

    def test_confidential_channel_wrapped(self):
        out = self.format_channel("product-leads-2026-11-04.json")
        self.assertTrue(out["confidential"])
        text = (self.ws / W45 / "slack-2026-11-04-product-leads.md").read_text()
        self.assertIn("sensitivity: confidential", text)
        self.assertIn("redact_content: true", text)
        self.assertEqual(text.count("<!-- CONFIDENTIAL: redact-on-share -->"), 3)
        self.assertEqual(text.count("<!-- /CONFIDENTIAL -->"), 3)

    def test_confidential_by_name_pattern_even_if_config_says_internal(self):
        cfg = self.ws / ".claude/brain/slack-channels.json"
        data = json.loads(cfg.read_text())
        next(c for c in data["channels"] if c["name"] == "#product-leads")["sensitivity"] = "internal"
        cfg.write_text(json.dumps(data))
        self.assertTrue(self.format_channel("product-leads-2026-11-04.json")["confidential"])

    def test_internal_channel_not_wrapped(self):
        self.format_channel("product-team-2026-11-05.json")
        self.assertNotIn("CONFIDENTIAL", (self.ws / W45 / "slack-2026-11-05-product-team.md").read_text())

    def test_flagged_ledger_dedupes_by_permalink(self):
        args = ("--date", "2026-11-06")
        first = helpers.result(helpers.run("flagged", self.ws, "--payload",
                                           helpers.stage_payload(self.ws, "flagged-2026-11-06.json"), *args))
        self.assertEqual((first["messages_added"], first["already_ingested"]), (2, 0))
        second = helpers.result(helpers.run("flagged", self.ws, "--payload",
                                            helpers.stage_payload(self.ws, "flagged-2026-11-06.json"), "--date", "2026-11-09"))
        self.assertEqual((second["messages_added"], second["already_ingested"], second["file"]), (0, 2, None))
        self.assertFalse((self.ws / "raw/slack/2026/2026-W46").exists())
        ledger = json.loads((self.ws / "system/run/slack-flagged-ledger.json").read_text())
        self.assertEqual(len(ledger), 2)

    def test_flagged_duplicate_inside_one_batch(self):
        data = json.loads((helpers.FIXTURES / "flagged-2026-11-06.json").read_text())
        data["messages"].append(dict(data["messages"][0]))
        (self.ws / "system/run/payloads/f.json").write_text(json.dumps(data))
        out = helpers.result(helpers.run("flagged", self.ws, "--payload", "system/run/payloads/f.json", "--date", "2026-11-06"))
        self.assertEqual((out["messages_added"], out["already_ingested"]), (2, 1))

    def test_flagged_uses_configured_emoji_and_confidential_wrapping(self):
        cfg = self.ws / ".claude/brain/slack-config.json"
        data = json.loads(cfg.read_text())
        data["flag_reaction"] = "bookmark"
        cfg.write_text(json.dumps(data))
        flagged = {"messages": [{"permalink": "https://fernhill.slack.com/archives/C0FERN0004/p1793811900000100",
                                 "channel_name": "#product-leads", "author": "Morgan Diaz",
                                 "text": "Private planning note.", "signal_quality": "high"}]}
        (self.ws / "system/run/payloads/f.json").write_text(json.dumps(flagged))
        helpers.run("flagged", self.ws, "--payload", "system/run/payloads/f.json", "--date", "2026-11-06")
        text = (self.ws / W45 / "slack-2026-11-06-slack-ingest.md").read_text()
        self.assertIn("sensitivity: confidential", text)
        self.assertIn("<!-- CONFIDENTIAL: redact-on-share -->", text)
        self.assertIn(":bookmark:", text)

    def test_flagged_rejects_payload_without_permalink(self):
        (self.ws / "system/run/payloads/f.json").write_text(json.dumps({"messages": [{"text": "x"}]}))
        proc = helpers.run("flagged", self.ws, "--payload", "system/run/payloads/f.json", "--date", "2026-11-06", check=False)
        self.assertEqual(proc.returncode, 2)

    def test_owed_replies_digest(self):
        items = [
            {"kind": "dm", "permalink": "https://fernhill.slack.com/archives/D1/p1", "channel": "DM", "author": "Sam Patel", "ts": "1793700000.0", "text": "Can you review the spec?"},
            {"kind": "dm", "permalink": "https://fernhill.slack.com/archives/D1/p1", "channel": "DM", "author": "Sam Patel", "ts": "1793700000.0", "text": "dup"},
            {"kind": "mention", "permalink": "https://fernhill.slack.com/archives/C0FERN0004/p2", "channel": "#product-leads", "author": "Riley Chen", "ts": "1793800000.0", "text": "Alex, thoughts on staffing?"},
        ]
        (self.ws / "system/run/payloads/o.json").write_text(json.dumps(items))
        out = helpers.result(helpers.run("owed", self.ws, "--payload", "system/run/payloads/o.json", "--date", "2026-11-06"))
        self.assertEqual(out["by_kind"], {"mention": 1, "dm": 1})
        text = (self.ws / "inbox/owed-replies/2026-11-06-owed-replies.md").read_text()
        self.assertIn("count: 2", text)
        self.assertEqual(text.count("<!-- CONFIDENTIAL: redact-on-share -->"), 1)

    def test_owed_replies_refuses_bad_input(self):
        (self.ws / "system/run/payloads/o.json").write_text('{"not": "an array"}')
        proc = helpers.run("owed", self.ws, "--payload", "system/run/payloads/o.json", check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse((self.ws / "inbox/owed-replies").exists() and any((self.ws / "inbox/owed-replies").iterdir()))

    def test_ledger_coverage_and_empty_day(self):
        helpers.run("channel", self.ws, "--empty", "--channel", "#proj-checkout", "--date", "2026-11-03")
        cov = helpers.result(helpers.run("ledger", self.ws, "--coverage", "--dates", "2026-11-03,2026-11-07"))
        self.assertEqual(cov["dates_partial"], ["2026-11-03"])  # other channels missing; Saturday exempt
        for ch in ("#partner-api", "#product-team", "#product-leads"):
            helpers.run("channel", self.ws, "--empty", "--channel", ch, "--date", "2026-11-03")
        cov = helpers.result(helpers.run("ledger", self.ws, "--coverage", "--dates", "2026-11-03"))
        self.assertEqual(cov["dates_partial"], [])  # transient channel does not count

    def test_fetch_plan_and_set_id(self):
        run_ctx = self.ws / "system/run/run-context.json"
        run_ctx.write_text(json.dumps({"slack": {"window": {"2026-11-03": {"oldest_ts": "1", "latest_ts": "2"}}}}))
        plan = helpers.result(helpers.run("plan", self.ws, "--date", "2026-11-03"))
        self.assertEqual((plan["oldest_ts"], plan["latest_ts"], len(plan["channels"])), ("1", "2", 5))
        self.assertEqual(plan["channels_missing_id"], [])
        self.assertTrue(next(c for c in plan["channels"] if c["slug"] == "product-leads")["confidential"])
        self.assertEqual(helpers.run("plan", self.ws, "--date", "2026-12-01", check=False).returncode, 2)
        cfg = self.ws / ".claude/brain/slack-channels.json"
        data = json.loads(cfg.read_text())
        data["channels"][0]["id"] = ""
        cfg.write_text(json.dumps(data))
        self.assertEqual(helpers.result(helpers.run("plan", self.ws, "--date", "2026-11-03"))["channels_missing_id"], ["#proj-checkout"])
        helpers.run("plan", self.ws, "--set-id", "#proj-checkout", "C0FERN0009")
        self.assertEqual(json.loads(cfg.read_text())["channels"][0]["id"], "C0FERN0009")


if __name__ == "__main__":
    unittest.main()
