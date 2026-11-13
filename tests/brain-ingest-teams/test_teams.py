"""Tests for brain-ingest-teams: VTT parsing, attendance, cross-route dedupe, ledger, window maths, saving."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wsutil_teams as W  # noqa: E402

sys.path.insert(0, str(W.REPO / "lib"))
_spec = importlib.util.spec_from_file_location("prepare", W.script("ingest-meeting-files", "prepare.py"))
prepare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare)

PREPARE = W.script("ingest-meeting-files", "prepare.py")
LEDGER = W.script("ingest-teams", "ledger.py")
WINDOW = W.script("ingest-teams", "event_window_utc.py")
SAVE = W.script("ingest-teams", "save_transcript.py")
SAMPLE_VTT = "inbox/transcripts/2026-11-05 14.00.00 Partner API sync.vtt"

VTT = """WEBVTT

id-1/1-0
00:00:01.000 --> 00:00:04.000
<v Sam Patel>First line
continues here.</v>

id-1/2-0
00:00:05.000 --> 00:00:07.000
<v Sam Patel>Same speaker again.</v>

id-1/3-0
00:00:08.000 --> 00:00:09.000
<v Taylor Brooks>Different speaker.</v>
"""


def vtt_for(speakers: list[str], marker: str = "") -> str:
    cues = [f"id/{i}-0\n00:00:{i:02d}.000 --> 00:00:{i + 1:02d}.000\n<v {s}>Line {i} {marker}</v>\n" for i, s in enumerate(speakers, 1)]
    return "WEBVTT\n\n" + "\n".join(cues)


def make_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


class VttParsing(unittest.TestCase):
    def test_turns_are_merged_per_speaker(self):
        self.assertEqual(prepare.vtt_to_text(VTT).splitlines(),
                         ["Sam Patel: First line continues here. Same speaker again.", "Taylor Brooks: Different speaker."])

    def test_headers_timings_and_cue_ids_dropped(self):
        text = prepare.vtt_to_text(VTT)
        self.assertNotIn("-->", text)
        self.assertNotIn("WEBVTT", text)
        self.assertNotIn("id-1/1-0", text)

    def test_filename_patterns(self):
        from datetime import datetime
        fb = datetime(2020, 1, 1)
        self.assertEqual(prepare.parse_name("2026-11-05 14.00.00 Partner API sync", fb), (datetime(2026, 11, 5, 14, 0), "Partner API sync"))
        self.assertEqual(prepare.parse_name("2026-11-05_14-30_Design review", fb), (datetime(2026, 11, 5, 14, 30), "Design review"))
        self.assertEqual(prepare.parse_name("2026-11-05 Retro", fb)[1], "Retro")
        self.assertEqual(prepare.parse_name("untitled", fb), (fb, "untitled"))

    def test_person_matching(self):
        self.assertEqual(prepare.person_slug("Morgan, Alex (Fernhill)"), "alex-morgan")
        self.assertEqual(prepare.person_slug("Alex Morgan"), "alex-morgan")


class Ingest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name, copy=(SAMPLE_VTT,))

    def run_prepare(self, *args):
        return W.run_json(self.root, PREPARE, *args)

    def drop(self, name: str, text: str, folder: str = "inbox/transcripts") -> Path:
        p = self.root / folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def raws(self):
        return sorted(self.root.glob("raw/meetings/*/*/mtg-*.md"))

    def test_sample_vtt_becomes_raw_with_flags_and_attendance(self):
        r = self.run_prepare()
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["counts"]["drop"], 1)
        out = self.root / r["outputs"][0]
        self.assertEqual(out.name, "mtg-2026-11-05-partner-api-sync.md")
        self.assertEqual(out.parent.name, "2026-W45")
        fm = prepare.frontmatter.read(out)
        self.assertEqual(fm["wiki_processed"], False)
        self.assertEqual(fm["todo_processed"], False)
        self.assertEqual(fm["attendance"], "attended")  # Alex Morgan speaks
        self.assertEqual(fm["participants"], ["Alex Morgan", "Sam Patel", "Taylor Brooks"])
        self.assertEqual(fm["id"], out.stem)
        self.assertIn("Sam Patel: Engineering can have the sandbox", out.read_text())
        self.assertTrue((self.root / "inbox/transcripts/_processed" / Path(SAMPLE_VTT).name).exists())
        self.assertFalse((self.root / SAMPLE_VTT).exists())

    def test_second_run_is_idle(self):
        self.run_prepare()
        again = self.run_prepare()
        self.assertEqual(again["status"], "skipped")
        self.assertEqual(len(self.raws()), 1)

    def test_dry_run_changes_nothing(self):
        r = self.run_prepare("--dry-run")
        self.assertTrue(r["dry_run"])
        self.assertEqual(self.raws(), [])
        self.assertTrue((self.root / SAMPLE_VTT).exists())

    def test_attendance_invited_absent_and_not_invited(self):
        self.drop("2026-11-04 10.00.00 Design review.vtt", vtt_for(["Jordan Lee", "Sam Patel"]), "inbox/transcripts/teams")
        (self.root / "inbox/transcripts/teams/2026-11-04 10.00.00 Design review.meta.json").write_text(json.dumps({"invited": ["Alex Morgan", "Jordan Lee"]}))
        self.drop("2026-11-04 15.00.00 Data sync.vtt", vtt_for(["Taylor Brooks", "Casey Nguyen"], "x"), "inbox/transcripts/teams")
        self.run_prepare()
        by_id = {f.stem: prepare.frontmatter.read(f) for f in self.raws()}
        self.assertEqual(by_id["mtg-2026-11-04-design-review"]["attendance"], "invited-absent")
        self.assertEqual(by_id["mtg-2026-11-04-data-sync"]["attendance"], "not-invited")
        self.assertTrue((self.root / "inbox/transcripts/_processed/2026-11-04 10.00.00 Design review.meta.json").exists())

    def test_dedupe_same_run_m365_wins(self):
        speakers = ["Alex Morgan", "Sam Patel"]
        self.drop("2026-11-05 14.00.00 Partner API sync.vtt", vtt_for(speakers, "teams"), "inbox/transcripts/teams")
        # same meeting from a recorder: different title, starts 3 minutes later, different text
        self.drop("2026-11-05_14-03_Partner-API-weekly.txt", "Alex Morgan: hello\nSam Patel: hi")
        (self.root / SAMPLE_VTT).unlink()
        r = self.run_prepare()
        self.assertEqual(r["counts"]["m365"], 1)
        self.assertEqual(r["counts"]["duplicates"], 1)
        raws = self.raws()
        self.assertEqual(len(raws), 1)
        self.assertEqual(prepare.frontmatter.read(raws[0])["origin"], "m365")
        self.assertTrue(list(raws[0].parent.glob("duplicates/*.txt")))
        self.assertTrue(any("duplicate" in o for o in r["observations"]))

    def test_dedupe_drop_already_ingested_then_m365_arrives(self):
        self.drop("2026-11-05_14-03_Partner-API-weekly.txt", "Alex Morgan: first copy\nSam Patel: hi")
        self.run_prepare()
        first = self.raws()
        self.assertEqual(len(first), 1)
        self.assertEqual(prepare.frontmatter.read(first[0])["origin"], "drop")
        self.drop("2026-11-05 14.00.00 Partner API sync.vtt", vtt_for(["Alex Morgan"], "teams"), "inbox/transcripts/teams")
        r = self.run_prepare()
        self.assertEqual(r["counts"]["duplicates"], 1)
        raws = self.raws()
        self.assertEqual([prepare.frontmatter.read(f)["origin"] for f in raws], ["m365"])
        moved = list(raws[0].parent.glob("duplicates/mtg-*.md"))
        self.assertEqual(len(moved), 1)  # the hand-dropped raw moved, nothing deleted
        index = json.loads((raws[0].parent / "_origin.json").read_text())
        self.assertEqual([v["origin"] for v in index.values()], ["m365"])

    def test_dedupe_drop_after_m365_goes_to_duplicates(self):
        self.drop("2026-11-05 14.00.00 Partner API sync.vtt", vtt_for(["Alex Morgan"], "teams"), "inbox/transcripts/teams")
        self.run_prepare()
        self.drop("2026-11-05 14.01.00 Partner API sync.txt", "Alex Morgan: from the recorder")
        r = self.run_prepare()
        self.assertEqual(r["counts"]["duplicates"], 1)
        self.assertEqual(r["counts"]["drop"], 0)
        self.assertEqual(len(self.raws()), 1)

    def test_identical_text_is_a_duplicate_even_with_other_title(self):
        (self.root / SAMPLE_VTT).unlink()
        self.drop("2026-11-04 09.00.00 Alpha.txt", "Alex Morgan: same words")
        self.run_prepare()
        self.drop("2026-11-04 17.00.00 Beta.txt", "Alex Morgan: same words")
        r = self.run_prepare()
        self.assertEqual(r["counts"]["duplicates"], 1)
        self.assertEqual(len(self.raws()), 1)

    def test_different_meetings_same_day_are_kept(self):
        (self.root / SAMPLE_VTT).unlink()
        self.drop("2026-11-04 09.00.00 Alpha.txt", "Alex Morgan: one")
        self.drop("2026-11-04 15.00.00 Beta.txt", "Alex Morgan: two")
        r = self.run_prepare()
        self.assertEqual(r["counts"]["drop"], 2)
        self.assertEqual(len(self.raws()), 2)

    def test_never_overwrites_existing_raw(self):
        week = self.root / "raw/meetings/2026/2026-W45"
        week.mkdir(parents=True)
        legacy = week / "mtg-2026-11-06-legacy-sync.md"  # hand-made file the origin index knows nothing about
        legacy.write_text("hand written, must survive")
        self.drop("2026-11-06 09.00.00 Legacy sync.txt", "Alex Morgan: a new recording")
        self.run_prepare()
        self.assertEqual(legacy.read_text(), "hand written, must survive")
        self.assertTrue((week / "mtg-2026-11-06-legacy-sync-2.md").exists())

    def test_docx_with_speaker_headers(self):
        make_docx(self.root / "inbox/transcripts/2026-11-03 11.00.00 Retro.docx",
                  ["Alex Morgan   0:03", "Welcome everyone.", "Casey Nguyen   0:20", "Thanks for the notes."])
        self.run_prepare()
        text = next(f for f in self.raws() if "retro" in f.name).read_text()
        self.assertIn("Alex Morgan: Welcome everyone.", text)
        self.assertIn("Casey Nguyen: Thanks for the notes.", text)

    def test_empty_vtt_left_in_inbox_with_warning(self):
        p = self.drop("2026-11-03 09.00.00 Empty.vtt", "WEBVTT\n\n")
        r = self.run_prepare()
        self.assertTrue(p.exists())
        self.assertTrue(any("no speech" in w for w in r["warnings"]))

    def test_corrupt_origin_index_blocks_writes(self):
        self.run_prepare()
        week = self.raws()[0].parent
        (week / "_origin.json").write_text("{not json")
        self.drop("2026-11-05 20.00.00 Late.txt", "Alex Morgan: hi")
        r = self.run_prepare()
        self.assertEqual(r["status"], "partial")
        self.assertEqual(len(self.raws()), 1)


class LedgerAndWindow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name)

    def ledger(self, *args):
        return W.run_json(self.root, LEDGER, *args)

    def test_first_window_uses_lookback_then_overlap(self):
        first = self.ledger("--window")
        self.assertIsNone(first["last_run"])
        self.ledger("--set-last-run", "2026-11-05T12:00:00+00:00")
        self.assertEqual(self.ledger("--window")["since"], "2026-11-04T12:00:00Z")

    def test_retry_policy(self):
        start = "2999-01-01T10:00:00+00:00"  # far future so the retry window never expires
        self.assertTrue(self.ledger("--should-attempt", "--event-id", "e1", "--start", start)["should_attempt"])
        self.ledger("--record", "--event-id", "e1", "--subject", "S", "--start", start, "--status", "transcripts_empty")
        self.assertEqual(self.ledger("--should-attempt", "--event-id", "e1", "--start", start)["reason"], "retryable")
        for _ in range(3):
            self.ledger("--record", "--event-id", "e1", "--subject", "S", "--start", start, "--status", "transcripts_empty")
        self.assertEqual(self.ledger("--should-attempt", "--event-id", "e1", "--start", start)["reason"], "max_attempts_reached")

    def test_fetched_and_structural_skips_are_final(self):
        s = "2026-11-05T10:00:00+00:00"
        self.ledger("--record", "--event-id", "a", "--subject", "A", "--start", s, "--status", "fetched", "--vtt-path", "inbox/transcripts/teams/a.vtt")
        self.ledger("--record", "--event-id", "b", "--subject", "B", "--start", s, "--status", "cancelled")
        self.assertEqual(self.ledger("--should-attempt", "--event-id", "a", "--start", s)["reason"], "already_fetched")
        self.assertEqual(self.ledger("--should-attempt", "--event-id", "b", "--start", s)["reason"], "permanent_skip")
        summ = self.ledger("--summary", "--since", "2020-01-01T00:00:00+00:00")
        self.assertEqual(summ["files"], ["inbox/transcripts/teams/a.vtt"])
        self.assertEqual(summ["by_status"], {"fetched": 1, "cancelled": 1})

    def test_event_window_conversion_and_filename(self):
        r = W.run_json(self.root, WINDOW, "--start", "2026-11-05T14:00:00.0000000", "--end", "2026-11-05T14:30:00.0000000",
                       "--tz", "GMT Standard Time", "--subject", "Partner API: sync/review")
        self.assertEqual(r["start_utc"], "2026-11-05T14:00:00.000Z")
        self.assertEqual(r["vtt_filename"], "2026-11-05 14.00.00 Partner API syncreview.vtt")
        summer = W.run_json(self.root, WINDOW, "--start", "2026-07-01T14:00:00", "--end", "2026-07-01T15:00:00", "--tz", "GMT Standard Time")
        self.assertEqual(summer["start_utc"], "2026-07-01T13:00:00.000Z")

    def test_unmapped_timezone_fails_loudly(self):
        proc = W.run(self.root, WINDOW, "--start", "2026-11-05T14:00:00", "--end", "2026-11-05T15:00:00", "--tz", "Nowhere Standard Time")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Unmapped", proc.stdout)

    def test_in_window_filters_other_occurrences(self):
        r = W.run_json(self.root, WINDOW, "--in-window", "2026-11-05T14:00:00.000Z", "2026-11-05T14:30:00.000Z",
                       "2026-11-05T14:01:00Z", "2026-10-29T14:01:00Z")
        self.assertTrue(r["match"])
        self.assertEqual(r["matching"], ["2026-11-05T14:01:00Z"])
        self.assertEqual(r["rejected"], ["2026-10-29T14:01:00Z"])


class SaveTranscript(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = W.make_workspace(self._tmp.name)

    def spill(self, name: str, transcripts: list[dict]) -> Path:
        p = self.root / name
        p.write_text(json.dumps({"result": {"transcripts": transcripts}}))
        return p

    def save(self, src: Path, out: str, *extra: str):
        return W.run(self.root, SAVE, "--src", str(src), "--start-utc", "2026-11-05T14:00:00.000Z",
                     "--end-utc", "2026-11-05T14:30:00.000Z", "--out", out, *extra)

    def test_writes_matching_occurrence_byte_for_byte_with_meta(self):
        src = self.spill("r.json", [{"createdDateTime": "2026-10-29T14:01:00Z", "content": vtt_for(["Old"])},
                                    {"createdDateTime": "2026-11-05T14:01:00Z", "content": VTT}])
        proc = self.save(src, "inbox/transcripts/teams/a.vtt", "--invited", "Alex Morgan;Sam Patel")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual((self.root / "inbox/transcripts/teams/a.vtt").read_text(), VTT)
        meta = json.loads((self.root / "inbox/transcripts/teams/a.meta.json").read_text())
        self.assertEqual(meta["invited"], ["Alex Morgan", "Sam Patel"])

    def test_occurrence_mismatch_writes_nothing(self):
        src = self.spill("r.json", [{"createdDateTime": "2026-10-29T14:01:00Z", "content": VTT}])
        proc = self.save(src, "inbox/transcripts/teams/a.vtt")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.root / "inbox/transcripts/teams/a.vtt").exists())

    def test_duplicate_bytes_refused_and_cueless_refused(self):
        src = self.spill("r.json", [{"createdDateTime": "2026-11-05T14:01:00Z", "content": VTT}])
        self.assertEqual(self.save(src, "inbox/transcripts/teams/a.vtt").returncode, 0)
        self.assertEqual(self.save(src, "inbox/transcripts/teams/b.vtt").returncode, 3)
        bad = self.spill("bad.json", [{"createdDateTime": "2026-11-05T14:01:00Z", "content": "WEBVTT\n\nnothing"}])
        self.assertEqual(self.save(bad, "inbox/transcripts/teams/c.vtt").returncode, 1)
        self.assertFalse((self.root / "inbox/transcripts/teams/c.vtt").exists())


if __name__ == "__main__":
    unittest.main()
