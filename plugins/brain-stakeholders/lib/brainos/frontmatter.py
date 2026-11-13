"""Minimal YAML-frontmatter reader/writer for Data store files.

Only what the ingest files use: `key: value`, inline lists `[a, b]`, block lists
(`key:` followed by `  - item`). Updates rewrite a single line and never touch the body.
"""
from __future__ import annotations

import re
from pathlib import Path

_FM_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)


def split(text: str) -> tuple[str | None, str]:
    m = _FM_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def _scalar(raw: str):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
    if v in ("true", "false"):
        return v == "true"
    if v in ("null", "~", ""):
        return None
    return v


def parse(text: str) -> dict:
    fm_text, _ = split(text)
    if fm_text is None:
        return {}
    data: dict = {}
    current_list: str | None = None
    for line in fm_text.splitlines():
        if current_list and re.match(r"^\s+-\s+", line):
            data[current_list].append(_scalar(re.sub(r"^\s+-\s+", "", line)))
            continue
        current_list = None
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if value.strip() == "":
            data[key] = []
            current_list = key
        else:
            data[key] = _scalar(value)
    return data


def read(path: Path) -> dict:
    return parse(Path(path).read_text(encoding="utf-8"))


def format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(v) for v in value) + "]"
    s = str(value)
    if s and (s[0] in "[{&*!|>%@`'\"#" or ": " in s or s.endswith(":") or " #" in s):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def set_fields(text: str, updates: dict) -> str:
    """Return text with frontmatter keys replaced or appended. Raises if no frontmatter."""
    m = _FM_RE.match(text)
    if not m:
        raise ValueError("file has no frontmatter")
    lines = m.group(1).splitlines()
    for key, value in updates.items():
        new_line = f"{key}: {format_value(value)}"
        for i, line in enumerate(lines):
            if re.match(rf"^{re.escape(key)}\s*:", line):
                lines[i] = new_line
                break
        else:
            lines.append(new_line)
    return "---\n" + "\n".join(lines) + "\n---\n" + text[m.end():]


def update_file(path: Path, updates: dict) -> None:
    p = Path(path)
    p.write_text(set_fields(p.read_text(encoding="utf-8"), updates), encoding="utf-8")


def render(fields: dict) -> str:
    """Render a fresh frontmatter block (with trailing newline)."""
    out = ["---"]
    for key, value in fields.items():
        if isinstance(value, list) and key in BLOCK_LIST_KEYS:
            out.append(f"{key}:")
            out.extend(f"  - {v}" for v in value)
        else:
            out.append(f"{key}: {format_value(value)}")
    out.append("---")
    return "\n".join(out) + "\n"


# Keys rendered as YAML block lists (one item per line) to match existing KB notes.
BLOCK_LIST_KEYS = {"participants"}
