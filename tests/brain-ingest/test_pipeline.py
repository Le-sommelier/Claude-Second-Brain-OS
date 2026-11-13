import json
import re
import unittest
from pathlib import Path

PLUGINS = Path(__file__).resolve().parents[2] / "plugins"
INGEST = PLUGINS / "brain-ingest"
SLACK = PLUGINS / "brain-ingest-slack"
STAGES = ["fetch", "transform", "index", "derive", "finalise"]


def frontmatter(path: Path) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(), re.S)
    assert m, f"{path} has no frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)


class PipelineBase(unittest.TestCase):
    def test_base_has_five_empty_stages(self):
        base = json.loads((INGEST / "templates/pipeline.base.json").read_text())
        self.assertEqual([s["id"] for s in base["stages"]], STAGES)
        for s in base["stages"]:
            self.assertFalse(s.get("lanes") or s.get("steps"), f"{s['id']} must ship with no bricks")
        self.assertTrue({"max_catchup_days", "run_log_retention_days"} <= set(base["settings"]))

    def test_module_json_template_and_schedule(self):
        mod = json.loads((INGEST / "brain.module.json").read_text())
        self.assertEqual(mod["module"], "brain-ingest")
        for t in mod["templates"]:
            self.assertTrue((INGEST / t["from"]).is_file())
        for s in mod["scheduled"]:
            self.assertTrue((INGEST / s["prompt"]).is_file())

    def test_slack_bricks_target_base_stages_and_exist_as_skills(self):
        mod = json.loads((SLACK / "brain.module.json").read_text())
        self.assertTrue(mod["bricks"])
        for b in mod["bricks"]:
            self.assertIn(b["stage"], STAGES)
            plugin, skill = b["brick"].split(":")
            self.assertEqual(plugin, "brain-ingest-slack")
            self.assertTrue((SLACK / "skills" / skill / "SKILL.md").is_file(), b["brick"])
            self.assertIn(b["model"], {"haiku", "sonnet", "opus"})

    def test_fetch_bricks_on_haiku_and_per_date_channels(self):
        bricks = {b["brick"].split(":")[1]: b for b in json.loads((SLACK / "brain.module.json").read_text())["bricks"]}
        self.assertEqual(bricks["ingest-slack-channels"]["model"], "haiku")
        self.assertTrue(bricks["ingest-slack-channels"]["per_date"])
        self.assertEqual(bricks["ingest-slack-flagged"]["model"], "haiku")
        self.assertFalse(bricks["ingest-owed-replies"]["enabled"])

    def test_skills_have_frontmatter_and_allowed_tools(self):
        for skill in [*INGEST.glob("skills/*/SKILL.md"), *SLACK.glob("skills/*/SKILL.md")]:
            fm = frontmatter(skill)
            self.assertTrue(fm.get("name") and fm.get("description"), skill)
            self.assertEqual(fm["name"], skill.parent.name)
            self.assertIn("allowed-tools", fm, skill)

    def test_slack_script_commands_are_single_line_allow_listed(self):
        for skill in SLACK.glob("skills/*/SKILL.md"):
            fm = frontmatter(skill)
            self.assertIn("Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)", fm["allowed-tools"])
            for line in skill.read_text().splitlines():
                if "python3" in line and "scripts/" in line:
                    self.assertNotRegex(line, r"&&|\|\s*\w|python3 -c|<<")

    def test_orchestrator_uses_core_cli_not_scripts(self):
        text = (INGEST / "skills/orchestrator/SKILL.md").read_text()
        for cmd in ("brain run plan", "brain run finalise"):
            self.assertIn(cmd, text)
        self.assertNotIn("/Users/", text)

    def test_json_files_parse(self):
        for p in [*INGEST.rglob("*.json"), *SLACK.rglob("*.json")]:
            json.loads(p.read_text())


if __name__ == "__main__":
    unittest.main()
