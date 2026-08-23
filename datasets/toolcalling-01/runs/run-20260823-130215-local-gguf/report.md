# toolcalling-01 smoke run: run-20260823-130215-local-gguf

- **model**: `local-gguf` — LFM2.5-2.6B Q8_0 GGUF (LocalAI llama.cpp)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/toolcalling-01/scenarios.json`
- **scenarios**: `6`
- **temperature**: `0.1`
- **workers**: `4`
- **run_at**: `2026-08-23T13:02:19+0200`
- **test**: `smoketests/toolcalling-01/test.py`

## Tool-call scoring

| Criterion | Score | Fraction |
|-----------|-------|----------|
| tool_calls emitted | **6/6 (100%)** | 100% |
| correct tool name | **6/6 (100%)** | 100% |
| correct arguments | **5/6 (83%)** | 83% |
| pythonic syntax | **6/6 (100%)** | 100% |
| mock round-trip | **6/6 (100%)** | 100% |

## Per-scenario detail

| Scenarios | tool_calls | name_ok | args_ok | syntax_ok | pythonic | round_trip_ok | seconds |
|-----------|------------|---------|---------|-----------|----------|---------------|---------|
| calc-bill | 1 | Y | n | Y | `calculate(expression='120 * 0.15')` | Y | 1.66s |
| calc-multiply | 1 | Y | Y | Y | `calculate(expression='12 * 7')` | Y | 0.88s |
| film-inception | 1 | Y | Y | Y | `lookup_film_year(title='Inception', studio='W...` | Y | 0.82s |
| film-totoro | 1 | Y | Y | Y | `lookup_film_year(title='My Neighbor Totoro', ...` | Y | 1.19s |
| weather-prague | 1 | Y | Y | Y | `get_weather(location='Prague')` | Y | 1.38s |
| weather-tokyo | 1 | Y | Y | Y | `get_weather(location='Tokyo')` | Y | 1.28s |

## Re-run

```sh
pixi run toolcalling-01-test -- --model local-gguf --temperature 0.1
pixi run toolcalling-01-report
```

Artifacts for this report:

- `datasets/toolcalling-01/runs/run-20260823-130215-local-gguf/results.json` — raw rows
- `datasets/toolcalling-01/runs/run-20260823-130215-local-gguf/eval.json` — scored scenarios
- `datasets/toolcalling-01/runs/run-20260823-130215-local-gguf/report.md` — this report
- latest copies: `datasets/toolcalling-01/results.json`, `eval.json`

---

*Rendered by `smoketests/toolcalling-01/report.py` at 2026-08-23T13:02:41+0200.*
