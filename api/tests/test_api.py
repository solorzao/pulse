import os
import re
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "seed"
SEED = os.environ.get("PULSE_TEST_SEED_DIR", str(FIXTURE))
os.environ["PULSE_SEED_DIR"] = SEED
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.store import Store  # noqa: E402


@pytest.fixture(scope="module")
def client():
    main.STATE.pop("store", None)
    with TestClient(main.app) as c:
        yield c


def first_topic(client):
    return client.get("/topics").json()[0]["id"]


def test_health(client):
    r = client.get("/health").json()
    assert r["ok"] is True and r["posts"] > 0


def test_topics(client):
    ts = client.get("/topics").json()
    assert {t["id"] for t in ts} >= {"ai-datacenters", "electric-scooters", "four-day-week"}
    for t in ts:
        assert set(t) == {"id", "name", "post_count", "mood"}
        assert -100 <= t["mood"] <= 100


def test_globe(client):
    r = client.get("/globe", params={"topic": "ai-datacenters", "days": 30}).json()
    assert r["topic"] == "ai-datacenters" and r["points"]
    for p in r["points"]:
        assert set(p) == {"region_id", "name", "lat", "lon", "score", "volume", "norm_volume"}
        assert p["volume"] >= 5 and 0 <= p["norm_volume"] <= 1
    ireland = next(p for p in r["points"] if p["region_id"] == "ireland")
    assert ireland["score"] < 0
    if SEED == str(FIXTURE):  # tokyo has only 3 posts in the fixture
        assert "tokyo" not in {p["region_id"] for p in r["points"]}


def test_globe_unknown_topic(client):
    assert client.get("/globe", params={"topic": "nope"}).json() == {"topic": "nope", "points": []}


def test_region(client):
    r = client.get("/region", params={"topic": "ai-datacenters", "region_id": "ireland"}).json()
    for k in ["region_id", "name", "topic", "score", "mood_label", "count", "narratives", "posts", "trend", "confidence"]:
        assert k in r
    assert r["mood_label"] == "Very negative"
    assert 0 < len(r["posts"]) <= 5
    assert any(p["media"] for p in r["posts"])
    assert abs(sum(n["share"] for n in r["narratives"]) - 1) < 0.05 or len(r["narratives"]) == 6
    assert re.match(r"\d{4}-\d{2}-\d{2}", r["trend"][0]["date"])
    assert r["confidence"]["level"] in ("low", "medium", "high")
    assert "not a representative poll" in r["confidence"]["note"]


def test_region_empty(client):
    r = client.get("/region", params={"topic": "ai-datacenters", "region_id": "atlantis"}).json()
    assert r["count"] == 0 and r["posts"] == [] and r["confidence"]["level"] == "low"


def test_spread(client):
    r = client.get("/spread").json()
    assert r["steps"] and all({"lat", "lon", "name", "region_id", "hours"} <= set(s) for s in r["steps"])
    assert isinstance(r["arcs"], list)


def test_trending(client):
    r = client.get("/trending").json()
    assert isinstance(r, list) and r and "velocity" in r[0]


def _check_answer(body):
    a = body["answer"]
    assert set(a) == {"verdict", "tone", "summary", "paragraphs", "citations", "confidence"}
    assert a["tone"] in ("positive", "negative", "mixed")
    assert a["verdict"] and len(a["paragraphs"]) >= 1
    for c in a["citations"]:
        assert set(c) == {"n", "post_id", "source", "text", "url"}
    ns = {c["n"] for c in a["citations"]}
    for m in re.findall(r"\[(\d+)\]", " ".join(a["paragraphs"])):
        assert int(m) in ns
    assert isinstance(body["tool_calls"], list) and body["tool_calls"]
    return a


@pytest.mark.parametrize("q,topic,region", [
    ("How does Ireland feel about AI datacenters?", None, None),
    ("Why is it so negative here?", "ai-datacenters", "ireland"),
    ("Compare Ireland and Sweden on data centers", None, None),
    ("Where are people most negative?", "electric-scooters", None),
    ("How did the dance challenge spread?", None, None),
    ("What does Atlantis think?", "four-day-week", None),
])
def test_ask_fallback(client, q, topic, region):
    r = client.post("/ask", json={"question": q, "topic": topic, "region_id": region})
    assert r.status_code == 200
    _check_answer(r.json())


def test_ask_region_cites_posts(client):
    a = _check_answer(client.post("/ask", json={"question": "How does Ireland feel about AI datacenters?"}).json())
    assert a["tone"] == "negative" and len(a["paragraphs"]) >= 2 and a["citations"]


def test_ask_claude_failure_falls_back(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-invalid")
    from app import agent

    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(agent, "claude_answer", boom)
    _check_answer(client.post("/ask", json={"question": "Ireland datacenters?"}).json())


def test_missing_seed_dir(tmp_path):
    s = Store(tmp_path / "nope")
    assert s.post_count() == 0
    assert s.globe("ai-datacenters") == {"topic": "ai-datacenters", "points": []}
    assert s.spread()["steps"] == []
    from app.agent import fallback_answer
    assert fallback_answer(s, "hi", None, None)["answer"]["verdict"]


def test_claude_loop_with_fake_client(client, monkeypatch):
    """Exercise the tool-use loop with a fake Anthropic client (no network)."""
    import sys
    import types
    from types import SimpleNamespace as NS

    from app import agent

    class Block(NS):
        def model_dump(self, exclude_none=True):
            return {k: v for k, v in vars(self).items() if v is not None}

    store = main.get_store()
    pid = store.top_posts("ai-datacenters", "ireland", 1)[0]["id"]
    script = [
        [Block(type="tool_use", id="t1", name="region_detail", input={"topic": "ai-datacenters", "region_id": "ireland"})],
        [Block(type="tool_use", id="t2", name="submit_answer", input={
            "verdict": "Ireland is sour.", "tone": "negative", "summary": "s",
            "paragraphs": ["Grid worries dominate [1]. Fake cite [9]."],
            "citations": [{"n": 1, "post_id": pid}, {"n": 9, "post_id": "made-up"}],
            "confidence": {"level": "medium", "note": "n"}})],
    ]

    class FakeMessages:
        def create(self, **kw):
            return NS(content=script.pop(0))

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda **kw: NS(messages=FakeMessages())
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    out = agent.claude_answer(store, "Ireland datacenters?", None, None)
    a = out["answer"]
    assert out["tool_calls"] == [{"name": "region_detail", "args": {"topic": "ai-datacenters", "region_id": "ireland"}}]
    assert [c["post_id"] for c in a["citations"]] == [pid]
    assert a["citations"][0]["url"] and a["paragraphs"] == ["Grid worries dominate [1]. Fake cite."]
