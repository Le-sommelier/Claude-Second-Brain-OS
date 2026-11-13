"""`brain run plan` / `brain run finalise`: ingest run state. All the date maths lives here.

The pipeline (`core.pipeline`, system/run/pipeline.json) is assembled by setup: brain-ingest's
pipeline.base.json plus the `bricks` of every installed module. The orchestrator (brain-ingest)
reads only what `plan` prints and hands every brick return back to `finalise`.

plan
----
Window: every calendar day after the last successful run, plus any `dates_partial` the most
recent run left behind, plus today, capped at settings.max_catchup_days. First run: today only.
`--catch-up N` forces the window to the N days ending today. N is capped at max_catchup_days;
the dates beyond the cap are listed in `dates_dropped_by_cap` so the caller can say so.

run-context.json (worked example, one per-date skill brick and one script brick):

    {
      "run_id": "2026-11-13T07:00:02Z", "today": "2026-11-13", "timezone": "Europe/London",
      "dates_to_process": ["2026-11-12", "2026-11-13"], "dates_dropped_by_cap": [], "catchup": true,
      "window": {"2026-11-13": {"start_iso": "2026-11-12T00:00:00+00:00", "end_iso": "2026-11-14T00:00:00+00:00",
                                "oldest_ts": "1794441600.000000", "latest_ts": "1794614400.000000"}},
      "slack": {"window": {"2026-11-13": {"oldest_ts": "...", "latest_ts": "..."}},
                "flagged_after": "2026-10-30", "owed_after": "2026-10-30"},
      "settings": {"max_catchup_days": 14, "...": "...", "bricks": {"brain-ingest-slack:ingest-slack-channels": {}}},
      "dispatch": [
        {"stage": "fetch", "mode": "lanes", "lanes": {"slack": [
          {"brick": "brain-ingest-slack:ingest-slack-channels", "kind": "skill", "model": "haiku",
           "skill": "brain-ingest-slack:ingest-slack-channels", "affects_status": true, "target_date": "2026-11-12"}]}},
        {"stage": "index", "mode": "sequential", "steps": [
          {"brick": "brain-core:kb-build", "kind": "script", "command": "brain kb build --as-brick brain-core:kb-build",
           "affects_status": false}]}
      ]
    }

Each date's window runs from local midnight (owner timezone) of the day before to local midnight
of the day after. The overlap catches late messages; fetch bricks file by posting date and
dedupe, so it never duplicates.

finalise
--------
Status: a brick counts unless its dispatch entry says affects_status=false.
  success: no counted brick failed and no date is partial
  failed:  every counted brick failed
  partial: anything in between
A date is partial when a per-date return carrying that `target_date` is not success/skipped, or
when any return lists it in `dates_partial`. The next plan re-includes partial dates.
Finalise never writes MEMORY.md: the orchestrator owns ingest observations
(`observations_written: false` in the output tells it so).
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from brainos.workspace import config, emit, parse_date, path, rel

STAGE_ORDER = ["fetch", "transform", "index", "derive", "finalise"]
DEFAULT_SETTINGS = {"max_catchup_days": 14, "flagged_lookback_days": 14, "owed_lookback_days": 14,
                    "run_log_retention_days": 90}


def _load(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default


def _tz():
    name = (config().get("owner") or {}).get("timezone") or "UTC"
    try:
        from zoneinfo import ZoneInfo
        return name, ZoneInfo(name)
    except Exception:  # unknown zone or no tzdata: fall back to UTC, loudly in the context
        return "UTC", timezone.utc


def load_runs() -> list[dict]:
    return _load(path("core", "run_log"), {"runs": []}).get("runs", [])


def compute_window(runs: list[dict], today: date, max_days: int, catch_up: int | None) -> tuple[list[date], list[date]]:
    """Return (dates_to_process ascending, dates_dropped_by_cap)."""
    if catch_up:
        # --catch-up is capped by max_catchup_days; dates beyond the cap are reported, not fetched
        n = max(1, min(catch_up, max_days or 1))
        dropped = [today - timedelta(days=i) for i in range(catch_up - 1, n - 1, -1)]
        return [today - timedelta(days=i) for i in range(n - 1, -1, -1)], dropped
    successes = [parse_date(r["date"]) for r in runs if r.get("status") == "success" and r.get("date")]
    last_success = max(successes) if successes else today
    missed = {last_success + timedelta(days=i) for i in range(1, (today - last_success).days)}
    if runs:
        missed |= {parse_date(d) for d in runs[0].get("dates_partial", []) if parse_date(d) < today}
    ordered = sorted(missed)
    dropped = ordered[:-max_days] if max_days and len(ordered) > max_days else ([] if max_days else ordered)
    kept = ordered[-max_days:] if max_days else []
    return kept + [today], dropped


def _ts(dt: datetime) -> str:
    return f"{calendar.timegm(dt.astimezone(timezone.utc).timetuple())}.000000"


def day_window(d: date, tz) -> dict:
    start = datetime.combine(d - timedelta(days=1), time(0), tzinfo=tz)
    end = datetime.combine(d + timedelta(days=1), time(0), tzinfo=tz)
    return {"start_iso": start.isoformat(), "end_iso": end.isoformat(), "oldest_ts": _ts(start), "latest_ts": _ts(end)}


def _step(spec: dict, dates: list[date]) -> list[dict]:
    if spec.get("enabled", True) is False:
        return []
    base = {"brick": spec["brick"], "affects_status": spec.get("affects_status", True)}
    if spec.get("command") or spec.get("script"):
        base["kind"] = "script"
        base["command"] = spec.get("command") or f"python3 {spec['script']}"
    else:
        base["kind"] = "skill"
        base["skill"] = spec.get("skill") or spec["brick"]
        base["model"] = spec.get("model", "sonnet")
    if spec.get("per_date"):
        return [{**base, "target_date": d.isoformat()} for d in dates]
    return [base]


def stale_module_roots(pipeline: dict) -> list[str]:
    """Modules whose recorded plugin root vanished (the plugin was updated to a new cache path).

    Roots may be absolute (what setup writes) or relative to the workspace root (the committed
    sample workspace uses ../../plugins/<module> so it carries no machine-specific path).
    """
    from brainos.workspace import root

    def exists(r: str) -> bool:
        p = Path(r)
        return (p if p.is_absolute() else root() / p).is_dir()

    return sorted(name for name, m in (pipeline.get("modules") or {}).items()
                  if isinstance(m, dict) and m.get("root") and not exists(m["root"]))


def _stages_sorted(stages: list[dict]) -> list[dict]:
    rank = {s: i for i, s in enumerate(STAGE_ORDER)}
    return sorted(stages, key=lambda s: rank.get(s.get("id"), len(STAGE_ORDER)))


def expand(stages: list[dict], dates: list[date]) -> list[dict]:
    out = []
    for stage in _stages_sorted(stages):
        if "lanes" in stage:
            lanes = {name: [s for spec in specs for s in _step(spec, dates)] for name, specs in stage["lanes"].items()}
            lanes = {k: v for k, v in lanes.items() if v}
            if lanes:
                out.append({"stage": stage["id"], "mode": "lanes", "lanes": lanes})
        else:
            steps = [s for spec in stage.get("steps", []) for s in _step(spec, dates)]
            if steps:
                out.append({"stage": stage["id"], "mode": "parallel" if stage.get("parallel") else "sequential",
                            "steps": steps})
    return out


def _all_specs(stages: list[dict]) -> list[dict]:
    specs = []
    for st in stages:
        for lane in (st.get("lanes") or {}).values():
            specs.extend(lane)
        specs.extend(st.get("steps") or [])
    return specs


def cmd_plan(args) -> int:
    pfile = path("core", "pipeline")
    if not pfile.is_file():
        raise SystemExit(f"no pipeline at {rel(pfile)} — install brain-ingest and re-run /brain-core:setup")
    pipeline = json.loads(pfile.read_text(encoding="utf-8"))
    stale = stale_module_roots(pipeline)
    if stale:
        raise SystemExit("module roots recorded in the pipeline no longer exist (" + ", ".join(stale)
                         + "): re-run /brain-core:setup to refresh module roots")
    settings = {**DEFAULT_SETTINGS, **(pipeline.get("settings") or {})}
    stages = pipeline.get("stages") or []
    today = parse_date(args.today) if args.today else date.today()
    runs = load_runs()
    dates, dropped = compute_window(runs, today, int(settings["max_catchup_days"]), args.catch_up)
    tzname, tz = _tz()
    window = {d.isoformat(): day_window(d, tz) for d in dates}
    flagged_after = min(min(dates) - timedelta(days=1), today - timedelta(days=int(settings["flagged_lookback_days"])))
    brick_settings = {s["brick"]: s["settings"] for s in _all_specs(stages) if isinstance(s.get("settings"), dict)}
    context = {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today.isoformat(),
        "timezone": tzname,
        "dates_to_process": [d.isoformat() for d in dates],
        "dates_dropped_by_cap": [d.isoformat() for d in dropped],
        "catchup": len(dates) > 1,
        "window": window,
        "slack": {
            "window": {k: {"oldest_ts": v["oldest_ts"], "latest_ts": v["latest_ts"]} for k, v in window.items()},
            "flagged_after": flagged_after.isoformat(),
            "owed_after": (today - timedelta(days=int(settings["owed_lookback_days"]))).isoformat(),
        },
        "settings": {**settings, "bricks": brick_settings},
        "dispatch": expand(stages, dates),
    }
    run_dir = path("core", "run_dir")
    (run_dir / "payloads").mkdir(parents=True, exist_ok=True)
    path("core", "run_context").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    (run_dir / "returns.json").write_text("[]\n", encoding="utf-8")
    emit(context)
    return 0


# ---------------------------------------------------------------- finalise

def dispatched(context: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for stage in context.get("dispatch", []):
        steps = [s for lane in (stage.get("lanes") or {}).values() for s in lane] + (stage.get("steps") or [])
        for s in steps:
            out.setdefault(s["brick"], s)
    return out


def partial_dates(returns: list[dict], dates: list[str]) -> list[str]:
    bad = set()
    for r in returns:
        if r.get("target_date") and r.get("status") not in ("success", "skipped"):
            bad.add(str(r["target_date"]))
        for d in r.get("dates_partial") or []:
            bad.add(str(d))
    return sorted(d for d in bad if d in set(dates))


def run_status(returns: list[dict], entries: dict[str, dict], dates_partial: list[str]) -> str:
    counted = [r for r in returns if entries.get(r.get("brick"), {}).get("affects_status", True)]
    failed = [r for r in counted if r.get("status") in ("failed", "needs_escalation")]
    seen = {r.get("brick") for r in returns}
    missing = [b for b, e in entries.items() if e.get("affects_status", True) and b not in seen]
    if counted and len(failed) == len(counted):
        return "failed"
    if failed or missing or dates_partial or any(r.get("status") == "partial" for r in counted):
        return "partial"
    return "success"


def merge_bricks(returns: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    for r in returns:
        b = merged.setdefault(r.get("brick", "?"), {"status": [], "counts": {}, "reasons": [], "warnings": 0})
        b["status"].append(r.get("status"))
        for k, v in (r.get("counts") or {}).items():
            prev = b["counts"].get(k, 0)
            b["counts"][k] = prev + v if isinstance(v, (int, float)) and isinstance(prev, (int, float)) else v
        if r.get("reason"):
            b["reasons"].append(str(r["reason"]))
        b["warnings"] += len(r.get("warnings") or [])
    for b in merged.values():
        statuses = set(b["status"])
        b["status"] = statuses.pop() if len(statuses) == 1 else "partial"
    return merged


def summary_lines(record: dict) -> list[str]:
    out = [f"=== Ingest {record['date']}: {record['status'].upper()} ==="]
    if record["catchup"]:
        out.append(f"Catch-up: {len(record['dates_processed'])} dates "
                   f"({record['dates_processed'][0]} to {record['dates_processed'][-1]})")
    for name, b in record["bricks"].items():
        counts = ", ".join(f"{k} {v}" for k, v in b["counts"].items()) or "-"
        tail = f" ({'; '.join(b['reasons'])})" if b["reasons"] else ""
        out.append(f"{name:<44} {b['status']:<16} {counts}{tail}")
    for name in record["bricks_missing"]:
        out.append(f"{name:<44} {'not run':<16}")
    out.append(f"Partial dates: {', '.join(record['dates_partial']) or 'none'}")
    if record["dates_dropped_by_cap"]:
        out.append(f"WARNING dates beyond the catch-up cap, not ingested: {', '.join(record['dates_dropped_by_cap'])}")
    if record["leftover_payloads"]:
        out.append(f"WARNING leftover payloads: {', '.join(record['leftover_payloads'])}")
    out.append(f"Observations to record: {record['observations_pending']}")
    return out


def cmd_finalise(args) -> int:
    run_dir = path("core", "run_dir")
    context = _load(path("core", "run_context"), None)
    if context is None:
        raise SystemExit("no run-context.json — run `brain run plan` first")
    returns_path = Path(args.returns) if args.returns else run_dir / "returns.json"
    if not returns_path.is_absolute():
        from brainos.workspace import root
        returns_path = root() / returns_path
    returns = _load(returns_path, [])
    if not isinstance(returns, list):
        raise SystemExit("returns file must be a JSON array of brick return objects")
    pipeline = _load(path("core", "pipeline"), {})
    settings = {**DEFAULT_SETTINGS, **(pipeline.get("settings") or {})}
    entries = dispatched(context)
    dates = context.get("dates_to_process", [])
    dates_partial = partial_dates(returns, dates)
    observations = sorted({f"{r.get('brick')}: {o.strip()}" for r in returns for o in (r.get("observations") or [])})
    record = {
        "run_id": context.get("run_id"),
        "date": context["today"],
        "started_at": context.get("run_id"),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": run_status(returns, entries, dates_partial),
        "catchup": context.get("catchup", False),
        "dates_processed": dates,
        "dates_partial": dates_partial,
        "dates_dropped_by_cap": context.get("dates_dropped_by_cap", []),
        "bricks": merge_bricks(returns),
        "bricks_missing": [b for b in entries if b not in {r.get("brick") for r in returns}],
        "leftover_payloads": sorted(p.name for p in (run_dir / "payloads").glob("*") if p.is_file()),
        "observations_pending": len(observations),
    }
    log_path = path("core", "run_log")
    log = _load(log_path, {"runs": []})
    cutoff = (parse_date(record["date"]) - timedelta(days=int(settings["run_log_retention_days"]))).isoformat()
    log["runs"] = [record] + [r for r in log.get("runs", []) if r.get("date", "9999") >= cutoff]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(summary_lines(record)))
    emit({"status": record["status"], "dates_partial": dates_partial, "leftover_payloads": record["leftover_payloads"],
          "observations_written": False, "observations": observations, "run_log": rel(log_path)})
    return 0
