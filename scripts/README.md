# Pulse data scripts

All scripts run from the repo root and read/write `seed/`. `generate_seed.py`, `mock_enrich.py` and `check_seed.py` only use the standard library.

```bash
# 1. Generate the raw mock posts. This is deterministic and writes
#    seed/raw/<topic>.jsonl plus a <topic>.truth.jsonl ground-truth file for each topic.
python scripts/generate_seed.py            # flags: --seed 42 --now 2026-10-17T12:00:00Z --scale 1.0

# 2a. Enrich without an API key (uses the ground truth plus some noise) -> seed/enriched/<topic>.jsonl
python scripts/mock_enrich.py

# 2b. Or enrich for real with Claude (overwrites seed/enriched/<topic>.jsonl once >=97% of posts are done)
pip install -r scripts/requirements.txt
export ANTHROPIC_API_KEY=sk-...            # optional: PULSE_ENRICH_MODEL (default claude-haiku-5-5)
python scripts/enrich.py --topic ai-datacenters --limit 40   # cheap smoke test
python scripts/enrich.py                   # all topics; batch 20, concurrency 8, resumable

# 3. Sanity check: per-region scores for the story regions, plus the Ireland and Singapore daily trends
python scripts/check_seed.py
```

Notes
- `enrich.py` saves progress to `seed/.enrich-cache/<topic>.jsonl`. If you re-run it, it skips posts that are already enriched. `--fresh` starts over.
- Posts that Claude can't map to a region id from `regions.json` are dropped.
- The seed covers the 30 days up to `--now`. If you change `--now`, the "last 10 days" story trends move with it.
