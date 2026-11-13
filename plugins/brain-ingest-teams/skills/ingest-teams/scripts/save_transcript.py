#!/usr/bin/env python3
"""Write a Teams transcript to the inbox WITHOUT the text passing through model context.

  --src <file>              the saved connector result (the JSON a large read_resource spills)
  --from-session-uri <uri>  the connector returned the transcript inline: pass the exact uri given
                            to read_resource; the result is read from Claude Code's session log
                            (stored verbatim). Fails closed when not found.
  --check <vtt>             validate a VTT file

Both write modes find transcripts[], keep those whose createdDateTime is inside the occurrence
window, join their content (ascending createdDateTime) and write the VTT byte-for-byte:

  python3 ${CLAUDE_SKILL_DIR}/scripts/save_transcript.py --from-session-uri "<uri>" --start-utc <Z> --end-utc <Z> --out "inbox/transcripts/teams/<name>.vtt" --invited "Alex Morgan;Sam Patel"

--invited (optional, calendar attendee display names, metadata only) writes <name>.meta.json beside
the VTT; ingest-meeting-files uses it to compute attendance. Refuses an empty or cue-less result
(exit 1), an occurrence mismatch (exit 2) and bytes identical to another VTT already in the
inbox or its _processed folder (exit 3, duplicate_bytes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brainos.workspace import root  # noqa: E402
from event_window_utc import _parse_utc, window_bounds  # noqa: E402

CUE = re.compile(r"(\d\d:\d\d:\d\d\.\d{3})\s+-->\s+(\d\d:\d\d:\d\d\.\d{3})")
TRUNCATION = re.compile(r"\[truncated|characters truncated|output too large", re.I)
SPILL = re.compile(r"saved to:?\s*(/\S+?\.(?:json|txt))", re.I)
SESSION_LOG_MAX_AGE_S = 6 * 3600


def find_transcripts(node):
    if isinstance(node, dict):
        t = node.get("transcripts")
        if isinstance(t, list) and t and all(isinstance(x, dict) and "content" in x for x in t):
            return t
        for v in node.values():
            found = find_transcripts(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = find_transcripts(v)
            if found:
                return found
    elif isinstance(node, str) and node.lstrip()[:1] in "{[":
        try:
            return find_transcripts(json.loads(node))
        except ValueError:
            return None
    return None


def projects_dir() -> Path:
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root()))


def session_result(uri: str):
    """(data, None) or (None, error): newest read_resource result whose call used exactly `uri`."""
    folder = projects_dir()
    if not folder.is_dir():
        return None, "no session log folder found for this workspace"
    now = time.time()
    logs = [p for p in list(folder.glob("*.jsonl")) + list(folder.glob("*/subagents/*.jsonl"))
            if now - p.stat().st_mtime <= SESSION_LOG_MAX_AGE_S]
    for log in sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True):
        ids, results = [], {}
        with log.open(encoding="utf-8") as fh:
            for line in fh:
                if uri not in line and '"tool_result"' not in line:
                    continue
                try:
                    content = (json.loads(line).get("message") or {}).get("content")
                except ValueError:
                    continue
                for b in content if isinstance(content, list) else []:
                    if b.get("type") == "tool_use" and (b.get("input") or {}).get("uri") == uri:
                        ids.append(b.get("id"))
                    elif b.get("type") == "tool_result":
                        results[b.get("tool_use_id")] = b.get("content")
        for tid in reversed(ids):
            if tid in results:
                data = results[tid]
                if not find_transcripts(data):
                    spill = SPILL.search(json.dumps(data))
                    if spill and Path(spill.group(1)).is_file():
                        try:
                            return json.loads(Path(spill.group(1)).read_text(encoding="utf-8")), None
                        except ValueError:
                            return None, "spilled result is not JSON"
                return data, None
    return None, "no read_resource result for that uri in recent session logs"


def check(text: str) -> dict:
    if "WEBVTT" not in text[:20]:
        return {"ok": False, "error": "missing WEBVTT header"}
    cues = CUE.findall(text)
    if not cues:
        return {"ok": False, "error": "no cues"}
    return {"ok": True, "cues": len(cues), "last_cue_end": cues[-1][1]}


def duplicate_of(text: str, out: Path):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    for folder in (out.parent, out.parent.parent / "_processed"):
        for f in folder.glob("*.vtt") if folder.is_dir() else []:
            if f.name != out.name and hashlib.sha256(f.read_bytes()).hexdigest() == digest:
                return f.name
    return None


def say(obj: dict, code: int) -> int:
    print(json.dumps(obj))
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src")
    ap.add_argument("--from-session-uri")
    ap.add_argument("--start-utc")
    ap.add_argument("--end-utc")
    ap.add_argument("--out")
    ap.add_argument("--check")
    ap.add_argument("--invited", default="", help="semicolon-separated attendee display names")
    a = ap.parse_args()

    if a.check:
        p = Path(a.check)
        p = p if p.is_absolute() else root() / p
        return say(check(p.read_text(encoding="utf-8")), 0)
    if not ((a.src or a.from_session_uri) and a.start_utc and a.end_utc and a.out):
        ap.error("--src or --from-session-uri, plus --start-utc, --end-utc and --out, are required (or use --check)")

    if a.from_session_uri:
        data, err = session_result(a.from_session_uri)
        if err:
            return say({"ok": False, "error": err}, 1)
    else:
        try:
            data = json.loads(Path(a.src).read_text(encoding="utf-8"))
        except ValueError:
            return say({"ok": False, "error": "source is not JSON"}, 1)
    transcripts = find_transcripts(data)
    if not transcripts:
        return say({"ok": False, "error": "no transcripts[] with content in source"}, 1)
    lo, hi = window_bounds(a.start_utc, a.end_utc)
    keep = [t for t in transcripts if t.get("createdDateTime") and lo <= _parse_utc(t["createdDateTime"]) <= hi]
    if not keep:
        return say({"ok": False, "error": "occurrence_mismatch",
                    "created": [t.get("createdDateTime") for t in transcripts]}, 2)
    keep.sort(key=lambda t: _parse_utc(t["createdDateTime"]))
    text = "\n\n".join(t["content"] for t in keep)
    verdict = check(text)
    if verdict["ok"] and TRUNCATION.search(text[-300:]):
        verdict = {"ok": False, "error": "transcript looks truncated"}
    if not verdict["ok"]:
        return say(verdict, 1)
    out = Path(a.out)
    out = out if out.is_absolute() else root() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    dup = duplicate_of(text, out)
    if dup:
        return say({"ok": False, "error": "duplicate_bytes", "same_as": dup}, 3)
    out.write_text(text, encoding="utf-8")
    invited = [n.strip() for n in a.invited.split(";") if n.strip()]
    if invited:
        out.with_suffix(".meta.json").write_text(json.dumps({"invited": invited}, indent=2) + "\n", encoding="utf-8")
    rel = str(out.relative_to(root())) if root() in out.parents else str(out)
    return say({"ok": True, "out": rel, "transcripts": len(keep), "cues": verdict["cues"],
                "bytes": len(text.encode("utf-8")), "meta": bool(invited)}, 0)


if __name__ == "__main__":
    raise SystemExit(main())
