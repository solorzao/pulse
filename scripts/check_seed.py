#!/usr/bin/env python3
"""Print per-region score/volume for each topic plus the key time trends."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "seed"
STORY = {
    "ai-datacenters": ["ireland", "virginia-us", "arizona-us", "texas-us", "netherlands", "sweden", "hyderabad", "johor", "santiago"],
    "electric-scooters": ["jakarta", "ho-chi-minh-city", "bangkok", "manila", "singapore", "paris", "los-angeles"],
    "four-day-week": ["united-kingdom", "germany", "new-york", "tokyo", "sydney", "bangalore", "seoul"],
}


def load(t):
    return [json.loads(l) for l in (SEED / "enriched" / f"{t}.jsonl").open(encoding="utf-8")]


def main():
    for t, story in STORY.items():
        posts = load(t)
        agg = defaultdict(list)
        for p in posts:
            agg[p["region_id"]].append(p["sentiment"])
        print(f"\n== {t}  ({len(posts)} posts, {len(agg)} regions) ==")
        for rid in story:
            v = agg[rid]
            print(f"  {rid:18s} n={len(v):4d} score={round(sum(v) / len(v) * 100):4d}")
        others = [s for r, v in agg.items() if r not in story for s in v]
        print(f"  {'(fillers)':18s} n={len(others):4d} score={round(sum(others) / len(others) * 100):4d}")
    now = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
    for t, rid, label in [("ai-datacenters", "ireland", "Ireland"), ("electric-scooters", "singapore", "Singapore")]:
        by_day = defaultdict(list)
        for p in load(t):
            if p["region_id"] == rid:
                d = (now - datetime.fromisoformat(p["ts"].replace("Z", "+00:00"))).days
                by_day[d].append(p["sentiment"])
        row = " ".join(f"{round(sum(by_day[d]) / len(by_day[d]) * 100) if by_day[d] else '·':>4}" for d in range(29, -1, -1))
        print(f"\n{label} daily score (30d ago -> today):\n{row}")


if __name__ == "__main__":
    main()
