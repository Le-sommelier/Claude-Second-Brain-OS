"""Argument parsing and the small commands (root, pending, flag). See bin/brain for the surface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brainos.workspace import emit, parse_date, root


def cmd_root(args) -> int:
    print(root())
    return 0


def cmd_pending(args) -> int:
    from brainos.pending import scan
    types = set(args.source_type) if args.source_type else None
    today = parse_date(args.today) if args.today else None
    emit(scan(args.flag, types, args.max_age_days, today))
    return 0


def _parse_set(value: str) -> tuple[str, bool]:
    key, sep, raw = value.partition("=")
    if not sep or raw.lower() not in ("true", "false"):
        raise SystemExit("--set must look like wiki_processed=true or todo_processed=false")
    return key.strip(), raw.lower() == "true"


def cmd_flag(args) -> int:
    from brainos.pending import set_flag
    flags = [_parse_set(v) for v in args.set]
    files: list[str] = list(args.file or [])
    payload = None
    if args.files_from:
        from brainos.payload import load
        payload = Path(args.files_from) if Path(args.files_from).is_absolute() else root() / args.files_from
        data = load(payload, expect=object)
        items = data.get("files", []) if isinstance(data, dict) else data
        if not isinstance(items, list) or not all(isinstance(x, (str, dict)) for x in items):
            raise SystemExit("--files-from payload must be a list of paths or {\"files\": [...]}")
        files += [x if isinstance(x, str) else x.get("path", "") for x in items]
    files = [f for f in files if f]
    if not files:
        raise SystemExit("nothing to flag: pass --file <rel> or --files-from <payload.json>")
    result = {"updated": [], "errors": []}
    for flag, value in flags:
        updated, errors = set_flag(files, flag, value)
        result["updated"] = sorted(set(result["updated"]) | set(updated))
        result["errors"] += errors
    if payload is not None and not result["errors"]:
        from brainos.payload import consume
        consume(payload, keep=args.keep_payload)
    emit({"status": "success" if not result["errors"] else "partial", "count": len(result["updated"]), **result})
    return 0 if not result["errors"] else 1


def build_parser() -> argparse.ArgumentParser:
    from braincore import doctor, kb, run, scaffold
    ap = argparse.ArgumentParser(prog="brain", description="claude-second-brain-os core CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("root", help="print the workspace root").set_defaults(fn=cmd_root)

    d = sub.add_parser("doctor", help="check config, paths, modules, schema and the kb")
    d.add_argument("--quick", action="store_true", help="skip the kb validation pass")
    d.set_defaults(fn=doctor.cmd_doctor)

    p = sub.add_parser("pending", help="the pending queue (JSON)")
    p.add_argument("--flag", default="wiki_processed", choices=["wiki_processed", "todo_processed"])
    p.add_argument("--source-type", action="append")
    p.add_argument("--max-age-days", type=int)
    p.add_argument("--today")
    p.set_defaults(fn=cmd_pending)

    f = sub.add_parser("flag", help="flip queue flags on raw files")
    f.add_argument("--set", action="append", required=True, metavar="FLAG=true|false")
    f.add_argument("--file", action="append", metavar="REL")
    f.add_argument("--files-from", metavar="PAYLOAD_JSON")
    f.add_argument("--keep-payload", action="store_true")
    f.set_defaults(fn=cmd_flag)

    kb.add_parser(sub)

    n = sub.add_parser("new", help="scaffold a project, topic or person from templates")
    n.add_argument("kind", choices=["project", "topic", "person"])
    n.add_argument("slug")
    n.add_argument("--title")
    n.add_argument("--dry-run", action="store_true")
    n.set_defaults(fn=scaffold.cmd_new)

    r = sub.add_parser("run", help="ingest run state for the orchestrator")
    rs = r.add_subparsers(dest="run_cmd", required=True)
    rp = rs.add_parser("plan", help="plan the window and write system/run/run-context.json")
    rp.add_argument("--today")
    rp.add_argument("--catch-up", type=int, metavar="N", help="force the window to the N days ending today")
    rp.set_defaults(fn=run.cmd_plan)
    rf = rs.add_parser("finalise", help="close the run: status, run log, summary")
    rf.add_argument("--returns", default="system/run/returns.json")
    rf.set_defaults(fn=run.cmd_finalise)
    return ap


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except RuntimeError as exc:  # no workspace
        print(f"brain: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:  # missing paths.json key
        print(f"brain: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"brain: {exc}", file=sys.stderr)
        return 1
