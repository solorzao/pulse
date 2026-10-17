#!/usr/bin/env python3
"""Real enrichment for Pulse using Claude (Anthropic Python SDK).

Reads seed/raw/<topic>.jsonl, writes seed/enriched/<topic>.jsonl (RawPost + sentiment, narrative,
region_id, region_conf, caption, ocr). Resumable: ids already present in the output are skipped.

Env: ANTHROPIC_API_KEY (required), PULSE_ENRICH_MODEL (default claude-haiku-5-5)
Usage: python scripts/enrich.py [--topic ID] [--batch 20] [--concurrency 8] [--limit N] [--fresh]
"""
import argparse
import asyncio
import json
import os
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "seed"
MODEL = os.environ.get("PULSE_ENRICH_MODEL", "claude-haiku-5-5")

SYSTEM = """You are an annotation engine for a social-listening product. For each social post you receive \
(text, author location, community, and descriptions of attached images/videos), output structured labels.

Return ONLY a JSON array (no prose, no markdown fences), one object per input post, in the same order, each:
{"id": str, "sentiment": float -1..1 (the author's feeling about the TOPIC, not general mood),
 "narrative": str (short 2-5 word label for the post's main argument/theme, Title case, reuse labels across posts when the theme is the same),
 "region_id": str (MUST be one of the allowed region ids; best guess from author_loc, community, place names, language),
 "region_conf": float 0..1 (how sure you are about region_id; lower when author_loc is missing),
 "caption": str|null (one-sentence neutral description of the first media item, null if no media),
 "ocr": str|null (any legible text visible in the media, e.g. sign or meme text, else null)}"""


def build_prompt(topic, posts, region_ids):
    items = []
    for p in posts:
        items.append({
            "id": p["id"], "source": p["source"], "community": p.get("community"),
            "author_loc": p.get("author_loc"), "lang": p.get("lang"), "text": p["text"],
            "media": [{"type": m.get("type"), "description": m.get("description")} for m in p.get("media") or []],
        })
    return (f"Topic: {topic}\nAllowed region ids: {', '.join(region_ids)}\n\n"
            f"Posts ({len(items)}):\n{json.dumps(items, ensure_ascii=False)}\n\n"
            f"Return the JSON array of {len(items)} objects now.")


def _clamp(x, lo, hi, default):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return default
    if x != x:  # NaN
        return default
    return max(lo, min(hi, x))


def _opt_str(v):
    if v is None:
        return None
    v = str(v).strip()
    if not v or v.lower() in ("null", "none", "n/a"):
        return None
    return v


