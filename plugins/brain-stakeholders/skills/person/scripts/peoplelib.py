"""Shared helpers for the brain-stakeholders scripts: people pages, _org.yaml, human fences.

Ownership of a people page (brain-wiki owns the rest):
  stakeholders owns the frontmatter keys in STAKEHOLDER_FIELDS and the sections in OWNED_SECTIONS.
  Text between <!-- human --> and <!-- /human --> is never rewritten by anyone.
Sibling skills add this folder to sys.path and import it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))  # plugins/<m>/skills/<s>/scripts/x.py
from brainos.workspace import root, path, rel, emit, owner, parse_date  # noqa: E402,F401
from brainos import frontmatter  # noqa: E402,F401
from brainos.confidential import OPEN, CLOSE  # noqa: E402,F401

ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RELATIONSHIPS = ["self", "manager", "report", "peer", "stakeholder", "exec", "mentee", "mentor", "partner"]
HEALTH = ["strong", "ok", "at-risk", "unknown"]
STAKEHOLDER_FIELDS = {"relationship": RELATIONSHIPS, "influence": range(1, 6), "interest": range(1, 6),
                      "health": HEALTH, "last_contact": None, "cadence_days": range(1, 366)}
OWNED_SECTIONS = ["Stakeholder notes", "1:1 log", "Evidence log"]
HUMAN_RE = re.compile(r"<!--\s*human\s*-->.*?<!--\s*/human\s*-->", re.S)


def people_dir() -> Path:
    return path("core", "people")


def page_path(person: str) -> Path:
    if not ID_RE.match(person):
        raise SystemExit(f"person id must look like first-last, got '{person}'")
    return people_dir() / f"{person}.md"


def human_fences(text: str) -> list[str]:
    return HUMAN_RE.findall(text)


def write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def pages() -> list[tuple[Path, dict]]:
    d = people_dir()
    out = []
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if p.name.startswith("_"):
            continue
        out.append((p, frontmatter.read(p)))
    return out


# ---------- sections ----------

def split_sections(body: str) -> list[tuple[str | None, list[str]]]:
    """[(heading or None for the preamble, lines)] split on '## ' headings, fences untouched."""
    out: list[tuple[str | None, list[str]]] = [(None, [])]
    for ln in body.splitlines():
        if ln.startswith("## "):
            out.append((ln[3:].strip(), [ln]))
        else:
            out[-1][1].append(ln)
    return out


def join_sections(secs: list[tuple[str | None, list[str]]]) -> str:
    return "\n".join(ln for _, lines in secs for ln in lines).rstrip("\n") + "\n"


def ensure_section(secs: list, name: str) -> int:
    for i, (h, _) in enumerate(secs):
        if h == name:
            return i
    secs.append((name, [f"## {name}", ""]))
    return len(secs) - 1


def insert_in_confidential(lines: list[str], new: list[str], newest_first: bool = True) -> list[str]:
    """Insert lines inside the section's CONFIDENTIAL wrapper (create it if missing)."""
    o = next((i for i, ln in enumerate(lines) if ln.strip() == OPEN), None)
    c = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == CLOSE), None)
    if o is None or c is None or c < o:
        tail = [ln for ln in lines]
        while tail and not tail[-1].strip():
            tail.pop()
        return tail + ["", OPEN] + new + [CLOSE, ""]
    at = o + 1 if newest_first else c
    return lines[:at] + new + lines[at:]


# ---------- _org.yaml (a small, explicit YAML subset: a list of flat records) ----------

ORG_KEYS = ["id", "name", "role", "tier", "manager", "team", "email", "slack_id", "location", "status"]


def _val(raw: str):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
    return None if v in ("", "null", "~") else v


def read_org(p: Path | None = None) -> tuple[list[str], list[dict]]:
    """(leading comment lines, people records). Missing file -> ([], [])."""
    p = p or path("core", "org")
    if not p.is_file():
        return [], []
    comments, people, cur = [], [], None
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.startswith("#"):
            if not people:
                comments.append(ln)
            continue
        if not ln.strip() or ln.strip() == "people:":
            continue
        m = re.match(r"^\s*-\s+(\w+):\s*(.*)$", ln)
        if m:
            cur = {m.group(1): _val(m.group(2))}
            people.append(cur)
            continue
        m = re.match(r"^\s+(\w+):\s*(.*)$", ln)
        if m and cur is not None:
            cur[m.group(1)] = _val(m.group(2))
    return comments, people


def _fmt(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    s = str(v)
    return f'"{s}"' if re.search(r"[:#\[\]{}]|^\s|\s$", s) else s


def write_org(comments: list[str], people: list[dict], p: Path | None = None) -> None:
    p = p or path("core", "org")
    out = list(comments) + ["people:"]
    for rec in people:
        keys = [k for k in ORG_KEYS if rec.get(k) not in (None, "")] + [k for k in rec if k not in ORG_KEYS and rec[k] not in (None, "")]
        for i, k in enumerate(keys):
            out.append(("  - " if i == 0 else "    ") + f"{k}: {_fmt(rec[k])}")
    write_atomic(p, "\n".join(out) + "\n")
