# toolcalling-01 smoke run: run-20260823-130047-local-vllm

- **model**: `local-vllm` — LFM2.5-2.6B W8A16 (vLLM)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/toolcalling-01/scenarios.json`
- **scenarios**: `6`
- **temperature**: `0.1`
- **workers**: `4`
- **run_at**: `2026-08-23T13:00:52+0200`
- **test**: `smoketests/toolcalling-01/test.py`

## Tool-call scoring

| Criterion | Score | Fraction |
|-----------|-------|----------|
| tool_calls emitted | **6/6 (100%)** | 100% |
| correct tool name | **6/6 (100%)** | 100% |
| correct arguments | **6/6 (100%)** | 100% |
| pythonic syntax | **6/6 (100%)** | 100% |
| mock round-trip | **6/6 (100%)** | 100% |

## Per-scenario detail

| Scenarios | tool_calls | name_ok | args_ok | syntax_ok | pythonic | round_trip_ok | seconds |
|-----------|------------|---------|---------|-----------|----------|---------------|---------|
| calc-bill | 1 | Y | Y | Y | `calculate(expression='0.15 * 120')` | Y | 1.64s |
| calc-multiply | 1 | Y | Y | Y | `calculate(expression='12 * 7')` | Y | 1.45s |
| film-inception | 1 | Y | Y | Y | `lookup_film_year(title='Inception', studio='W...` | Y | 0.99s |
| film-totoro | 1 | Y | Y | Y | `lookup_film_year(title='My Neighbor Totoro', ...` | Y | 0.85s |
| weather-prague | 1 | Y | Y | Y | `get_weather(location='Prague')` | Y | 1.63s |
| weather-tokyo | 1 | Y | Y | Y | `get_weather(location='Tokyo')` | Y | 1.55s |

## Re-run

```sh
pixi run toolcalling-01-test -- --model local-vllm --temperature 0.1
pixi run toolcalling-01-report
```

Artifacts for this report:

- `datasets/toolcalling-01/runs/run-20260823-130047-local-vllm/results.json` — raw rows
- `datasets/toolcalling-01/runs/run-20260823-130047-local-vllm/eval.json` — scored scenarios
- `datasets/toolcalling-01/runs/run-20260823-130047-local-vllm/report.md` — this report
- latest copies: `datasets/toolcalling-01/results.json`, `eval.json`

---

*Rendered by `smoketests/toolcalling-01/report.py` at 2026-08-23T13:00:56+0200.*
