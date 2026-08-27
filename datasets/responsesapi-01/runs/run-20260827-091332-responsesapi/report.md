# responsesapi-01 smoke run: run-20260827-091332-responsesapi

- **service**: `http://localhost:6644` (cheap-rAPI-memproxy :6644)
- **gateway alias**: `local-vllm` → vLLM :8000
- **direct model**: `LiquidAI/LFM2.5-2.6B`
- **scenarios**: `13`
- **run_at**: `2026-08-27T09:13:42+0200`
- **test**: `smoketests/responsesapi-01/test.py`

## Summary

**13/13 scenarios passed**

| Scenario | Result | Route / check |
|----------|--------|---------------|
| `litellm_route` | **PASS** | POST /v1/responses litellm@local-vllm (gateway leg) |
| `vllm_route` | **PASS** | POST /v1/responses vllm@LiquidAI/LFM2.5-2.6B (direct leg) |
| `payload_wire` | **PASS** | payload cleanliness: no isValid/sequence_number, millis created_at |
| `header_route` | **PASS** | POST with x-model-provider: vllm |
| `stream_route` | **PASS** | SSE stream:true on vllm route |
| `stream_wire` | **PASS** | SSE cleanliness: no leaked sequence_number/isValid |
| `retrieve` | **PASS** | GET /v1/responses/{id} |
| `continue_flow` | **PASS** | POST previous_response_id continuation |
| `input_items` | **PASS** | GET /v1/responses/{id}/input_items |
| `engine_down_502` | **PASS** | POST sglang@LiquidAI/LFM2.5-2.6B (engine down) -> expect 502 upstream_error |
| `bad_alias` | **PASS** | POST nope@bogus -> expect HTTP 400 |
| `stats` | **PASS** | GET /stats field + requests.failedBy assertions |
| `metrics` | **PASS** | GET /metrics + /prometheus meter + store gauge names |

## Per-scenario detail

| Scenario | http_status | ok | detail |
|----------|-------------|----|--------|
| `litellm_route` | 200 | Y | model=local-vllm |
| `vllm_route` | 200 | Y | model=LiquidAI/LFM2.5-2.6B |
| `payload_wire` | 200 | Y | created_at_millis=True leaked=0 |
| `header_route` | 200 | Y | model=LiquidAI/LFM2.5-2.6B |
| `stream_route` | 200 | Y | deltas=1 completed=True |
| `stream_wire` | 200 | Y | leaked=0 completed=True |
| `retrieve` | 200 | Y | id=chatcmpl-9148a48ee39c81a9 |
| `continue_flow` | 200 | Y | prev=chatcmpl-9148a48ee39c81a9 |
| `input_items` | 200 | Y | object=list |
| `engine_down_502` | 502 | Y | type=upstream_error expect 502 upstream_error |
| `bad_alias` | 400 | Y | expect 400 got 400 |
| `stats` | 200 | Y | {"service": true, "requests.total>0": true, "responseStore.entries>0": true, "cache.mode==on": true, "memory.maxBytes==3221225472": true, "maximumWeightBytes==2147483648": true, "failedBy.causes>=5": true, "failedBy.upstream>=1": true, "failedBy.client>=1": true} |
| `metrics` | 200 | Y | http.server.requests=Y jvm_memory_used_bytes=Y store_gauges=Y |

## Re-run

```sh
pixi run responsesapi-01-test
pixi run responsesapi-01-report
```

Artifacts for this report:

- `datasets/responsesapi-01/runs/run-20260827-091332-responsesapi/results.json` — raw rows
- `datasets/responsesapi-01/runs/run-20260827-091332-responsesapi/eval.json` — pass/fail summary
- `datasets/responsesapi-01/runs/run-20260827-091332-responsesapi/report.md` — this report
- latest copies: `datasets/responsesapi-01/results.json`, `eval.json`

---

*Rendered by `smoketests/responsesapi-01/report.py` at 2026-08-27T09:13:44+0200.*
