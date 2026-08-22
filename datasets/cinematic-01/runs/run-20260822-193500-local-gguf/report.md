# cinematic-01 smoke run: run-20260822-193500-local-gguf

- **model**: `local-gguf` — LFM2.5-2.6B Q8_0 GGUF (LiquidAI/LFM2.5-2.6B-GGUF)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, llama.cpp engine)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `20` rows (round-robin across studios)
- **mode**: `enabled` reasoning, `4` workers
- **run_at**: `2026-08-22T19:35:33+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **6/20** (30%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **15/20** (75%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.6** | 0.8 | **FAIL** |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 20 | 6 | 14 | 5540 | 2.45s |
| 2 | 20 | 6 | 14 | 5609 | 1.85s |
| 3 | 20 | 6 | 14 | 4198 | 1.46s |

## Cache demo — identical prompt, three calls

| Call | Prompt | Regime | Latency | Cache header |
|------|--------|--------|---------|--------------|
| Q1 | base | `litellm-redis-hit` | 0.0077s | — |
| Q2 | base | `litellm-redis-hit` | 0.0167s | — |
| Q3 | base + suffix | `litellm-redis-hit` | 0.0072s | — |

Call Q2 reuses the Q1 response from Redis — the GPU never wakes up.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. |
| Walt Disney Pictures | The Lion King | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Dark Knight Rises | Legendary Entertainment |
| Paramount Pictures | Star Wars: Episode IV – A New Hope | 20th Century Fox |
| Sony Pictures | Spider-Man: Into the Spider-Verse | Sony Pictures Animation |
| Columbia Pictures | Gone with the Wind | MGM |
| 20th Century Studios | Ratatouille | Pixar Animation Studios |
| Lionsgate Films | The Fast and the Furious | Lionsgate |
| A24 | Get Out | Focus Features |
| Metro-Goldwyn-Mayer | Singin' in the Rain | MGM |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| Focus Features | The Last Samurai | Paramount Pictures |
| Searchlight Pictures | Sully | Paramount Pictures |
| Netflix | The Irishman | A24 |

## Re-run

```sh
pixi run cinematic-01-test
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260822-193500-local-gguf/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260822-193500-local-gguf/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260822-193500-local-gguf/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-22T19:35:41+0200.*
