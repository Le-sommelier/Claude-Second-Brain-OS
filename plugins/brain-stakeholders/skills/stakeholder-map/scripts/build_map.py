#!/usr/bin/env python3
"""Build the stakeholder map: an influence/interest grid plus relationship health, as markdown (mermaid).

    python3 build_map.py [--today YYYY-MM-DD] [--dry-run]

Reads people/*.md frontmatter (influence 1-5, interest 1-5, health, last_contact, cadence_days,
relationship) and the org chart. Quadrants: manage-closely (high/high), keep-satisfied (high
influence, low interest), keep-informed (low influence, high interest), monitor (low/low). A person is
'stale' when last_contact is older than their cadence (default: 14 days for manage-closely, 30 for
keep-satisfied/informed, 60 for monitor). People without ratings are listed as 'unrated'. Writes
people/_stakeholder-map.md, marked confidential. Contains ratings only, never notes.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "person" / "scripts"))
import peoplelib as pl  # noqa: E402

DEFAULT_CADENCE = {"manage-closely": 14, "keep-satisfied": 30, "keep-informed": 30, "monitor": 60}
QUADRANT_LABEL = {"manage-closely": "Manage closely", "keep-satisfied": "Keep satisfied",
                  "keep-informed": "Keep informed", "monitor": "Monitor"}


def quadrant(influence: int, interest: int) -> str:
    hi_inf, hi_int = influence >= 4, interest >= 4
    return {(True, True): "manage-closely", (True, False): "keep-satisfied",
            (False, True): "keep-informed", (False, False): "monitor"}[(hi_inf, hi_int)]


def collect(today: date) -> tuple[list[dict], list[dict]]:
    _, org = pl.read_org()
    orgmap = {p["id"]: p for p in org if p.get("id")}
    rated, unrated = [], []
    for p, fm in pl.pages():
        pid = p.stem
        if fm.get("relationship") == "self":
            continue
        rec = {"id": pid, "name": fm.get("name") or orgmap.get(pid, {}).get("name") or pid,
               "role": fm.get("role") or orgmap.get(pid, {}).get("role") or "",
               "relationship": fm.get("relationship") or "", "health": fm.get("health") or "unknown",
               "last_contact": str(fm.get("last_contact") or "")}
        try:
            inf, intr = int(fm["influence"]), int(fm["interest"])
            assert 1 <= inf <= 5 and 1 <= intr <= 5
        except (KeyError, ValueError, TypeError, AssertionError):
            unrated.append(rec)
            continue
        q = quadrant(inf, intr)
        cadence = int(fm.get("cadence_days") or DEFAULT_CADENCE[q])
        age = None
        if pl.DATE_RE.match(rec["last_contact"]):
            age = (today - pl.parse_date(rec["last_contact"])).days
        rec.update({"influence": inf, "interest": intr, "quadrant": q, "cadence_days": cadence,
                    "days_since_contact": age, "stale": age is None or age > cadence})
        rated.append(rec)
    order = {"manage-closely": 0, "keep-satisfied": 1, "keep-informed": 2, "monitor": 3}
    rated.sort(key=lambda r: (order[r["quadrant"]], -r["influence"], r["name"]))
    return rated, unrated


def render_md(rated: list[dict], unrated: list[dict], today: date) -> str:
    def pos(v: int, n: int, k: int) -> float:
        return round(min(0.95, max(0.05, (v - 1) / 4 + (n * 0.03 - k * 0.015))), 2)

    seen: dict = {}
    pts = []
    for r in rated:
        k = (r["influence"], r["interest"])
        seen[k] = seen.get(k, 0) + 1
        pts.append(f"    {r['name']}: [{pos(r['interest'], seen[k] - 1, 0)}, {pos(r['influence'], seen[k] - 1, 1)}]")
    fm = pl.frontmatter.render({"type": "stakeholder-map", "generated": today.isoformat(), "sensitivity": "confidential"})
    out = [fm, "# Stakeholder map", "", pl.OPEN, "", "```mermaid", "quadrantChart", "    title Influence and interest",
           "    x-axis Low interest --> High interest", "    y-axis Low influence --> High influence",
           "    quadrant-1 Manage closely", "    quadrant-2 Keep satisfied", "    quadrant-3 Monitor", "    quadrant-4 Keep informed"] + pts + ["```", "",
           "| Person | Role | Quadrant | Health | Last contact | Stale |", "|---|---|---|---|---|---|"]
    for r in rated:
        out.append(f"| [[{r['id']}]] {r['name']} | {r['role']} | {QUADRANT_LABEL[r['quadrant']]} | {r['health']} | "
                   f"{r['last_contact'] or '-'} | {'yes' if r['stale'] else 'no'} |")
    attention = [r for r in rated if r["health"] == "at-risk" or (r["stale"] and r["quadrant"] == "manage-closely")]
    out += ["", "## Needs attention", ""] + ([f"- {r['name']}: {'at risk' if r['health'] == 'at-risk' else 'overdue for contact'}" for r in attention] or ["- nobody"])
    if unrated:
        out += ["", "## Unrated", "", "Add `influence` and `interest` (1-5) to these pages: " + ", ".join(r["name"] for r in unrated)]
    out += ["", pl.CLOSE, ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = pl.parse_date(args.today) if args.today else date.today()
    rated, unrated = collect(today)
    if not rated and not unrated:
        pl.emit({"status": "skipped", "reason": "no people pages found"})
        return 0
    md = pl.path("stakeholders", "map_md")
    if not args.dry_run:
        pl.write_atomic(md, render_md(rated, unrated, today))
    pl.emit({"status": "success", "rated": len(rated), "unrated": len(unrated),
             "at_risk": sum(1 for r in rated if r["health"] == "at-risk"), "stale": sum(1 for r in rated if r["stale"]),
             "outputs": [pl.rel(md)]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
