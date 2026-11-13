"""Shared helpers for the brain-growth scripts: config, framework, candidates, tracker, hypotheses.

Everything here reads the owner's framework and config; nothing is hardcoded to a company.
Sibling skills add this folder to sys.path and import it.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos.workspace import root, path, rel, emit, owner  # noqa: E402,F401
from brainos import frontmatter  # noqa: E402,F401

CONFIG_SUBDIR = "growth"


# ---------- paths and config ----------

def gp(key: str) -> Path:
    return path("growth", key)


def run_dir() -> Path:
    """Run state for growth (candidate and classified payloads). Under growth/ so it stays confidential."""
    d = gp("run")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_cfg(name: str) -> dict:
    p = path("core", "module_config_dir") / CONFIG_SUBDIR / name
    if not p.is_file():
        raise FileNotFoundError(f"{rel(p)} missing: run /brain-core:setup (it copies the brain-growth templates)")
    data = json.loads(p.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def source_config() -> dict:
    return load_cfg("source-config.json")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


# ---------- framework ----------

SKILL_SECTION_RE = re.compile(r"^##\s+(?:\d+\.\s+)?(.+?)\s*$")
CRITERION_RE = re.compile(r"^-\s+`([a-z0-9][a-z0-9-]*)`\s+(?:—|-|:)\s+(.+?)\s*$")


@dataclass
class Criterion:
    id: str
    skill: str
    text: str
    level: str
    track: str
    version: str
    framework: str


@dataclass
class Framework:
    file: str
    name: str
    level: str
    track: str
    version: str
    criteria: list = field(default_factory=list)


def parse_framework(p: Path) -> Framework:
    text = p.read_text(encoding="utf-8")
    fm = frontmatter.parse(text)
    fw = Framework(rel(p), str(fm.get("framework") or p.stem), str(fm.get("level") or ""),
                   str(fm.get("track") or ""), str(fm.get("version") or "1.0"))
    skill = None
    _, body = frontmatter.split(text)
    for line in body.splitlines():
        m = SKILL_SECTION_RE.match(line)
        if m and not line.startswith("###"):
            skill = m.group(1).strip()
            continue
        c = CRITERION_RE.match(line)
        if c and skill:
            fw.criteria.append(Criterion(c.group(1), skill, c.group(2), fw.level, fw.track, fw.version, fw.name))
    return fw


def frameworks() -> list[Framework]:
    d = gp("frameworks")
    return [parse_framework(p) for p in sorted(d.glob("*.md")) if not p.name.startswith("_")] if d.is_dir() else []


def criteria_index() -> dict[str, Criterion]:
    idx: dict[str, Criterion] = {}
    for fw in frameworks():
        for c in fw.criteria:
            idx.setdefault(c.id, c)
    return idx


# ---------- candidates file ----------

HASH_RE = re.compile(r"^- `hash:\s*([a-f0-9]{12})`")
TRIAGE_RE = re.compile(r"^- \*\*Triage:\*\*\s+(.*)$")
STATUS_RE = re.compile(r"^- \*\*Status:\*\*\s+(.*)$")
CHECKED_RE = re.compile(r"`\[\s*[xX]\s*\]`\s+(Accept|Reject|Defer)")
CRIT_LINE_RE = re.compile(r"^\s+-\s+`([a-z0-9][a-z0-9-]*)`")
SKILL_LINE_RE = re.compile(r"^- \*\*Skill:\*\*\s+(.*)$")
HEADING_RE = re.compile(r"^#{1,4}\s")


def existing_hashes(text: str) -> set[str]:
    return set(re.findall(r"`hash:\s*([a-f0-9]{12})`", text))


def parse_candidates(text: str) -> list[dict]:
    """Candidate blocks: '#### title' up to the next heading or '---'."""
    lines = text.splitlines()
    out: list[dict] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#### "):
            start = i
            i += 1
            while i < len(lines) and not HEADING_RE.match(lines[i]) and lines[i].strip() != "---":
                i += 1
            block = lines[start:i]
            cand = {"title": lines[start][5:].strip(), "start": start, "end": i, "hash": None, "skill": None,
                    "criteria": [], "triage_idx": None, "status_idx": None, "status": None, "action": None}
            for j, ln in enumerate(block):
                idx = start + j
                if (m := HASH_RE.match(ln)):
                    cand["hash"] = m.group(1)
                elif (m := TRIAGE_RE.match(ln)):
                    cand["triage_idx"] = idx
                    if (a := CHECKED_RE.search(m.group(1))):
                        cand["action"] = a.group(1).lower()
                elif (m := STATUS_RE.match(ln)):
                    cand["status_idx"] = idx
                    cand["status"] = m.group(1)
                elif (m := SKILL_LINE_RE.match(ln)):
                    cand["skill"] = m.group(1).strip()
                elif ln.startswith("- **Criteria evidenced:**"):
                    cand["_in_crit"] = True
                elif cand.get("_in_crit") and (m := CRIT_LINE_RE.match(ln)):
                    cand["criteria"].append(m.group(1))
                elif ln.startswith("- **"):
                    cand["_in_crit"] = False
            cand.pop("_in_crit", None)
            if cand["hash"]:
                out.append(cand)
        else:
            i += 1
    return out


# ---------- tracker ----------

CRIT_TAG_RE = re.compile(r"<!--\s*crit:\s*([^>]*?)\s*-->")


def tracker_evidence(text: str) -> dict[str, list[str]]:
    """criterion id -> bullet titles tagged with <!-- crit: ... -->."""
    out: dict[str, list[str]] = {}
    for ln in text.splitlines():
        m = CRIT_TAG_RE.search(ln)
        if not m or not ln.lstrip().startswith("-"):
            continue
        title = CRIT_TAG_RE.sub("", ln).lstrip("- ").strip()
        for cid in [c.strip() for c in m.group(1).split(",") if c.strip()]:
            out.setdefault(cid, []).append(title)
    return out


# ---------- hypotheses ----------

HYP_HEAD_RE = re.compile(r"^###\s+H-(\d+):\s+(.*)$")


def load_hypotheses(text: str) -> dict[str, dict]:
    by_crit: dict[str, dict] = {}
    cur = None
    for ln in text.splitlines():
        if (m := HYP_HEAD_RE.match(ln)):
            if cur and cur.get("criterion_id"):
                by_crit[cur["criterion_id"]] = cur
            cur = {"hyp_num": int(m.group(1)), "title": m.group(2), "sources": [], "confirmations": 0,
                   "refutations": 0, "status": "open"}
            continue
        if cur is None:
            continue
        if (m := re.search(r"\*\*Criterion targeted:\*\*\s+`([^`]+)`", ln)):
            cur["criterion_id"] = m.group(1)
        if (m := re.search(r"\*\*Confirmations:\*\*\s+(\d+)", ln)):
            cur["confirmations"] = int(m.group(1))
        if (m := re.search(r"\*\*Refutations:\*\*\s+(\d+)", ln)):
            cur["refutations"] = int(m.group(1))
        if re.match(r"\s*-\s+\d{4}-\d{2}-\d{2}", ln):
            cur["sources"].append(ln.strip())
        if (m := re.search(r"\*\*Status:\*\*\s+(.*)", ln)):
            cur["status"] = "paused" if "paused" in m.group(1).lower() or "refuted" in m.group(1).lower() else "open"
    if cur and cur.get("criterion_id"):
        by_crit[cur["criterion_id"]] = cur
    return by_crit


def self_ratings() -> dict:
    p = gp("self_assessment")
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


# ---------- owner ----------

def actor_aliases(extra: list[str] | None = None) -> list[str]:
    o = owner()
    names = [o.get("first_name"), o.get("name"), o.get("person_id")] + list(extra or [])
    return [n for n in names if n and not str(n).startswith("{{")]


def objective_files() -> list[Path]:
    d = gp("objectives")
    return sorted(d.glob("*.md")) if d.is_dir() else []


# ---------- objectives ----------

OBJ_HEAD_RE = re.compile(r"^##\s+Objective\s+(\d+)\s*[:.-]\s*(.+?)\s*$")
BOX_RE = re.compile(r"^\s*-\s+\[( |x|X)\]\s+(.+?)\s*$")
FW_TAG_RE = re.compile(r"<!--\s*framework-criteria:\s*([^>]*?)\s*-->")


def parse_objectives(text: str) -> list[dict]:
    """Objectives from an objectives file: title, narrative, done-looks-like boxes, criterion tags."""
    _, body = frontmatter.split(text)
    out: list[dict] = []
    cur = None
    for ln in body.splitlines():
        if (m := OBJ_HEAD_RE.match(ln)):
            cur = {"n": int(m.group(1)), "title": m.group(2), "narrative": [], "done": [], "criteria": []}
            out.append(cur)
            continue
        if ln.startswith("## "):
            cur = None
            continue
        if cur is None:
            continue
        if (m := BOX_RE.match(ln)):
            cur["done"].append({"text": m.group(2), "checked": m.group(1).lower() == "x"})
        elif (m := FW_TAG_RE.search(ln)):
            cur["criteria"] += [c.strip() for c in m.group(1).split(",") if c.strip()]
        elif ln.strip() and not ln.startswith("**Done looks like"):
            cur["narrative"].append(ln.strip())
    for o in out:
        o["narrative"] = " ".join(o["narrative"])
    return out
