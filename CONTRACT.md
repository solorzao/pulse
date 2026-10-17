# Pulse — shared contract (read this first)

Hackathon MVP: a globe showing how people in each region feel about a topic, built from (mock) social posts incl. images/video, plus an agent you can ask questions. Mock data first; real sources later behind the same interface.

## Repo layout
```
api/        FastAPI + DuckDB (in-memory) + Claude agent loop   → Azure Container Apps (port 8000)
web/        Next.js (App Router, TS, Tailwind) + react-globe.gl  → Vercel (root dir = web/)
scripts/    generate_seed.py (raw mock posts), enrich.py (Claude enrichment), mock_enrich.py (no-API fallback)
seed/       committed data files (below)
infra/      deploy-azure.sh (az CLI)
.github/workflows/api.yml   build api image → ACR → update Container App
```
Docker build context for the API is the **repo root**: `docker build -f api/Dockerfile .` — the image copies `api/` and `seed/`.

## Topic ids
`ai-datacenters`, `electric-scooters`, `four-day-week`

## Seed files
- `seed/topics.json` — `[{ "id", "name", "keywords": [str] }]`
- `seed/regions.json` — `[{ "id": "ireland", "name": "Ireland", "country": "IE", "lat": 53.3, "lon": -8.0 }]` (~40 regions worldwide; ids are lowercase-hyphen slugs, e.g. `virginia-us`, `ho-chi-minh-city`)
- `seed/raw/<topic>.jsonl` — one RawPost per line:
  `{ "id", "topic", "source": "bluesky|reddit|youtube|tiktok|mastodon|news", "community": "r/ireland"|null, "author_loc": str|null, "lang": "en", "text", "media": [{ "type": "image|video", "description": str, "url": null }], "ts": ISO8601 UTC, "url": str, "engagement": int }`
- `seed/enriched/<topic>.jsonl` — RawPost fields plus:
  `{ "sentiment": float -1..1, "narrative": str, "region_id": str, "region_conf": float 0..1, "caption": str|null, "ocr": str|null }`
- `seed/spread.json` — `{ "id", "name", "steps": [{ "region_id", "hours": number, "note", "count": int }], "arcs": [[from_region_id, to_region_id]] }`
- `seed/trending.json` — `[{ "id", "name", "category": "Culture|News|Meme|Tech", "regions": [str], "format": str, "velocity": int (-3..3), "sentiment": float, "count": int }]`

## API (all JSON; CORS open to localhost and *.vercel.app)
- `GET /health` → `{ "ok": true, "posts": int }`
- `GET /topics` → `[{ "id", "name", "post_count", "mood": int -100..100 }]`
- `GET /globe?topic=ID&days=30` → `{ "topic", "points": [{ "region_id", "name", "lat", "lon", "score": int -100..100, "volume": int, "norm_volume": float 0..1 }] }`
- `GET /region?topic=ID&region_id=ID` → `{ "region_id", "name", "topic", "score", "mood_label", "count", "narratives": [{ "label", "share": 0..1, "sentiment": float }], "posts": [ up to 5 enriched posts, highest engagement, include media+caption ], "trend": [{ "date": "YYYY-MM-DD", "score": int }], "confidence": { "level": "low|medium|high", "note": str } }`
- `GET /spread` → contents of seed/spread.json, with `lat`, `lon`, `name` added to each step
- `GET /trending` → contents of seed/trending.json
- `POST /ask` body `{ "question": str, "topic": str|null, "region_id": str|null }` →
  `{ "answer": { "verdict": str, "tone": "positive|negative|mixed", "summary": str, "paragraphs": [str], "citations": [{ "n": int, "post_id", "source", "text", "url" }], "confidence": { "level", "note" } }, "tool_calls": [{ "name", "args": {} }] }`
  Paragraphs reference citations inline as `[1]`, `[2]`. If `ANTHROPIC_API_KEY` is unset, return a deterministic answer assembled from the same tool functions (demo must never break).

Score = round(mean sentiment × 100). mood_label: ≥25 Very positive, ≥8 Positive, >−8 Mixed, >−25 Negative, else Very negative.

## Env vars
- API: `ANTHROPIC_API_KEY`, `PULSE_AGENT_MODEL` (default `claude-sonnet-5-5`), `PULSE_SEED_DIR` (default `../seed` relative to api/, `/app/seed` in Docker), `CORS_ORIGINS` (optional extra, comma-separated)
- scripts: `ANTHROPIC_API_KEY`, `PULSE_ENRICH_MODEL` (default `claude-haiku-5-5`)
- web: `NEXT_PUBLIC_API_URL` (e.g. http://localhost:8000)

## Demo stories baked into the data
- ai-datacenters: Ireland very negative (power grid), Virginia negative (noise, power bills), Arizona negative (water), Texas mixed, Netherlands negative (farmland), Sweden positive (hydro), Hyderabad positive (jobs), Johor positive, Santiago negative (water). Ireland worsens over the last 10 days.
- electric-scooters: Jakarta & Ho Chi Minh City very positive, Bangkok positive, Manila slightly positive, Singapore negative (battery fires; dip after a viral fire ~13 days ago), Paris negative (rental clutter), Los Angeles mixed-positive.
- four-day-week: UK very positive, Germany positive, New York positive, Tokyo mixed, Sydney positive, Bangalore slightly negative ("longer days instead"), Seoul mixed-positive.
- spread.json: a dance challenge Seoul(0h) → Manila(+2h) → Jakarta(+4h) → Los Angeles(+5h) → São Paulo(+6h).

Product name: **Pulse**. Visual style: dark (#05070B ground), diverging sentiment orange #FF8A3D (neg) ↔ grey #A7B0BD ↔ blue #4C9BFF (pos), lime accent #C8F25A, IBM Plex Sans/Mono.
