# Responses API (rAPI memproxy): sessions, caching, routing

This note is the field record for the optional **Responses API proxy** in the
README's architecture map (item 9). It is the lab's playground for the
[OpenResponses](https://www.openresponses.org/) standard — an open spec for
interoperable model response APIs — without pretending to be a full OpenAI API
replacement.

The component is `cheap-rAPI-memproxy`, a Docker-only OpenResponses-compatible
cache/proxy sitting **between the client and LiteLLM**. It accepts a focused
subset of the Responses routes, routes requests to a configured upstream
provider, and keeps response flows in a **weighted in-memory cache**. The store
is intentionally **ephemeral** — no persistence, no restart survival. That's the
whole point of the experiment: watch capacity and cost tradeoffs in a small lab.

## Role in the stack

```
 Client (llama.ui / scripts)
   │  POST /v1/responses   (Responses API)
   ▼
 cheap-rAPI-memproxy :6644   ← the rAPI cache + routing shim
   │  provider@model aliases  (default: litellm)
   ▼
 cheap-litellm :4000   ← gateway, billing, Redis cache
   ▼
 engine (single at a time: cheap-llamasrv / cheap-vllm / cheap-sglang)
```

The default route is `litellm`; the same proxy can also point straight at any
engine alias (`llama`, `vllm`, `sglang`) via `provider@model` or the
`x-model-provider` header. Unknown/undefined aliases are rejected with HTTP 400.

## In-memory weighted cache

`OPEN_RESPONSES_STORE_TYPE=in-memory` gives us a **weighted Caffeine cache** —
not a simple LRU, but one where every cached flow carries a weight and the cache
evicts based on total weight, not just entry count. The knobs we wired in:

| Knob | Env var | Value | Meaning |
|---|---|---|---|
| Cache ceiling | `OPEN_RESPONSES_STORE_MAXIMUM_WEIGHT` | `2147483648` (2 GiB) | total weight the flow cache tolerates before eviction |
| Soft threshold | `OPEN_RESPONSES_STORE_SOFT_THRESHOLD` | `0.80` | cleanup targets 80% utilization, not a hard cap |
| Cleanup interval | `OPEN_RESPONSES_STORE_CLEANUP_INTERVAL_MS` | `60000` | idle-flow sweep runs every minute |
| Idle timeout | `OPEN_RESPONSES_STORE_FLOW_IDLE_TIMEOUT_MS` | `600000` (10 min) | an idle flow is purged after ten minutes |

Confirmed live in `/stats`:

```json
"responseStore": {
  "entries": 0, "hitCount": 0, "missCount": 0, "evictionCount": 0,
  "weightedSizeBytes": 0, "maximumWeightBytes": 2147483648,
  "flows": 0, "idleFlowEvictionCount": 0
}
```

The JVM heap is capped at 3 GiB (`-Xmx3g`) inside a 4 GiB container
(`mem_limit: 4g`) — the container's memory is finite and the cache (not the
container healthcheck) is responsible for proactive eviction. The orchestration
`mem_limit` only detects a hard OOM, it doesn't tune the cache.

## Ephemeral-store caveat

The response store is **in-memory and ephemeral**. Cache eviction, idle cleanup,
a process restart, a container replacement, or an OOM kill can all remove active
response flows — a stored `resp_...` you grabbed a minute ago can legitimately
404 later. Treat it as a disposable lab surface, not durable storage. There is
no Mongo/Postgres backing behind it in this lab variant; the README's
"MongoDB-backed sessions" is the aspirational production shape, the memproxy is
the in-memory approximation we actually run for the caching/routing lesson.

## Routing to LiteLLM + the three engines

Requests identify a provider with `provider@model` (e.g. `litellm@local-vllm`
for the gateway leg, `vllm@LiquidAI/LFM2.5-2.6B` for the direct engine leg)
or the `x-model-provider` header; the alias selects the upstream base URL and the
part after `@` is sent as the model name. Compose registers six aliases:

| Alias | URL |
|---|---|
| `litellm` (default) | `http://cheap-litellm:4000/v1` |
| `llama` | `http://cheap-llamasrv:8080/v1` |
| `vllm` | `http://cheap-vllm:8000/v1` |
| `sglang` | `http://cheap-sglang:30000/v1` |
| `openrouter` | placeholder |
| `neocloud` | placeholder |

Note the single-engine GPU rule still applies: only one of
`llamasrv`/`vllm`/`sglang` is up at a time, so `llama@`, `vllm@`, and `sglang@`
are not all reachable simultaneously — the aliases exist so a rerouted request
doesn't need a compose edit, it just needs the matching engine running.

