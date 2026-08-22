# cinematic-01 smoke run: run-20260822-192623-local-gguf

- **model**: `local-gguf` — LFM2.5-2.6B Q8_0 GGUF (LiquidAI/LFM2.5-2.6B-GGUF)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, llama.cpp engine)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `6` rows (round-robin across studios)
- **mode**: `enabled` reasoning, `4` workers
- **run_at**: `2026-08-22T19:26:46+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **3/6** (50%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **4/6** (67%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.333** | 0.8 | **FAIL** |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 6 | 0 | 6 | 1747 | 3.96s |
| 2 | 6 | 0 | 6 | 1745 | 3.34s |
| 3 | 6 | 0 | 6 | 1165 | 1.82s |

## Cache demo — identical prompt, three calls

| Call | Prompt | Regime | Latency | Cache header |
|------|--------|--------|---------|--------------|
| Q1 | base | `litellm-redis-miss` | 1.9177s | — |
| Q2 | base | `litellm-redis-hit` | 0.0110s | — |
| Q3 | base + suffix | `litellm-redis-miss` | 1.9468s | — |

Call Q2 reuses the Q1 response from Redis — the GPU never wakes up.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. |
| Walt Disney Pictures | The Lion King | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Dark Knight Rises | Legendary Entertainment |

## Re-run

```sh
pixi run cinematic-01-test
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260822-192623-local-gguf/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260822-192623-local-gguf/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260822-192623-local-gguf/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-22T19:26:52+0200.*