def parse_response(text, posts, region_ids):
    """Parse model output into {id: enrichment-dict}. Tolerates code fences / prose around the array,
    drops unknown ids, validates region ids, clamps numbers. Missing posts are simply absent."""
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("no JSON array in response")
    data = json.loads(s[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("response is not a list")
    by_id = {p["id"]: p for p in posts}
    valid = set(region_ids)
    out = {}
    for i, obj in enumerate(data):
        if not isinstance(obj, dict):
            continue
        pid = obj.get("id")
        if pid not in by_id and i < len(posts) and len(data) == len(posts):
            pid = posts[i]["id"]  # fall back to positional match if id got mangled
        if pid not in by_id:
            continue
        rid = str(obj.get("region_id") or "").strip().lower().replace(" ", "-").replace("_", "-")
        conf = _clamp(obj.get("region_conf"), 0.0, 1.0, 0.5)
        if rid not in valid:
            continue  # unmappable region: skip post (API joins region_id against regions.json)
        has_media = bool(by_id[pid].get("media"))
        out[pid] = {
            "sentiment": round(_clamp(obj.get("sentiment"), -1.0, 1.0, 0.0), 3),
            "narrative": (_opt_str(obj.get("narrative")) or "Other")[:60],
            "region_id": rid,
            "region_conf": round(conf, 3),
            "caption": _opt_str(obj.get("caption")) if has_media else None,
            "ocr": _opt_str(obj.get("ocr")) if has_media else None,
        }
    return out


async def enrich_batch(client, sem, topic, posts, region_ids, retries=4):
    prompt = build_prompt(topic, posts, region_ids)
    async with sem:
        for attempt in range(retries + 1):
            try:
                resp = await client.messages.create(
                    model=MODEL, max_tokens=8000, system=SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                return parse_response(text, posts, region_ids)
            except Exception as e:  # noqa: BLE001 — network, rate limit, or parse errors all retry
                if attempt == retries:
                    print(f"  ! batch failed after {retries + 1} attempts: {e!r}", file=sys.stderr)
                    return {}
                wait = min(60, 2 ** attempt + random.random())
                print(f"  retry {attempt + 1} in {wait:.1f}s: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
                await asyncio.sleep(wait)


async def enrich_topic(client, topic, region_ids, batch, concurrency, limit, fresh, min_coverage=0.97):
    raw_p = SEED_DIR / "raw" / f"{topic}.jsonl"
    final_p = SEED_DIR / "enriched" / f"{topic}.jsonl"
    out_p = SEED_DIR / ".enrich-cache" / f"{topic}.jsonl"  # resume cache (not read by the API); promoted when complete
    out_p.parent.mkdir(parents=True, exist_ok=True)
    final_p.parent.mkdir(parents=True, exist_ok=True)
    if fresh and out_p.exists():  # noqa
        out_p.unlink()
    done = set()
    if out_p.exists():
        for line in out_p.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    posts = [json.loads(l) for l in raw_p.open(encoding="utf-8") if l.strip()]
    todo = [p for p in posts if p["id"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"{topic}: {len(posts)} raw, {len(done)} already enriched, {len(todo)} to do")
    if not todo:
        _promote(out_p, final_p, posts, min_coverage)
        return
    sem = asyncio.Semaphore(concurrency)
    chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    lock = asyncio.Lock()
    written = 0
    with out_p.open("a", encoding="utf-8") as out:
        async def run(chunk):
            nonlocal written
            res = await enrich_batch(client, sem, topic, chunk, region_ids)
            async with lock:
                for p in chunk:
                    if p["id"] in res:
                        out.write(json.dumps({**p, **res[p["id"]]}, ensure_ascii=False) + "\n")
                        written += 1
                out.flush()
                print(f"  {topic}: {written}/{len(todo)}")
        await asyncio.gather(*(run(c) for c in chunks))
    if written < len(todo):
        print(f"  {topic}: {len(todo) - written} posts not enriched (failed batch or unmappable region); re-run to retry")
    _promote(out_p, final_p, posts, min_coverage)


def _promote(work_p, final_p, posts, min_coverage=0.97):
    """Replace seed/enriched/<topic>.jsonl (e.g. mock output) once every raw post is enriched."""
    ids = {json.loads(l)["id"] for l in work_p.open(encoding="utf-8") if l.strip()} if work_p.exists() else set()
    missing = sum(1 for p in posts if p["id"] not in ids)
    if missing > len(posts) * (1 - min_coverage):
        print(f"  not promoting {work_p.name}: {missing} posts still missing (existing {final_p.name} kept)")
        return
    order = {p["id"]: i for i, p in enumerate(posts)}
    rows = sorted((json.loads(l) for l in work_p.open(encoding="utf-8") if l.strip()), key=lambda r: order.get(r["id"], 1e9))
    seen = set()
    with final_p.open("w", encoding="utf-8") as f:
        for r in rows:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  promoted -> {final_p.relative_to(ROOT)} ({len(seen)} posts)")


async def amain(args):
    import anthropic  # imported lazily so the parser can be tested without the SDK installed
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (use scripts/mock_enrich.py for the no-API path)")
    client = anthropic.AsyncAnthropic(max_retries=2)
    region_ids = [r["id"] for r in json.loads((SEED_DIR / "regions.json").read_text())]
    topics = [args.topic] if args.topic else [t["id"] for t in json.loads((SEED_DIR / "topics.json").read_text())]
    for t in topics:
        await enrich_topic(client, t, region_ids, args.batch, args.concurrency, args.limit, args.fresh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="only enrich the first N pending posts per topic")
    ap.add_argument("--fresh", action="store_true", help="discard the partial work file and start over")
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
