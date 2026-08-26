# responsesapi-01 smoke run: run-20260826-172244-responsesapi

- **service**: `http://localhost:6644` (cheap-rAPI-memproxy :6644)
- **gateway alias**: `local-vllm` → vLLM :8000
- **direct model**: `LiquidAI/LFM2.5-2.6B`
- **scenarios**: `10`
- **run_at**: `2026-08-26T17:22:46+0200`
- **test**: `smoketests/responsesapi-01/test.py`

## Summary

**10/10 scenarios passed**

| Scenario | Result | Route / check |
|----------|--------|---------------|
| `litellm_route` | **PASS** | POST /v1/responses litellm@local-vllm (gateway leg) |
| `vllm_route` | **PASS** | POST /v1/responses vllm@LiquidAI/LFM2.5-2.6B (direct leg) |
| `header_route` | **PASS** | POST with x-model-provider: vllm |
| `stream_route` | **PASS** | SSE stream:true on vllm route |
| `retrieve` | **PASS** | GET /v1/responses/{id} |
| `continue_flow` | **PASS** | POST previous_response_id continuation |
| `input_items` | **PASS** | GET /v1/responses/{id}/input_items |
| `bad_alias` | **PASS** | POST nope@bogus -> expect HTTP 400 |
| `stats` | **PASS** | GET /stats field assertions |
| `metrics` | **PASS** | GET /metrics + /prometheus meter names |

## Per-scenario detail

| Scenario | http_status | ok | detail |
|----------|-------------|----|--------|
| `litellm_route` | 200 | Y | model=local-vllm |
| `vllm_route` | 200 | Y | model=LiquidAI/LFM2.5-2.6B |
| `header_route` | 200 | Y | model=LiquidAI/LFM2.5-2.6B |
| `stream_route` | 200 | Y | deltas=1 completed=True |
| `retrieve` | 200 | Y | id=chatcmpl-8b67371cf3ad87cd |
| `continue_flow` | 200 | Y | prev=chatcmpl-8b67371cf3ad87cd |
| `input_items` | 200 | Y | object=list |
| `bad_alias` | 400 | Y | expect 400 got 400 |
| `stats` | 200 | Y | {"service": true, "requests.total>0": true, "responseStore.entries>0": true, "cache.mode==on": true, "memory.maxBytes==3221225472": true, "maximumWeightBytes==2147483648": true} |
| `metrics` | 200 | Y | http.server.requests=Y jvm_memory_used_bytes=Y |

## Re-run

```sh
pixi run responsesapi-01-test
pixi run responsesapi-01-report
```

Artifacts for this report:

- `datasets/responsesapi-01/runs/run-20260826-172244-responsesapi/results.json` — raw rows
- `datasets/responsesapi-01/runs/run-20260826-172244-responsesapi/eval.json` — pass/fail summary
- `datasets/responsesapi-01/runs/run-20260826-172244-responsesapi/report.md` — this report
- latest copies: `datasets/responsesapi-01/results.json`, `eval.json`

---

*Rendered by `smoketests/responsesapi-01/report.py` at 2026-08-26T17:22:48+0200.*
