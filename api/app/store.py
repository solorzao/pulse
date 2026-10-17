"""In-memory DuckDB store loaded from seed files, plus the query functions
shared by the HTTP endpoints and the agent tools."""
from __future__ import annotations

import glob
import json
import logging
import os
import threading
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

log = logging.getLogger("pulse.store")

MIN_GLOBE_POSTS = 5

POST_COLS = [
    "id", "topic", "source", "community", "author_loc", "lang", "text", "media",
    "ts", "url", "engagement", "sentiment", "narrative", "region_id",
    "region_conf", "caption", "ocr",
]


def default_seed_dir() -> Path:
    env = os.environ.get("PULSE_SEED_DIR")
    if env:
        return Path(env)
    # api/app/store.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "seed"


def mood_label(score: int) -> str:
    if score >= 25:
        return "Very positive"
    if score >= 8:
        return "Positive"
    if score > -8:
        return "Mixed"
    if score > -25:
        return "Negative"
    return "Very negative"


def _load_json(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning("seed file missing: %s", path)
    except Exception as e:  # noqa: BLE001
        log.warning("failed to load %s: %s", path, e)
    return default


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class Store:
    def __init__(self, seed_dir: Path | str | None = None):
        self.seed_dir = Path(seed_dir) if seed_dir else default_seed_dir()
        self.lock = threading.Lock()
        self.con = duckdb.connect(":memory:")
        self.regions: dict[str, dict] = {}
        self.topics: list[dict] = []
        self.spread_raw: dict = {}
        self.trending: list = []
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        sd = self.seed_dir
        regions = _load_json(sd / "regions.json", [])
        self.regions = {r["id"]: r for r in regions if isinstance(r, dict) and "id" in r}
        topics = _load_json(sd / "topics.json", [])
        self.topics = [t for t in topics if isinstance(t, dict) and "id" in t]
        self.spread_raw = _load_json(sd / "spread.json", {}) or {}
        self.trending = _load_json(sd / "trending.json", []) or []

        rows = []
        for fp in sorted(glob.glob(str(sd / "enriched" / "*.jsonl"))):
            topic_from_file = Path(fp).stem
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        p = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not p.get("id"):
                        continue
                    rows.append((
                        str(p["id"]), p.get("topic") or topic_from_file, p.get("source"),
                        p.get("community"), p.get("author_loc"), p.get("lang"),
                        p.get("text") or "", json.dumps(p.get("media") or []),
                        p.get("ts"), p.get("url"), int(_f(p.get("engagement"))),
                        max(-1.0, min(1.0, _f(p.get("sentiment")))), p.get("narrative") or "Other",
                        p.get("region_id"), _f(p.get("region_conf"), 0.5),
                        p.get("caption"), p.get("ocr"),
                    ))
        # Dedupe by id (last wins)
        rows = list({r[0]: r for r in rows}.values())

        with self.lock:
            c = self.con
            c.execute("DROP TABLE IF EXISTS posts")
            c.execute("""CREATE TABLE posts (
                id VARCHAR, topic VARCHAR, source VARCHAR, community VARCHAR,
                author_loc VARCHAR, lang VARCHAR, text VARCHAR, media VARCHAR,
                ts_raw VARCHAR, url VARCHAR, engagement BIGINT, sentiment DOUBLE,
                narrative VARCHAR, region_id VARCHAR, region_conf DOUBLE,
                caption VARCHAR, ocr VARCHAR)""")
            if rows:
                c.executemany("INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            c.execute("""ALTER TABLE posts ADD COLUMN ts TIMESTAMP""")
            c.execute("""UPDATE posts SET ts = TRY_CAST(replace(replace(ts_raw,'Z',''),'T',' ') AS TIMESTAMP)""")
            c.execute("""ALTER TABLE posts ADD COLUMN has_media BOOLEAN""")
            c.execute("""UPDATE posts SET has_media = (media <> '[]')""")
            c.execute("DROP TABLE IF EXISTS regions")
            c.execute("CREATE TABLE regions (id VARCHAR, name VARCHAR, country VARCHAR, lat DOUBLE, lon DOUBLE)")
            if self.regions:
                c.executemany("INSERT INTO regions VALUES (?,?,?,?,?)", [
                    (r["id"], r.get("name", r["id"]), r.get("country"), _f(r.get("lat")), _f(r.get("lon")))
                    for r in self.regions.values()])
        # Topics that only exist in posts (topics.json missing) still get listed.
        known = {t["id"] for t in self.topics}
        for (tid,) in self.q("SELECT DISTINCT topic FROM posts WHERE topic IS NOT NULL ORDER BY 1"):
            if tid not in known:
                self.topics.append({"id": tid, "name": tid.replace("-", " ").title(), "keywords": []})
        log.info("loaded %d posts, %d regions, %d topics from %s",
                 len(rows), len(self.regions), len(self.topics), sd)

    def q(self, sql: str, params: list | tuple = ()) -> list[tuple]:
        with self.lock:
            return self.con.execute(sql, params).fetchall()

    def qd(self, sql: str, params: list | tuple = ()) -> list[dict]:
        with self.lock:
            cur = self.con.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    # --------------------------------------------------------------- helpers
    def post_count(self) -> int:
        return self.q("SELECT count(*) FROM posts")[0][0]

    def region_name(self, rid: str | None) -> str:
        if not rid:
            return ""
        r = self.regions.get(rid)
        return r.get("name", rid) if r else rid.replace("-", " ").title()

    def topic_name(self, tid: str | None) -> str:
        for t in self.topics:
            if t["id"] == tid:
                return t.get("name", tid)
        return (tid or "").replace("-", " ")

    def _since_clause(self, days: int | None) -> tuple[str, list]:
        """Window is relative to the newest post in the dataset (mock data
        may not be 'today')."""
        if not days or days <= 0:
            return "", []
        return " AND ts >= (SELECT max(ts) FROM posts) - to_days(CAST(? AS INTEGER))", [int(days)]

    def format_post(self, row: dict, text_limit: int | None = None) -> dict:
        try:
            media = json.loads(row.get("media") or "[]")
        except Exception:  # noqa: BLE001
            media = []
        text = row.get("text") or ""
        if text_limit and len(text) > text_limit:
            text = text[: text_limit - 1].rstrip() + "…"
        return {
            "id": row["id"], "topic": row.get("topic"), "source": row.get("source"),
            "community": row.get("community"), "author_loc": row.get("author_loc"),
            "lang": row.get("lang"), "text": text, "media": media,
            "ts": row.get("ts_raw"), "url": row.get("url"),
            "engagement": int(row.get("engagement") or 0),
            "sentiment": round(float(row.get("sentiment") or 0), 3),
            "narrative": row.get("narrative"), "region_id": row.get("region_id"),
            "region_conf": round(float(row.get("region_conf") or 0), 3),
            "caption": row.get("caption"), "ocr": row.get("ocr"),
        }

    def get_post(self, post_id: str) -> dict | None:
        rows = self.qd("SELECT * FROM posts WHERE id = ?", [post_id])
        return self.format_post(rows[0]) if rows else None

    # ------------------------------------------------------------- endpoints
    def topics_summary(self) -> list[dict]:
        stats = {r[0]: (r[1], r[2]) for r in self.q(
            "SELECT topic, count(*), avg(sentiment) FROM posts GROUP BY topic")}
        out = []
        for t in self.topics:
            n, m = stats.get(t["id"], (0, None))
            out.append({"id": t["id"], "name": t.get("name", t["id"]), "post_count": int(n),
                        "mood": int(round((m or 0) * 100))})
        return out

    def globe(self, topic: str, days: int | None = 30) -> dict:
        since, sp = self._since_clause(days)
        rows = self.q(f"""
            SELECT region_id, count(*) n, avg(sentiment) s FROM posts
            WHERE topic = ? AND region_id IS NOT NULL {since}
            GROUP BY region_id HAVING count(*) >= ? ORDER BY n DESC""",
                      [topic, *sp, MIN_GLOBE_POSTS])
        rows = [r for r in rows if r[0] in self.regions]
        maxv = max((r[1] for r in rows), default=1) or 1
        points = []
        for rid, n, s in rows:
            reg = self.regions[rid]
            points.append({"region_id": rid, "name": reg.get("name", rid),
                           "lat": _f(reg.get("lat")), "lon": _f(reg.get("lon")),
                           "score": int(round((s or 0) * 100)), "volume": int(n),
                           "norm_volume": round(n / maxv, 4)})
        return {"topic": topic, "points": points}

    def confidence(self, topic: str, region_id: str | None = None) -> dict:
        where, params = "topic = ?", [topic]
        if region_id:
            where += " AND region_id = ?"
            params.append(region_id)
        n, mc = self.q(f"SELECT count(*), avg(region_conf) FROM posts WHERE {where}", params)[0]
        n = int(n or 0)
        mc = float(mc or 0)
        srcs = self.q(f"SELECT source, count(*) c FROM posts WHERE {where} GROUP BY source ORDER BY c DESC", params)
        if n >= 40 and mc >= 0.6:
            level = "high"
        elif n >= 15 and mc >= 0.45:
            level = "medium"
        else:
            level = "low"
        mix = ", ".join(f"{s or 'unknown'} {round(100 * c / n)}%" for s, c in srcs[:4]) if n else "none"
        note = (f"Based on {n} social posts (mean location confidence {mc:.2f}); source mix: {mix}. "
                "Social media sentiment, not a representative poll.")
        if n and n < 15:
            note = "Small sample. " + note
        return {"level": level, "note": note}

    def narratives(self, topic: str, region_id: str | None = None, limit: int = 6) -> list[dict]:
        where, params = "topic = ?", [topic]
        if region_id:
            where += " AND region_id = ?"
            params.append(region_id)
        rows = self.q(f"""SELECT narrative, count(*) c, avg(sentiment) s FROM posts WHERE {where}
                          GROUP BY narrative ORDER BY c DESC LIMIT ?""", [*params, limit])
        total = self.q(f"SELECT count(*) FROM posts WHERE {where}", params)[0][0] or 1
        return [{"label": r[0], "share": round(r[1] / total, 3), "sentiment": round(r[2] or 0, 3)}
                for r in rows]

    def trend(self, topic: str, region_id: str | None = None) -> list[dict]:
        where, params = "topic = ? AND ts IS NOT NULL", [topic]
        if region_id:
            where += " AND region_id = ?"
            params.append(region_id)
        rows = self.q(f"""SELECT strftime(CAST(ts AS DATE), '%Y-%m-%d') d, avg(sentiment), count(*)
                          FROM posts WHERE {where} GROUP BY 1 ORDER BY 1""", params)
        return [{"date": d, "score": int(round((s or 0) * 100))} for d, s, _ in rows]

    def top_posts(self, topic: str, region_id: str | None, limit: int = 5,
                  min_media: int = 2, text_limit: int | None = None) -> list[dict]:
        where, params = "topic = ?", [topic]
        if region_id:
            where += " AND region_id = ?"
            params.append(region_id)
        top = self.qd(f"SELECT * FROM posts WHERE {where} ORDER BY engagement DESC LIMIT ?", [*params, limit])
        n_media = sum(1 for r in top if r["has_media"])
        if n_media < min_media:
            need = min_media - n_media
            ids = [r["id"] for r in top]
            extra = self.qd(f"""SELECT * FROM posts WHERE {where} AND has_media
                                AND NOT list_contains(?, id) ORDER BY engagement DESC LIMIT ?""",
                            [*params, ids, need])
            if extra:
                # replace the lowest-engagement non-media posts
                non_media = [r for r in top if not r["has_media"]]
                for e in extra:
                    if non_media:
                        top.remove(non_media.pop())
                    top.append(e)
                top.sort(key=lambda r: r["engagement"], reverse=True)
        return [self.format_post(r, text_limit) for r in top[:limit]]

    def region(self, topic: str, region_id: str) -> dict:
        n, s = self.q("SELECT count(*), avg(sentiment) FROM posts WHERE topic=? AND region_id=?",
                      [topic, region_id])[0]
        score = int(round((s or 0) * 100))
        return {
            "region_id": region_id, "name": self.region_name(region_id), "topic": topic,
            "score": score, "mood_label": mood_label(score), "count": int(n or 0),
            "narratives": self.narratives(topic, region_id),
            "posts": self.top_posts(topic, region_id),
            "trend": self.trend(topic, region_id),
            "confidence": self.confidence(topic, region_id),
        }

    def spread(self) -> dict:
        sp = json.loads(json.dumps(self.spread_raw or {}))
        if not sp:
            return {"id": None, "name": None, "steps": [], "arcs": []}
        for st in sp.get("steps", []) or []:
            reg = self.regions.get(st.get("region_id"), {})
            st["lat"] = _f(reg.get("lat"))
            st["lon"] = _f(reg.get("lon"))
            st["name"] = reg.get("name", st.get("region_id"))
        sp.setdefault("steps", [])
        sp.setdefault("arcs", [])
        return sp

    def search_posts(self, query: str, topic: str | None = None, region_id: str | None = None,
                     limit: int = 8) -> list[dict]:
        words = [w for w in "".join(ch if ch.isalnum() or ch in "-' " else " " for ch in (query or "").lower()).split()
                 if len(w) > 2][:8]
        where, params = ["1=1"], []
        if topic:
            where.append("topic = ?")
            params.append(topic)
        if region_id:
            where.append("region_id = ?")
            params.append(region_id)
        hay = "lower(coalesce(text,'') || ' ' || coalesce(caption,'') || ' ' || coalesce(ocr,'') || ' ' || coalesce(narrative,''))"
        if words:
            score_expr = " + ".join([f"CASE WHEN {hay} LIKE ? THEN 1 ELSE 0 END" for _ in words])
            wparams = [f"%{w}%" for w in words]
            sql = f"""SELECT *, ({score_expr}) hits FROM posts WHERE {' AND '.join(where)}
                      AND ({score_expr}) > 0 ORDER BY hits DESC, engagement DESC LIMIT ?"""
            rows = self.qd(sql, [*wparams, *params, *wparams, max(1, min(int(limit), 25))])
        else:
            rows = self.qd(f"SELECT * FROM posts WHERE {' AND '.join(where)} ORDER BY engagement DESC LIMIT ?",
                           [*params, max(1, min(int(limit), 25))])
        return [self.format_post(r, 280) for r in rows]

    def sentiment_by_region(self, topic: str) -> list[dict]:
        rows = self.q("""SELECT region_id, count(*) n, avg(sentiment) s, avg(region_conf) c FROM posts
                         WHERE topic=? AND region_id IS NOT NULL GROUP BY region_id ORDER BY s""", [topic])
        out = []
        for rid, n, s, c in rows:
            sc = int(round((s or 0) * 100))
            out.append({"region_id": rid, "name": self.region_name(rid), "score": sc,
                        "mood_label": mood_label(sc), "posts": int(n),
                        "mean_region_conf": round(c or 0, 2), "low_sample": n < MIN_GLOBE_POSTS})
        return out

    def source_mix(self, topic: str, region_id: str | None = None) -> dict:
        where, params = "topic = ?", [topic]
        if region_id:
            where += " AND region_id = ?"
            params.append(region_id)
        return dict(Counter({s: c for s, c in self.q(
            f"SELECT source, count(*) FROM posts WHERE {where} GROUP BY source", params)}))
