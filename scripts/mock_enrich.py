#!/usr/bin/env python3
"""No-API enrichment for Pulse: turns seed/raw/<topic>.jsonl into seed/enriched/<topic>.jsonl
using the ground-truth sidecar seed/raw/<topic>.truth.jsonl plus realistic model-like noise.

Usage: python scripts/mock_enrich.py [--topic ID] [--seed 7]
"""
import argparse
import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "seed"

# Regions that a noisy model would plausibly confuse with each other
CONFUSABLE = {
    "ireland": ["united-kingdom"], "united-kingdom": ["ireland"], "virginia-us": ["new-york", "chicago"],
    "johor": ["singapore", "kuala-lumpur"], "singapore": ["johor", "kuala-lumpur"], "kuala-lumpur": ["johor"],
    "hyderabad": ["bangalore", "mumbai"], "bangalore": ["hyderabad", "delhi"], "mumbai": ["delhi"],
    "arizona-us": ["los-angeles", "texas-us"], "texas-us": ["arizona-us"], "los-angeles": ["arizona-us"],
    "netherlands": ["germany"], "germany": ["netherlands"], "sweden": ["germany"],
    "santiago": ["buenos-aires"], "buenos-aires": ["santiago"], "jakarta": ["kuala-lumpur"],
    "ho-chi-minh-city": ["bangkok"], "manila": ["jakarta"], "toronto": ["new-york"], "vancouver": ["toronto"],
}


def clean_caption(desc):
    d = re.sub(r"^(Video slideshow:|Photo of|Wide photo of|Short video of|Phone video|Drone video|Screenshot of)\s*", "", desc).strip()
    d = d[0].upper() + d[1:] if d else d
    d = re.sub(r"\s*\([^)]*\)", "", d)          # drop inline translations
    if len(d) > 160:
        d = d[:157].rsplit(" ", 1)[0] + "..."
    return d


def enrich_topic(topic, rng):
    raw_p = SEED_DIR / "raw" / f"{topic}.jsonl"
    truth_p = SEED_DIR / "raw" / f"{topic}.truth.jsonl"
    truth = {}
    for line in truth_p.open(encoding="utf-8"):
        t = json.loads(line)
        truth[t["id"]] = t
    out_p = SEED_DIR / "enriched" / f"{topic}.jsonl"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_p.open("w", encoding="utf-8") as out:
        for line in raw_p.open(encoding="utf-8"):
            p = json.loads(line)
            t = truth[p["id"]]
            s = t["sentiment"] + rng.gauss(0, 0.08)
            s = round(max(-1.0, min(1.0, s)), 2)
            rid = t["region_id"]
            if p["author_loc"]:
                conf = rng.uniform(0.78, 0.98)
            elif p.get("community") and p["community"].startswith("r/") and p["community"][2:].islower():
                conf = rng.uniform(0.62, 0.85)
            else:
                conf = rng.uniform(0.5, 0.72)
            # ~3% of low-confidence posts get a plausible but wrong region
            if conf < 0.65 and rid in CONFUSABLE and rng.random() < 0.12:
                rid = rng.choice(CONFUSABLE[rid])
                conf = rng.uniform(0.5, 0.58)
            caption = clean_caption(p["media"][0]["description"]) if p["media"] else None
            ocr = t.get("ocr") if p["media"] else None
            p.update({"sentiment": s, "narrative": t["narrative"], "region_id": rid,
                      "region_conf": round(conf, 2), "caption": caption, "ocr": ocr})
            out.write(json.dumps(p, ensure_ascii=False) + "\n")
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    topics = [args.topic] if args.topic else [t["id"] for t in json.loads((SEED_DIR / "topics.json").read_text())]
    for tid in topics:
        n = enrich_topic(tid, random.Random(f"{args.seed}-{tid}"))
        print(f"{tid}: enriched {n} posts -> seed/enriched/{tid}.jsonl")


if __name__ == "__main__":
    main()