## `OPEN_RESPONSES_UPSTREAM_CACHE` behavior

`OPEN_RESPONSES_UPSTREAM_CACHE=on` (default) is a single global knob that decides
whether the memproxy **asks the upstream to cache**:

- `on`: the proxy injects litellm's cache directive (`cache: {"no-cache": false}`)
  into the downstream chat-completions body, so LiteLLM uses its own cache.
- `off`: nothing cache-related is sent downstream; LiteLLM and the engines follow
  their own config.

This is **distinct** from the in-memory response store. Engine-side caching
(vLLM prefix caching, sglang RadixAttention, llama.cpp slot reuse) is a
server-side flag and **ignores** the injected field either way — it's inert for
them. The active mode shows up in `/stats` as `cache.mode` and on the client span
as `gen_ai.cache.mode`. A client that sends its own `caching` body field is never
rejected (no HTTP 400) and the field is never forwarded; it is recorded only as a
`clientHint` on `/stats`.

## Management endpoints

All live reads, no writes:

```bash
curl -sS http://localhost:6644/health      # {"status":"UP"} — used by the healthcheck
curl -sS http://localhost:6644/stats       # service, requests, responseStore, cache, memory
curl -sS http://localhost:6644/metrics     # Micrometer JSON meter list (jvm.*, logback.*, http.server.requests)
curl -sS http://localhost:6644/prometheus  # Prometheus-format scrape
```

- `/health` is what the container healthcheck curls (`start_period: 30s`).
- `/metrics` registers `gen_ai.client.*` meters lazily — they only appear after a
  request actually reaches an upstream, so a cold container with no reachable
  peer won't show them.
- `/prometheus` ships `jvm_memory_used_bytes` and `logback_events_total`, and
  **is scraped by VictoriaMetrics** every 15s (`rapi-memproxy` job in
  `docker/prometheus.yml`, target `cheap-rAPI-memproxy:6644`).
- **OpenTelemetry traces are exported to Phoenix** (OTLP over HTTP, service name
  `cheap-rAPI-memproxy`): the rAPI HTTP/`gen_ai.*` client spans land in the
  default project alongside LiteLLM's. Two gotchas wired in compose: the OTLP
  endpoint must be the **base** URL (`http://cheap-phoenix:6006`) — the Java SDK
  appends `/v1/traces` itself, and a full `/v1/traces` path causes the
  `...v1/traces/v1/traces` 405 — and `OTEL_LOGS_EXPORTER=none` is set because
  Phoenix rejects the `/v1/logs` signal.

## Live smoke test

With vLLM up (the current single-engine) we can route through the memproxy to
LiteLLM and watch the store fill. Note the **alias gotcha**: LiteLLM only routes
by its `model_list` aliases, so this leg must use `litellm@local-vllm` (which
backs onto vLLM), not a raw model id like `litellm@LiquidAI/LFM2.5-2.6B` — that
form 404s. The direct-engine leg uses the raw id `vllm@LiquidAI/LFM2.5-2.6B`:

```bash
RESP=$(curl -sS http://localhost:6644/v1/responses \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-1234-master-key-4321' \
  -d '{"model":"litellm@local-vllm","input":"What is a weighted cache?","store":true}')
printf '%s' "$RESP" | jq '{id, status, text: .output[0].content[0].text}'
```

Streaming works the same against the SSE body, and a stored response is retrieved
with `GET /v1/responses/{id}`. After traffic, `/stats` shows `requests.total` and
`responseStore.entries` climbing past zero and `/prometheus` exposes
`gen_ai.client.token.usage` — the proof that tokens moved end-to-end through the
proxy.

The automated version of this is the **`responsesapi-01` smoke test**
(`smoketests/responsesapi-01/`), which covers the gateway + direct legs,
streaming, retrieve/continue/input-items, a bad-alias 400, and `/stats` +
`/metrics` + `/prometheus` assertions, and writes artifacts under
`datasets/responsesapi-01/`:

```bash
# make sure the gateway leg is up (LiteLLM + postgres + redis + phoenix)
pixi run responsesapi-01-test && pixi run responsesapi-01-report
```

## Cross-ref

- Docker integration: `docker/docker-compose.yml` → `cheap-rAPI-memproxy`
- Build context (scratch, uncommitted): `$SCRATCH/open-responses-memproxy`
  (`README.md`, `docker/README.md`, `docs/README.md`)
- Sibling engine notes: [vLLM caching](nn-vLLM-caching.md),
  [llama.cpp caching](nn-llamacpp-caching.md), [SGLang caching](nn-SGLang-caching.md),
  [JSON / structured output](nn-json-response.md)
