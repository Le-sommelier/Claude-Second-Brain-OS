#!/usr/bin/env python3
"""Extract a compact digest of recent Claude Code sessions for the nightly consolidation.

Reads this workspace's Claude Code transcripts straight from
  ~/.claude/projects/<encoded-workspace-path>/*.jsonl
(the folder name is computed at runtime from the workspace root), so it does not depend on any
Stop/PreCompact hook firing. Per session it keeps the opening ask, the human steering turns and the
final assistant message; tool output, thinking, system reminders and hook bootstrap text are dropped.
Sessions that touched a confidential path are listed with their content withheld.

  (default)             digest sessions newer than the watermark -> <learning.input_dir>/consolidation-input-DATE.md
  --commit <iso8601>    advance the watermark (call AFTER the nightly writes are on disk)
  --since <iso8601>     override the lower bound (backfill / testing)
  --max-sessions N      cap per run, newest first (default 40)
  --transcripts-dir D   override the transcript folder ($BRAIN_TRANSCRIPTS_DIR does the same)
  --min-age-seconds N   skip files touched in the last N seconds, likely a live session (default 120)

Extra noise markers (text that is hook output, not human intent) can be listed in
.claude/brain.json -> learning.noise_markers.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from brainos.workspace import config, emit, path, rel, root  # noqa: E402
from brainos.confidential import is_confidential_path  # noqa: E402

PER_SESSION_CHAR_CAP = 4000
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
TURN_NOISE_PREFIXES = ("<task-notification>", "<scheduled-task", "<command-", "[Request interrupted",
                       "Continue from where you left off", "Caveat: The messages below were generated")
SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}"
    r"|xox[abp]-[A-Za-z0-9-]{10,}|(?i:(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+)")


def transcripts_dir(override: str | None = None) -> Path:
    env = override or os.environ.get("BRAIN_TRANSCRIPTS_DIR")
    if env:
        return Path(env).expanduser()
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    return base / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root()))


def noise_markers() -> tuple[str, ...]:
    return tuple(config().get("learning", {}).get("noise_markers", []))


def strip_reminders(text: str) -> str:
    return re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL).strip()


def is_noise(text: str) -> bool:
    return text.startswith(TURN_NOISE_PREFIXES) or any(m in text for m in noise_markers())


def read_events(p: Path):
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def extract_turns(p: Path) -> tuple[list[str], list[str]]:
    """(human turns, assistant texts) with tool output, thinking and reminders removed."""
    humans, assistants = [], []
    for d in read_events(p):
        kind = d.get("type")
        if kind not in ("user", "assistant"):
            continue
        content = (d.get("message") or {}).get("content")
        if kind == "user":
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(b.get("text", "") for b in content
                                 if isinstance(b, dict) and b.get("type") == "text")
            else:
                continue
            text = strip_reminders(text)
            if text and not is_noise(text):
                humans.append(text)
        elif isinstance(content, list):
            text = "\n".join(b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text").strip()
            if text:
                assistants.append(text)
    return humans, assistants


def files_touched(p: Path) -> set[str]:
    """Workspace-relative paths the session wrote to (absolute paths outside the workspace are kept as-is)."""
    out: set[str] = set()
    for d in read_events(p):
        if d.get("type") != "assistant":
            continue
        for b in (d.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS:
                inp = b.get("input") or {}
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp:
                    try:
                        out.add(rel(Path(fp)))
                    except (ValueError, OSError):
                        out.add(str(fp))
    return out


def touches_confidential(files: set[str]) -> bool:
    return any(is_confidential_path(f) for f in files)


def tidy(text: str, n: int) -> str:
    return SECRET_RE.sub("[redacted]", " ".join(text.split()))[:n]


def session_digest(p: Path) -> str | None:
    humans, assistants = extract_turns(p)
    if not humans:
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    head = f"### Session {p.stem[:8]} - {mtime.strftime('%Y-%m-%d %H:%M UTC')}"
    if touches_confidential(files_touched(p)):
        return head + "\n_Touched a confidential area: content withheld. Do not infer or quote it._"
    lines = [head, f"**Opening ask:** {tidy(humans[0], 600)}"]
    if len(humans) > 1:
        lines.append("**Steering turns:**")
        lines += [f"- {tidy(h, 220)}" for h in humans[1:8]]
    if assistants:
        lines.append(f"**Final assistant note:** {tidy(assistants[-1], 600)}")
    return "\n".join(lines)[:PER_SESSION_CHAR_CAP]


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_watermark() -> dict:
    wm = path("learning", "watermark")
    if wm.is_file():
        try:
            return json.loads(wm.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"last_run_iso": None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--commit")
    ap.add_argument("--since")
    ap.add_argument("--max-sessions", type=int, default=40)
    ap.add_argument("--transcripts-dir")
    ap.add_argument("--min-age-seconds", type=int, default=120)
    args = ap.parse_args()

    if args.commit:
        try:
            parse_iso(args.commit)
        except ValueError:
            emit({"status": "failed", "reason": f"--commit is not an ISO 8601 timestamp: {args.commit!r}"})
            return 1
        wm = path("learning", "watermark")
        wm.parent.mkdir(parents=True, exist_ok=True)
        data = load_watermark()
        data["last_run_iso"] = args.commit
        tmp = wm.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(wm)
        emit({"status": "success", "watermark": args.commit})
        return 0

    since_iso = args.since or load_watermark().get("last_run_iso")
    since = parse_iso(since_iso) if since_iso else datetime.now(timezone.utc) - timedelta(hours=24)
    pdir = transcripts_dir(args.transcripts_dir)
    if not pdir.is_dir():
        emit({"status": "failed", "reason": f"transcript folder not found: {pdir}"})
        return 1

    now = datetime.now(timezone.utc)
    candidates = []
    for p in pdir.glob("*.jsonl"):
        mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mt > since and (now - mt).total_seconds() >= args.min_age_seconds:
            candidates.append((mt, p))
    candidates.sort(reverse=True)
    candidates = candidates[: args.max_sessions]

    digests, newest, ids = [], since, []
    for mt, p in candidates:
        d = session_digest(p)
        if d:
            digests.append(d)
            ids.append(p.stem)
        newest = max(newest, mt)

    out_dir = path("learning", "input_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"consolidation-input-{now.strftime('%Y-%m-%d')}.md"
    header = (f"# Session consolidation input - generated {now.isoformat()}\n"
              f"Sessions since: {since.isoformat()}\n"
              f"Sessions found: {len(digests)} (of {len(candidates)} candidate files)\n"
              f"Proposed new watermark: {newest.isoformat()}\n\n")
    out_file.write_text(header + ("\n\n".join(digests) if digests else "_No sessions to consolidate._\n"),
                        encoding="utf-8")
    emit({"status": "success", "input_file": rel(out_file), "sessions": len(digests),
          "candidates": len(candidates), "session_ids": [i[:8] for i in ids],
          "proposed_watermark": newest.isoformat()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
