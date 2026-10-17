"""/ask agent: Claude tool-use loop over the DuckDB store, with a deterministic
fallback when no API key is configured or the API call fails."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .store import Store, mood_label

log = logging.getLogger("pulse.agent")

MAX_ITERS = 6

SYSTEM_PROMPT = """You are Pulse, a concise social-sentiment analyst. You answer questions about how people in different regions feel about a topic, using ONLY the data returned by your tools (mock/collected social media posts: Reddit, Bluesky, TikTok, YouTube, Mastodon, news comments; incl. image/video captions and OCR).

Rules:
- Call tools to gather evidence before answering. Ground every claim in tool results; never invent numbers, posts or regions.
- Scores are mean post sentiment x100 (-100..100). Quote scores and post counts.
- Always state sample-size caveats (post count, source mix, location confidence) and that this is social media sentiment, not a representative poll.
- When useful, cite visual evidence (image/video captions, OCR text) from posts.
- Finish by calling submit_answer exactly once. Paragraphs (2-4, short) reference citations inline as [1], [2]; each citation's post_id MUST be a real post id you saw in tool results. Verdict is one punchy sentence.
- Analyst voice: direct, specific, no fluff."""

TOOLS: list[dict] = [
    {"name": "list_topics", "description": "List available topics with post counts and overall mood (-100..100).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "sentiment_by_region",
     "description": "Per-region sentiment score, mood label, post count and mean location confidence for a topic (sorted most negative first).",
     "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}},
    {"name": "region_detail",
     "description": "Detail for one region on a topic: score, narratives with share and sentiment, top sample posts (with ids, media captions, OCR), confidence.",
     "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}, "region_id": {"type": "string"}},
                      "required": ["topic", "region_id"]}},
    {"name": "trend", "description": "Daily sentiment score series for a topic, optionally for one region.",
     "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}, "region_id": {"type": "string"}},
                      "required": ["topic"]}},
    {"name": "search_posts", "description": "Keyword search over post text, media captions, OCR and narratives.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"}, "topic": {"type": "string"}, "region_id": {"type": "string"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 25}}, "required": ["query"]}},
    {"name": "compare", "description": "Compare two regions on a topic side by side (score, narratives, sample posts).",
     "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}, "region_a": {"type": "string"},
                                                      "region_b": {"type": "string"}},
                      "required": ["topic", "region_a", "region_b"]}},
    {"name": "spread", "description": "The tracked cross-region spread event (step timings in hours, counts, arcs).",
     "input_schema": {"type": "object", "properties": {}}},
]

SUBMIT_TOOL = {
    "name": "submit_answer",
    "description": "Submit the final answer. Must be called exactly once, at the end.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "description": "One-sentence headline answer."},
            "tone": {"type": "string", "enum": ["positive", "negative", "mixed"]},
            "summary": {"type": "string", "description": "1-2 sentence summary."},
            "paragraphs": {"type": "array", "items": {"type": "string"},
                           "description": "2-4 short paragraphs, with inline [n] citation markers."},
            "citations": {"type": "array", "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "post_id": {"type": "string"}},
                "required": ["n", "post_id"]}},
            "confidence": {"type": "object", "properties": {
                "level": {"type": "string", "enum": ["low", "medium", "high"]},
                "note": {"type": "string"}}, "required": ["level", "note"]},
        },
        "required": ["verdict", "tone", "summary", "paragraphs", "citations", "confidence"],
    },
}


# ------------------------------------------------------------------ tool impl
def _compact_region(store: Store, topic: str, rid: str) -> dict:
    d = store.region(topic, rid)
    d["posts"] = store.top_posts(topic, rid, limit=5, text_limit=280)
    tr = d.pop("trend")
    d["trend_summary"] = _trend_summary(tr)
    return d


def _trend_summary(tr: list[dict]) -> dict:
    if not tr:
        return {}
    import datetime as _dt
    end = _dt.date.fromisoformat(tr[-1]["date"])
    cut = (end - _dt.timedelta(days=9)).isoformat()
    last = [p["score"] for p in tr if p["date"] >= cut]
    first = [p["score"] for p in tr if p["date"] < cut] or last
    return {"days": len(tr), "first_date": tr[0]["date"], "last_date": tr[-1]["date"],
            "avg_earlier": round(sum(first) / len(first)), "avg_last_10_days": round(sum(last) / len(last))}


def run_tool(store: Store, name: str, args: dict) -> Any:
    args = args or {}
    if name == "list_topics":
        return store.topics_summary()
    if name == "sentiment_by_region":
        return store.sentiment_by_region(args.get("topic", ""))
    if name == "region_detail":
        return _compact_region(store, args.get("topic", ""), args.get("region_id", ""))
    if name == "trend":
        tr = store.trend(args.get("topic", ""), args.get("region_id"))
        return {"series": tr, "summary": _trend_summary(tr)}
    if name == "search_posts":
        return store.search_posts(args.get("query", ""), args.get("topic"), args.get("region_id"),
                                  int(args.get("limit") or 8))
    if name == "compare":
        t = args.get("topic", "")
        return {"a": _compact_region(store, t, args.get("region_a", "")),
                "b": _compact_region(store, t, args.get("region_b", ""))}
    if name == "spread":
        return store.spread()
    return {"error": f"unknown tool {name}"}


def _collect_post_ids(obj: Any, acc: set[str]) -> None:
    if isinstance(obj, dict):
        if "id" in obj and "text" in obj and isinstance(obj["id"], str):
            acc.add(obj["id"])
        for v in obj.values():
            _collect_post_ids(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_post_ids(v, acc)


# ------------------------------------------------------------ answer shaping
def _citation(store: Store, n: int, post_id: str) -> dict | None:
    p = store.get_post(post_id)
    if not p:
        return None
    text = p["text"]
    if len(text) > 240:
        text = text[:239].rstrip() + "…"
    return {"n": n, "post_id": p["id"], "source": p["source"], "text": text, "url": p["url"]}


def finalize_answer(store: Store, raw: dict, seen_ids: set[str], fallback_conf: dict) -> dict:
    cites = []
    renum: dict[int, int] = {}
    for c in raw.get("citations") or []:
        try:
            pid = str(c.get("post_id"))
            n = int(c.get("n"))
        except Exception:  # noqa: BLE001
            continue
        if seen_ids and pid not in seen_ids and not store.get_post(pid):
            continue
        cit = _citation(store, len(cites) + 1, pid)
        if cit:
            renum[n] = cit["n"]
            cites.append(cit)

    def fix(par: str) -> str:
        def rep(m: re.Match) -> str:
            k = int(m.group(2))
            return f"{m.group(1)}[{renum[k]}]" if k in renum else ""
        return re.sub(r"(\s?)\[(\d+)\]", rep, par).strip()

    paragraphs = [fix(str(p)) for p in (raw.get("paragraphs") or []) if str(p).strip()]
    tone = raw.get("tone") if raw.get("tone") in ("positive", "negative", "mixed") else "mixed"
    conf = raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}
    level = conf.get("level") if conf.get("level") in ("low", "medium", "high") else fallback_conf["level"]
    return {
        "verdict": str(raw.get("verdict") or "").strip() or "No clear verdict.",
        "tone": tone,
        "summary": str(raw.get("summary") or "").strip(),
        "paragraphs": paragraphs,
        "citations": cites,
        "confidence": {"level": level, "note": str(conf.get("note") or fallback_conf["note"])},
    }


# --------------------------------------------------------------- detection
def detect(store: Store, question: str, topic: str | None, region_id: str | None) -> tuple[str | None, list[str]]:
    q = (question or "").lower()
    found_topic = None
    best = 0
    for t in store.topics:
        terms = [t.get("name", "").lower(), t["id"].replace("-", " "), t["id"]] + [k.lower() for k in t.get("keywords", [])]
        hits = sum(1 for k in terms if k and len(k) > 1 and re.search(r"\b" + re.escape(k) + r"(s|es)?\b", q))
        if hits > best:
            best, found_topic = hits, t["id"]
    regions: list[str] = []
    for rid, r in store.regions.items():
        names = {r.get("name", "").lower(), rid.replace("-", " ")}
        base = r.get("name", "").lower().split(",")[0].strip()
        names.add(base)
        for nm in names:
            if nm and len(nm) > 2 and re.search(r"\b" + re.escape(nm) + r"\b", q):
                pos = q.find(nm)
                regions.append((pos, rid))
                break
    reg_ids = [rid for _, rid in sorted(regions)]
    t = found_topic or topic
    if not found_topic and reg_ids:
        # Choose the topic with most posts in the mentioned regions (prefer the selected topic on ties).
        ph = ",".join("?" for _ in reg_ids)
        rows = store.q(f"SELECT topic, count(*) c FROM posts WHERE region_id IN ({ph}) GROUP BY topic ORDER BY c DESC", reg_ids)
        counts = dict(rows)
        if rows and counts.get(topic, 0) < rows[0][1] and (not topic or counts.get(topic, 0) == 0 or len(reg_ids) > 1):
            t = rows[0][0]
    if not t and store.topics:
        t = store.topics[0]["id"]
    if not reg_ids and region_id:
        reg_ids = [region_id]
    return t, reg_ids


def _tone(score: int) -> str:
    return "positive" if score >= 8 else "negative" if score <= -8 else "mixed"


# ---------------------------------------------------------------- fallback
def fallback_answer(store: Store, question: str, topic: str | None, region_id: str | None) -> dict:
    tool_calls: list[dict] = []

    def call(name, **args):
        tool_calls.append({"name": name, "args": args})
        return run_tool(store, name, args)

    t, regs = detect(store, question, topic, region_id)
    tname = store.topic_name(t)
    q = (question or "").lower()

    if not t or store.post_count() == 0:
        return {"answer": {
            "verdict": "Not enough data loaded to answer yet.", "tone": "mixed",
            "summary": "No posts are available in the dataset.", "paragraphs": [
                "The Pulse dataset is empty, so there is nothing to analyse yet."],
            "citations": [], "confidence": {"level": "low", "note": "No posts loaded."}}, "tool_calls": tool_calls}

    if any(w in q for w in ("spread", "viral", "travel", "challenge")) and not regs:
        sp = call("spread")
        steps = sp.get("steps") or []
        if steps:
            path = " → ".join(f"{s['name']} (+{s.get('hours', 0)}h)" for s in steps)
            return {"answer": {
                "verdict": f"{sp.get('name') or 'The trend'} moved across {len(steps)} regions in {steps[-1].get('hours', 0)} hours.",
                "tone": "mixed", "summary": f"Spread path: {path}.",
                "paragraphs": [f"The tracked spread event started in {steps[0]['name']} and travelled {path}.",
                               "Timing comes from first-seen post timestamps per region in social data; it is indicative, not a full census."],
                "citations": [], "confidence": {"level": "medium", "note": "Based on seeded spread tracking data; social media signal, not a poll."}},
                "tool_calls": tool_calls}

    cites: list[dict] = []

    def cite(post: dict) -> str:
        for c in cites:
            if c["post_id"] == post["id"]:
                return f"[{c['n']}]"
        c = _citation(store, len(cites) + 1, post["id"])
        if not c:
            return ""
        cites.append(c)
        return f"[{c['n']}]"

    def evidence_line(d: dict, k: int = 2) -> str:
        posts = d.get("posts") or []
        bits = []
        media_first = sorted(posts, key=lambda p: (not p["media"], -p["engagement"]))[:k]
        for p in media_first:
            if p["media"]:
                desc = p.get("caption") or p["media"][0].get("description") or "media"
                extra = f' with on-screen text "{p["ocr"]}"' if p.get("ocr") else ""
                bits.append(f"a {p['source']} {p['media'][0].get('type', 'post')} showing {desc.rstrip('.').lower()}{extra} {cite(p)}")
            else:
                snippet = p["text"][:110].rstrip() + ("…" if len(p["text"]) > 110 else "")
                bits.append(f'a {p["source"]} post saying "{snippet}" {cite(p)}')
        return "; ".join(bits)

    def narr_line(d: dict) -> str:
        ns = d.get("narratives") or []
        if not ns:
            return "no dominant narrative"
        return ", ".join(f"{n['label'].lower()} ({round(n['share'] * 100)}%, {'+' if n['sentiment'] >= 0 else ''}{round(n['sentiment'] * 100)})"
                         for n in ns[:3])

    def caveat(conf: dict) -> str:
        return conf["note"]

    if len(regs) >= 2:
        a, b = regs[0], regs[1]
        res = call("compare", topic=t, region_a=a, region_b=b)
        da, db = res["a"], res["b"]
        if da["count"] == 0 or db["count"] == 0:
            missing = da if da["count"] == 0 else db
            present = db if missing is da else da
            if present["count"] == 0:
                return {"answer": {
                    "verdict": f"Neither {da['name']} nor {db['name']} has enough {tname} posts to compare.",
                    "tone": "mixed", "summary": f"0 posts for both regions on {tname}.",
                    "paragraphs": [f"Pulse has no located posts about {tname} for {da['name']} or {db['name']}. Try another topic or region."],
                    "citations": [], "confidence": {"level": "low", "note": "No data; social media sentiment, not a poll."}},
                    "tool_calls": tool_calls}
            regs = [present["region_id"]]
    if len(regs) >= 2:
        diff = da["score"] - db["score"]
        more = da if diff >= 0 else db
        less = db if diff >= 0 else da
        verdict = (f"{more['name']} feels clearly better about {tname} than {less['name']} ({more['score']:+d} vs {less['score']:+d})."
                   if abs(diff) >= 15 else
                   f"{da['name']} and {db['name']} feel similarly about {tname} ({da['score']:+d} vs {db['score']:+d}).")
        paras = [
            f"{da['name']} scores {da['score']:+d} ({da['mood_label'].lower()}, {da['count']} posts). Main narratives: {narr_line(da)}. Evidence includes {evidence_line(da)}.",
            f"{db['name']} scores {db['score']:+d} ({db['mood_label'].lower()}, {db['count']} posts). Main narratives: {narr_line(db)}. Evidence includes {evidence_line(db)}.",
            f"Caveat: {da['name']} has {da['count']} posts and {db['name']} {db['count']} (confidence {da['confidence']['level']} / {db['confidence']['level']}). This is social media sentiment, not a representative poll.",
        ]
        conf_levels = [da["confidence"]["level"], db["confidence"]["level"]]
        level = "low" if "low" in conf_levels else "medium" if "medium" in conf_levels else "high"
        conf = {"level": level, "note": f"{da['name']}: {da['count']} posts; {db['name']}: {db['count']} posts. Social media sentiment, not a representative poll."}
        tone = _tone(round((da["score"] + db["score"]) / 2)) if abs(diff) < 15 else "mixed"
        summary = f"{da['name']} {da['score']:+d} vs {db['name']} {db['score']:+d} on {tname}."
    elif len(regs) == 1:
        rid = regs[0]
        d = call("region_detail", topic=t, region_id=rid)
        if d["count"] == 0:
            byr = call("sentiment_by_region", topic=t)
            names = ", ".join(r["name"] for r in byr[:5])
            return {"answer": {
                "verdict": f"There isn't enough {tname} conversation located in {store.region_name(rid)} to judge.",
                "tone": "mixed", "summary": f"0 posts for {store.region_name(rid)} on {tname}.",
                "paragraphs": [f"Pulse found no posts about {tname} attributed to {store.region_name(rid)}. Regions with data include {names}."],
                "citations": [], "confidence": {"level": "low", "note": "No posts for this region; social media sentiment, not a poll."}},
                "tool_calls": tool_calls}
        tr = call("trend", topic=t, region_id=rid)["summary"]
        trend_txt = ""
        if tr and tr.get("days", 0) > 10:
            delta = tr["avg_last_10_days"] - tr["avg_earlier"]
            direction = "worsened" if delta <= -8 else "improved" if delta >= 8 else "held roughly steady"
            trend_txt = (f" Over the last 10 days sentiment has {direction} (avg {tr['avg_last_10_days']:+d} vs {tr['avg_earlier']:+d} before).")
        verdict = f"{d['name']} is {d['mood_label'].lower()} on {tname} (score {d['score']:+d})."
        paras = [
            f"Across {d['count']} posts, {d['name']} scores {d['score']:+d}. The conversation is driven by {narr_line(d)}.{trend_txt}",
            f"Representative evidence: {evidence_line(d, 3)}.",
            f"Caveat: {d['confidence']['note']}",
        ]
        conf = d["confidence"]
        tone = _tone(d["score"])
        summary = f"{d['name']}: {d['mood_label']} ({d['score']:+d}) across {d['count']} posts about {tname}."
    else:
        byr = call("sentiment_by_region", topic=t)
        byr = [r for r in byr if not r["low_sample"]] or byr
        if not byr:
            return {"answer": {
                "verdict": f"No regional data for {tname} yet.", "tone": "mixed", "summary": "",
                "paragraphs": [f"There are no located posts about {tname}."], "citations": [],
                "confidence": {"level": "low", "note": "No data; social media sentiment, not a poll."}},
                "tool_calls": tool_calls}
        neg, pos = byr[0], byr[-1]
        neg_list = [r for r in byr if r["score"] < 0][:3] or byr[:1]
        pos_list = [r for r in reversed(byr) if r["score"] >= 0][:3] or byr[-1:]
        total = sum(r["posts"] for r in byr)
        overall = round(sum(r["score"] * r["posts"] for r in byr) / max(total, 1))
        dn = call("region_detail", topic=t, region_id=neg["region_id"])
        dp = call("region_detail", topic=t, region_id=pos["region_id"])
        negs = ", ".join(f"{r['name']} {r['score']:+d}" for r in neg_list)
        poss = ", ".join(f"{r['name']} {r['score']:+d}" for r in pos_list)
        verdict = f"Global mood on {tname} is {mood_label(overall).lower()} ({overall:+d}), but it splits sharply by region."
        paras = [
            f"Most negative: {negs}. In {dn['name']} the talk centres on {narr_line(dn)}, e.g. {evidence_line(dn)}.",
            f"Most positive: {poss}. {dp['name']} is driven by {narr_line(dp)}, e.g. {evidence_line(dp)}.",
            f"Caveat: {store.confidence(t)['note']} Regions with under {5} posts are excluded.",
        ]
        conf = store.confidence(t)
        tone = _tone(overall) if abs(pos["score"] - neg["score"]) < 40 else "mixed"
        summary = f"{len(byr)} regions, {total} posts; overall {overall:+d}."
    paras = [re.sub(r"\s+", " ", p).replace(" .", ".").strip() for p in paras]
    return {"answer": {"verdict": verdict, "tone": tone, "summary": summary, "paragraphs": paras,
                       "citations": cites, "confidence": conf}, "tool_calls": tool_calls}


# ------------------------------------------------------------------- claude
def claude_answer(store: Store, question: str, topic: str | None, region_id: str | None) -> dict:
    import anthropic

    client = anthropic.Anthropic(timeout=60.0, max_retries=1)
    model = os.environ.get("PULSE_AGENT_MODEL", "claude-sonnet-5-5")
    ctx = []
    if topic:
        ctx.append(f"Currently selected topic: {topic}")
    if region_id:
        ctx.append(f"Currently selected region: {region_id} ({store.region_name(region_id)})")
    topic_list = ", ".join(f"{t['id']} ({t.get('name')})" for t in store.topics)
    region_list = ", ".join(f"{rid}={r.get('name')}" for rid, r in store.regions.items())
    user = (f"Question: {question}\n\n" + ("\n".join(ctx) + "\n" if ctx else "")
            + f"Topic ids: {topic_list}\nRegion ids: {region_list}")
    messages: list[dict] = [{"role": "user", "content": user}]
    tools = TOOLS + [SUBMIT_TOOL]
    tool_calls: list[dict] = []
    seen: set[str] = set()

    for i in range(MAX_ITERS + 1):
        force = i == MAX_ITERS
        resp = client.messages.create(
            model=model, max_tokens=2000, system=SYSTEM_PROMPT, tools=tools, messages=messages,
            tool_choice={"type": "tool", "name": "submit_answer"} if force else {"type": "auto"},
        )
        uses = [b for b in resp.content if b.type == "tool_use"]
        submit = next((b for b in uses if b.name == "submit_answer"), None)
        if submit:
            t_guess, _ = detect(store, question, topic, region_id)
            fc = store.confidence(t_guess) if t_guess else {"level": "low", "note": "Social media sentiment, not a poll."}
            ans = finalize_answer(store, dict(submit.input), seen, fc)
            if not ans["paragraphs"]:
                raise RuntimeError("empty answer")
            return {"answer": ans, "tool_calls": tool_calls}
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        if not uses:
            # Model replied in prose; force the structured submission next.
            messages.append({"role": "user", "content": "Now call submit_answer with your final answer."})
            resp2 = client.messages.create(
                model=model, max_tokens=2000, system=SYSTEM_PROMPT, tools=tools, messages=messages,
                tool_choice={"type": "tool", "name": "submit_answer"})
            sub = next((b for b in resp2.content if b.type == "tool_use" and b.name == "submit_answer"), None)
            if not sub:
                raise RuntimeError("no submit_answer")
            t_guess, _ = detect(store, question, topic, region_id)
            return {"answer": finalize_answer(store, dict(sub.input), seen, store.confidence(t_guess)),
                    "tool_calls": tool_calls}
        results = []
        for b in uses:
            args = dict(b.input or {})
            tool_calls.append({"name": b.name, "args": args})
            try:
                out = run_tool(store, b.name, args)
            except Exception as e:  # noqa: BLE001
                out = {"error": str(e)}
            _collect_post_ids(out, seen)
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": json.dumps(out, default=str)[:20000]})
        messages.append({"role": "user", "content": results})
    raise RuntimeError("agent loop exhausted")


def ask(store: Store, question: str, topic: str | None, region_id: str | None) -> dict:
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return claude_answer(store, question, topic, region_id)
        except Exception as e:  # noqa: BLE001
            log.warning("Claude agent failed, using fallback: %s", e)
    return fallback_answer(store, question, topic, region_id)
