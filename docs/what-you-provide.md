# What you provide by hand

The automation only works on what you give it. Ingest can fetch your Slack and your meetings on
its own, but it can't know who you are, which channels matter, what your company expects of someone in
your role, or what you are trying to become. That part is manual, and it comes first.

This page lists every input a person has to supply, per module. Setup copies a template for each
file and never overwrites it afterwards. **The templates describe a fictional company (Fernhill).
Until you replace them, the modules that read them produce fiction.**

## The short version

1. Install PyYAML (`python3 -m pip install pyyaml`), run `/brain-core:setup` and answer the interview.
2. Fill in `SOUL.md` and `BRAND.md`.
3. Create your first project and list its team.
4. For each source module, say what to watch.
5. If you use the growth module, paste in your company's career framework. Nothing in that
   module is useful before you do.
6. Only then say yes to the scheduled jobs.

## Every workspace (brain-core)

| You provide | Where | Why it matters |
|---|---|---|
| Name, person ID, role, company, timezone | the setup interview → `.claude/brain.json` | The person ID ties you to meetings and project teams. The timezone sets the daily ingest window. |
| Who you are, what you own, your audiences | `SOUL.md` | Read at the start of every session. Without it every draft is generic. |
| Your voice, banned words, format defaults | `BRAND.md` | Used for digests, exec updates and any text written in your name. |
| How you like to work | `RULES.md`, the fenced "Working preferences" block | The defaults suit most people. Edit what doesn't suit you. |
| What counts as confidential | the setup interview → `.claude/brain.json → confidential` | Extra folders and Slack channel name patterns beyond the defaults. |
| Your projects | `/brain-core:new-project <slug>`, then the project's `README.md` | Nothing is filed under a project that doesn't exist. |
| Each project's team | `projects/<slug>/teams.md` (person IDs) | The trust tier of every fact is computed from who was in the room and who is on the team. An empty roster means low trust everywhere. |
| Tokens, if a module needs one | `.secrets/apis.env`, created by you | Setup never asks for a secret and never writes this file. |
| Connectors | Claude Code settings | Slack, Microsoft 365, Atlassian. The first run of a skill asks you to allow the connector's read tools. |
| A yes or no per scheduled job | the end of setup | Nothing is scheduled without your yes for that job. |

## Sources

| Module | You provide | Where |
|---|---|---|
| **brain-ingest-slack** | The channels to watch, with tags and sensitivity | `.claude/brain/slack-channels.json` |
| | Your Slack workspace URL, your own Slack user ID, the emoji you flag messages with | `.claude/brain/slack-config.json` |
| | The habit of flagging: react to a message with that emoji and it is ingested | in Slack |
| **brain-ingest-teams** | Nothing if the Microsoft 365 connector is on. Otherwise you drop transcripts (`YYYY-MM-DD HH.MM.SS Title.vtt`, `.txt` or `.docx`) | `inbox/transcripts/` |
| **brain-ingest-confluence** | The spaces, pages, labels or CQL to watch, and which labels mean confidential | `.claude/brain/confluence-watch.json` |
| **brain-ingest-notes** | The notes themselves: drop files or use `/brain-ingest-notes:note` | `inbox/notes/` |

## People

| Module | You provide | Where |
|---|---|---|
| **brain-stakeholders** | Your org chart: who reports to whom, roles, teams | `people/_org.yaml` |
| | A page per person you work with (`brain new person <first-last>`); influence and interest ratings for the stakeholder map | `people/<first-last>.md` |
| | Whose 1:1s to draft notes for | `.claude/brain/one-on-one-roster.json` |
| | A yes for each drafted 1:1 note before it reaches the person's page | in chat |
| **brain-mentoring** | Per mentorship: the goals, the agreement, the cadence, and whether you are mentor or mentee | `/brain-mentoring:mentoring-setup` |

## Growth: the module that needs the most from you

`brain-growth` looks for evidence of your impact in your meetings, decisions and digests, and
measures it against a competency framework. **It has no idea what your role means at your
company until you tell it.** There is no connector for this. You type or paste it in once, and
you keep it current.

| You provide | Where | What it is |
|---|---|---|
| The definition of your current level | `growth/development/frameworks/<level>.md` | What your company expects of someone in your position: the skills, and under each skill the criteria. One file per level. |
| The definition of the next level | a second file in the same folder | What is expected of the position you are aiming for. The gap report, the objectives linter and the self-review all compare the two. With one level only, there is no gap to report. |
| Which level you are at and which you target | `.claude/brain/growth/source-config.json → levels` | Must match the `level:` in the two framework files. |
| Your company values | `.claude/brain/growth/values.json` | Used to tag evidence and to write the values paragraph of a self-review. |
| The shape of your review form | `.claude/brain/growth/review-format.json` | Section titles, prompts and word budgets of the tool your company uses. |
| Who counts as a senior leader | `.claude/brain/growth/senior-leaders.json` | Role keywords, so that feedback from senior people is recognised as such. |
| Your objectives | `growth/objectives/<period>.md`, with `/brain-growth:objectives` | Written with you in a conversation. Each one is tied to framework criteria. |
| Past reviews and feedback | `growth/reviews/`, `growth/feedback/received/` | Optional, but they are the best early evidence. Paste them in as markdown. |
| Your triage | `/brain-growth:growth-signals` | The weekly job only queues candidates. Evidence counts once you accept it. |

How to write a framework file is explained in the template setup copies
(`growth/development/frameworks/framework.md`): frontmatter with the level, one `## Skill`
heading per skill, one bullet per criterion with a stable ID. If your company has no written
framework, write down what your manager would say the two levels mean. A rough framework you
agree with beats a precise one that isn't yours.

Everything under `growth/` is confidential by default and is never quoted into a digest, the
wiki or anything shared. A career framework is usually an internal document: keep the
workspace private.

## Outputs

| Module | You provide | Where |
|---|---|---|
| **brain-digests** | Which projects to include, and where a digest may be published (Confluence space and parent page, Slack channel, or email recipients) | `.claude/brain/digests.json` |
| | A yes for each digest before it is published | in chat |
| **brain-steal-list** | The clips: screenshots of posts worth a look | `steal/inbox/` (or a synced folder set in `.claude/brain/steal.json`) |
| | Your decision on each verdict (adopt, reject, defer), and approval of a plan before anything is built | `/brain-steal-list:steal` |
| **brain-learning-loop** | Your answer to each proposal, and the decision to promote a pattern into `RULES.md` | `brain kb confirm`, the weekly review |
| **brain-wiki** | Confirmation of AI-written decisions; anything inside `<!-- human -->` fences is yours and is never rewritten | project pages |
| **brain-grill** | The document or plan to stress-test, and your answers | `/brain-grill:grill-me` |
