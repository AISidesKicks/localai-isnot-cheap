# responsesapi-01 design notes

Field-decision notes for the `responsesapi-01` smoke test. Written down so the
choice of scenarios, the alias string, and the stdlib-only client stay
deliberate, not accidental.

## Motivation

The lab metering story needs a proof that the optional **rAPI memproxy**
(README architecture item 9) accepts a focused Responses-API subset, routes
`provider@model` to the right upstream, keeps response flows in the ephemeral
in-memory store, and serves `/stats` / `/metrics` / `/prometheus`. This smoke
test flips those properties into a small set of observable rows, one per
scenario, mirroring the `toolcalling-01` / `cinematic-01` run+report pattern.

## stdlib-only client

The test talks to rAPI over the wire with `urllib`/`json` — no `httpx`,
`openai`, or `litellm` imports. `httpx` and `httpx-sse` are already in the pixi
env, but keeping the client dependency-free makes the smoke test runnable with a
bare Python 3.12 interpreter (the pixi `cheap` env has Python 3.12 pinned). Only
a small `get_master_key()` helper is copied from `smoketests/cinematic-01/llm.py`
so the gateway credential is still resolved at runtime (env var -> `docker/.env`
-> demo placeholder) and never hard-coded.

## Alias choice: `litellm@local-vllm`, not `litellm@LiquidAI/LFM2.5-2.6B`

The rAPI doc examples use `litellm@gpt-4o-mini` and the lab note used
`litellm@LiquidAI/LFM2.5-2.6B`. That second form **404s in practice**: LiteLLM
only routes by the aliases in its `model_list` (`local-gguf`, `local-llama`,
`local-vllm`, `local-sglang`, ...), so a raw model id is unknown to the gateway.
The correct LiteLLM-leg model string is `litellm@local-vllm`
(`local-vllm` -> `http://cheap-vllm:8000/v1` in `docker/litellm_config.yaml`).
The direct engine leg bypasses the gateway and hits vLLM straight, so it uses
the bare model id: `vllm@LiquidAI/LFM2.5-2.6B`. The rAPI response echoes the
requested alias on the gateway leg and the raw model id on the direct leg —
a clean way to tell the two legs apart.

## Ephemeral-store caveat

`store:true` is mandatory for the retrieve/continue/input-items scenarios — the
flow is only kept in the in-memory weighted cache when the client asks for it.
The store is intentionally non-durable: eviction, idle cleanup, restart, or OOM
can 404 a stored response, so the test creates a stored response and immediately
retrieves/continues it within the same run (not assuming it survives across
runs). `/stats` reads `requests.total` and `responseStore.entries` from the
shared live service, so the test only asserts that traffic happened
(total > 0, entries > 0) — an assertion reader on `idleFlowEvictionCount`
points at the ephemeral nature rather than pretending the store is durable.

## Bad-alias negative test

An unknown provider alias (`nope@bogus`) returns HTTP 400 — a cheap
negative-path assertion that the alias table is actually consulted, not
defaulted silently.

## Streaming

With `stream:true` the body is an SSE event stream (`event:`/`data:` lines), not
a single JSON document. The test consumes lines until it sees
`response.completed`, collecting `response.output_text.delta` payloads, and
records whether deltas were observed and whether the stream terminated cleanly.

## Single-engine GPU rule

Only one engine (llamasrv / vllm / sglang) is up at a time; vLLM is the active
engine for this lab, so `vllm@` (and the `litellm@local-vllm` gateway alias that
backs onto it) are the only reachable routes. `sglang@` is therefore an
unreachable-route probe: since the memproxy fix set, a connection-level failure
to a down engine is reported as **502 `upstream_error`** (no misleading 500),
which makes the down engine a cheap negative-path assertion (`engine_down_502`),
distinct from the unknown-provider case (`bad_alias` -> 400).

## Regression assertions (memproxy fix set)

The run also locks in the wire/config behavior delivered by the upstream fix set
(`6824e5f..3520743` of `open-responses-memproxy`):

- `payload_wire` / `stream_wire` — the SDK-internal `isValid` and
  `sequence_number` fields are stripped from both the response JSON and every SSE
  data event, and stream termination still arrives via `response.completed`.
- `created_at` is epoch **millis** (13-digit) on the non-streaming response.
- `engine_down_502` — `sglang@LiquidAI/LFM2.5-2.6B` (engine down) returns
  502 `upstream_error`.
- `stats` — `requests.failedBy` breaks failures down by
  client/upstream/internal/timeout/exception, and the run asserts the two causes
  it provokes (down-engine 502 -> upstream, bogus alias 400 -> client).
- `metrics` — `/prometheus` exposes the store/cache gauges
  `openresponses_store_entries` / `openresponses_store_evictions` /
  `openresponses_cache_mode`.

Ignored-client-hint behavior (`caching` WARN) is exercised in the lab but not as
a test scenario — it needs container-log inspection, which would make the
stdlib-only client depend on `docker`.
<br>(also see `memproxy-fix.md` + `docs/stats.md` in the upstream repo).

## Layout

```
smoketests/responsesapi-01/design.md      this file
smoketests/responsesapi-01/test.py        run scenarios -> artifacts
smoketests/responsesapi-01/report.py      render report.md from artifacts
datasets/responsesapi-01/runs/<run-id>/results.json   raw rows
datasets/responsesapi-01/runs/<run-id>/eval.json      pass/fail summary
datasets/responsesapi-01/runs/<run-id>/report.md      this report
datasets/responsesapi-01/results.json     "latest" copies, refreshed each run
datasets/responsesapi-01/eval.json
```

`<run-id>` defaults to `run-<YYYYMMDD-HHMMSS>-responsesapi`. The test renders a
pass/fail summary into `eval.json`; `report.py` re-renders a reproducible
`report.md` from those artifacts alone (no live calls), so a given run-id always
re-renders to the same report modulo the `rendered_at` stamp. Mirrors
`smoketests/toolcalling-01/` / `smoketests/cinematic-01/`.
