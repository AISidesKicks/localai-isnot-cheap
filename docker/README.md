# Docker stack

Full EDU AI LAB stack: LiteLLM gateway, Redis cache, local inference engines
(llama.cpp / vLLM / SGLang), PostgreSQL, Phoenix observability, VictoriaMetrics,
and a LiteLLM admin MCP server. LiteLLM also aggregates all three admin MCP
servers behind a single MCP gateway at `http://localhost:4000/mcp`.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- NVIDIA GPU + `nvidia-container-toolkit` for the GPU profiles
  (`--profile vllm`, `--profile llamasrv`, `--profile sglang`); the core
  stack (gateway, cache, observability, postgres, redis) runs without a GPU
- `docker compose version` to check Compose v2 (no `version:` key needed)

## Setup

1. Copy the environment template:

   ```sh
   cp docker/.env.example docker/.env
   ```

   The stack runs out of the box with defaults; edit keys only if you want
   the external model fallbacks (gpt-4o / claude / deepseek) to work.

2. Download the GGUF checkpoint into `docker/models/Q8/` (llamasrv profile;
   the container mounts `./models:/models:ro`, so it lands at `/models/Q8/`):

   ```sh
   # LiquidAI/LFM2.5-2.6B-GGUF, Q8_0 (2.87 GB)
   huggingface-cli download LiquidAI/LFM2.5-2.6B-GGUF \
     LFM2.5-2.6B-Q8_0.gguf --local-dir docker/models/Q8/
   ```

   vLLM and SGLang pull `plavno/LFM2.5-2.6B-AutoRound-W8A16` (W8A16
   quantized, ~2.9 GB vs 5.4 GB bf16) from Hugging Face on first start and
   cache it under `docker/models/hf-cache` (gitignored).

### vLLM VRAM usage

Measured on an RTX 4070 (12 GiB): baseline 442 MiB at idle, 11.4 GiB after
load. Weights take 3.09 GiB, activations ~0.96 GiB, CUDA graphs 0.42 GiB,
and the KV cache 6.62 GiB at the default `--gpu-memory-utilization 0.92`
(roughly 91% of the card). W8A16 keeps the model on a 12 GiB card with
headroom for a small batch.

### SGLang VRAM usage

Same checkpoint, same RTX 4070: 9.37 GiB after load (engine process, vs
10.9 GiB for vLLM). Weights take 3.44 GiB; with the full 128K context SGLang
reserves a 134,039-token KV cache (2.04 GiB K+V), a 1.84 GiB Mamba
conv_state cache, and a 1024 MiB CUDA IPC pool, at the auto-tuned
`--mem-fraction-static 0.669`. The auto-round quantization is auto-detected
(`quant=auto-round, bits=8`). Both engines derive the full 131072-token
context from `max_position_embeddings` when no length flag is given —
service at a shorter context (e.g. the model card's recommended 4096) frees
the rest of the card. Cold CUDA graph capture can take ~5 minutes on first
start, which can outrun the `start_period 420s` healthcheck before flipping
healthy.

### llama.cpp VRAM usage

Same RTX 4070, Q8_0 GGUF checkpoint: 5.0 GiB after load (llama-server, vs
11.4 GiB vLLM / 9.37 GiB SGLang on the W8A16 quant). Weights take 2.67 GiB
on the GPU (another 0.26 GiB stays CPU-mapped, off-card), the KV cache
1.95 GiB in f16, and compute scratch ~0.19 GiB, on top of the 442 MiB idle
baseline. llama.cpp auto-derives the context from the model card:
`n_ctx` 128000 split into 4 parallel slots of 32K tokens each, so the KV
buffer is pre-allocated for the whole 128K regardless of how many slots a
batch actually uses.

The KV cache is quantized to `q8_0` (`-ctk q8_0 -ctv q8_0` in the
`cheap-llamasrv` command), which drops the KV buffer from ~1.95 GiB f16 to
~1 GiB q8_0 (half the memory for the same 4×32K seats). This matches the
`eduailab/nn-KV-cache-quantization.md` recipe: LFM2.5 is a small hybrid
(GQA full-attn, 8 of 30 layers carry K/V), so 8-bit is the sweet spot —
4-bit is risky, and q8_0 V needs FlashAttention (auto-enabled via
`--flash-attn auto`). After the q8_0 change the post-load footprint is
~4.1 GiB instead of ~5.0 GiB.

## Run

Core stack (gateway + cache + observability + postgres + redis, no engines):

```sh
docker compose -f docker/docker-compose.yml up -d
```

With a local inference engine (pick one profile):

```sh
docker compose -f docker/docker-compose.yml --profile llamasrv up -d
docker compose -f docker/docker-compose.yml --profile vllm up -d
docker compose -f docker/docker-compose.yml --profile sglang up -d
```

Or set `INFERENCE_PROFILE` in `docker/.env` and use the environment-driven
`COMPOSE_PROFILES` mechanism:

```sh
# INFERENCE_PROFILE=llamasrv | vllm | sglang
COMPOSE_PROFILES="$INFERENCE_PROFILE" docker compose -f docker/docker-compose.yml up -d
```

The core stack starts without engines (plain `docker compose up -d`), but when
a profile is active LiteLLM waits for the selected engine's `/health` before
starting — activate two profiles at once and it waits for both.

Switching engines mid-session: `docker compose` only applies `command`
changes on `up -d` (recreate), not on `restart` or `stop`+`start`. To move from
the llama.cpp profile to the vLLM profile:

```sh
docker compose -f docker/docker-compose.yml stop cheap-llamasrv   # frees the GPU
docker compose -f docker/docker-compose.yml --profile vllm up -d cheap-vllm
```

`cheap-vllm` runs with `--enable-prefix-caching` (set in
`docker/docker-compose.yml`), so shared prompt prefixes reuse KV blocks — watch
`vllm:prefix_cache_hits_total` / `vllm:prefix_cache_queries_total` in
VictoriaMetrics. Note the vLLM profile binds host port 8000, which conflicts
with the optional `vm-mcp` container — stop `vm-mcp` first if it is running.

Stop / tear down:

```sh
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml down -v   # wipes volumes too
```

## Embeddings

Alongside the GPU chat engines, the stack can serve **text embeddings** — the
point of this lab is to meter and bill *every* token, and embeddings are just
another token stream. Routing embeddings through the gateway (4000) meters
every request, so each one shows up in LiteLLM spend logs and Phoenix just like
a chat completion.

It serves **nomic-embed-text-v1.5** (768-dim; chunks up to 8192 tokens) on
**llama.cpp** — both a CPU and a GPU config, started **manually** one at a time,
sharing host port **8081**. We use llama.cpp for embeddings because the other
two engines don't cleanly support the nomic model: vLLM's CPU image fights the
host RAM (`--gpu-memory-utilization`) and SGLang's only CPU image needs Intel
AMX (SIGILL on non-Xeon CPUs, e.g. AMD), while its GPU image lacks a native
NomicBert implementation and falls back to a slow transformers loader that
chokes on `get_input_embeddings`. llama.cpp just works for BERT-style embedders.

Download the two GGUF checkpoints into `docker/models/embeddings/` (F16 for
CPU, Q8_0 for GPU — see the root README for the F16-on-CPU rationale; the GPU
config runs the much smaller Q8_0 offloaded to the card):

```sh
huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF \
  nomic-embed-text-v1.5.f16.gguf  --local-dir docker/models/embeddings/
huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF \
  nomic-embed-text-v1.5.Q8_0.gguf --local-dir docker/models/embeddings/
```

They land at `/models/embeddings/` (the `./models:/models:ro` mount mirrors
them), and `docker/models/**/*.gguf` is gitignored.

Both configs are the **same container name `cheap-llamaembed` on port 8081**,
so LiteLLM's alias `nomic-embed-llama` always points at
`http://cheap-llamaembed:8081/v1` — start the CPU or GPU one, never both:

```sh
# CPU: nomic-embed-text-v1.5.f16.gguf, pure CPU (-t 3)
docker compose -f docker/docker-compose.yml --profile embed-cpu up -d

# GPU: nomic-embed-text-v1.5.Q8_0.gguf, all layers on the GPU (-ngl 99)
docker compose -f docker/docker-compose.yml --profile embed-gpu up -d
```

or via the `COMPOSE_PROFILES` mechanism:

```sh
COMPOSE_PROFILES="embed-cpu" docker compose -f docker/docker-compose.yml up -d   # or embed-gpu
```

Both use llama.cpp's `server` with `--embedding --pooling mean` and
`--ctx-size 8192`; the GPU config adds `-ngl 99` and the `nvidia` runtime. They
share the port, so stop one before starting the other (stop the single service
by its container name, not the whole stack with a profile — `stop` on a profile
takes down the core stack too):

```sh
docker compose -f docker/docker-compose.yml stop cheap-llamaembed
```

Since the two embed services carry the same `container_name`, never pass both
profiles at once.

Smoke-test the engine directly on 8081, or verify the whole path plus LiteLLM
metering with the bundled script (asserts dim 768):

```sh
./docker/verify-embed.sh
```

## Test

Smoke-test the vLLM endpoint directly (bypasses LiteLLM). First wait for
`cheap-vllm` to report healthy:

```sh
docker compose -f docker/docker-compose.yml --profile vllm ps
```

Then send a chat completion:

```sh
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"LiquidAI/LFM2.5-2.6B","messages":[{"role":"user","content":"Give me a short summary about Marvel Cinematic Universe."}]}'
```

Smoke-test the SGLang endpoint the same way (one engine at a time; stop
`cheap-vllm` first). Wait for `cheap-sglang` to report healthy, then:

```sh
curl -s http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"LiquidAI/LFM2.5-2.6B","messages":[{"role":"user","content":"Give me a short summary about Marvel Cinematic Universe."}]}'
```

To verify LiteLLM routing instead, hit the gateway on port 4000 with the
`local-llama` alias and the master key from `docker/.env`
(`LITELLM_MASTER_KEY`, default `sk-1234-master-key-4321`).

## WebUI (llama.ui)

The stack ships a browser-hosted chat UI at `http://localhost:3333` (llama.ui).
It stores all state in the browser's IndexedDB, so there is no server volume and
nothing to back up.

Point llama.ui at the **LiteLLM gateway**, not the engine, or you silently lose
spend metering. Configure it once in the browser:

- **Provider**: **Llama.cpp** (or **OpenAI Compatible**) — either lets you edit
  the Base URL and the API key. Skip the cloud providers (OpenAI, etc.); they
  hard-code their own endpoint and you cannot point them at the gateway.
- **Base URL**: `http://localhost:4000` — and **do NOT append `/v1`**. llama.ui
  appends `/v1/...` itself, so entering `.../4000/v1` sends the request to
  `.../4000/v1/v1/chat/completions` → 404. This is the single most common
  misconfiguration.
- **API key**: paste the full `LITELLM_WEBUI_KEY` from `docker/.env`
  (chat-only key for user `webui`). If you leave it blank, llama.ui sends **no
  `Authorization` header** and the gateway answers 401. Quoting it is not
  needed.
- **Model**: exactly `local-gguf` (llama.cpp / `--profile llamasrv`).

The key and Base URL fields are always visible in **General settings** for the
Llama.cpp / OpenAI Compatible providers — the `Authorization: Bearer` header is
only sent when the key field is non-empty.

If llama.ui reports **"Failed to respond from api"**, open the browser's
DevTools → Network tab and check the failing request:
`http://localhost:4000/v1/chat/completions` should be the exact URL. Diagnose
by status:

| Status | Cause | Fix |
|--------|-------|-----|
| 404 | Double `/v1` — Base URL entered as `http://localhost:4000/v1` | Set Base URL to `http://localhost:4000` (no trailing `/v1`) |
| 401 | Missing / wrong API key (blank key sends no `Authorization` header) | Paste the full `LITELLM_WEBUI_KEY` into the API key field |
| 403 | Wrong model name (not exactly `local-gguf`) | Set model to `local-gguf` |
| 404 / connection refused | Llama.cpp provider defaulted to `localhost:8080` (engine, no metering) | Point Base URL at the gateway `http://localhost:4000` (see below) |

Routing chat through the gateway (4000) meters every request — you get a row in
LiteLLM spend logs and a trace in Phoenix. Hitting the engine directly at
`localhost:8080` bypasses the gateway entirely and shows up nowhere in billing.

The llama.cpp engine itself runs with `--no-webui`: it exposes only the OpenAI
compatible API (`/health`, `/v1/models`, `/v1/chat/completions`) on 8080, with no
built-in UI. This is fine — the WebUI lives in llama.ui on 3333 instead.

`LITELLM_WEBUI_KEY` is still defined in `.env`/compose even though Open WebUI was
removed; llama.ui uses it for manual config, so keep it.

## Monitoring

The datastores are watched too — not just the inference engines. Stock Redis and
PostgreSQL images don't expose a Prometheus `/metrics` endpoint, so the stack
runs **sidecar exporters**: small containers co-located with the datastore that
translate its stats into Prometheus-format metrics.

| Sidecar | Image | Scrapes | Exposes |
|---------|-------|---------|---------|
| `cheap-redis-exporter` | `oliver006/redis_exporter` | `redis://cheap-redis:6379` | `:9121/metrics` |
| `cheap-postgres-exporter` | `prometheuscommunity/postgres-exporter` | `cheap-postgres:5432` (LiteLLM db) | `:9187/metrics` |

Both are capped at **0.50 CPU / 256M memory** via `deploy.resources.limits` —
same thin limits as the rest of the metric path (VictoriaMetrics itself runs on
the same cap). They start only after their datastore reports healthy
(`depends_on: service_healthy`), so they never scrape a half-booted DB. The
Redis exporter intentionally has **no healthcheck** (its `:latest` image is
scratch-based — no shell or wget); the Postgres exporter's busybox-based image
has one that wgets `/metrics`.

VictoriaMetrics scrapes both through `prometheus.yml` (labels
`db_type: redis` / `db_type: postgres`). Query them like the engine metrics —
through the VM query API on 8428:

```sh
# is the exporter connected to Redis? (1 = up)
curl -s 'http://localhost:8428/api/v1/query?query=redis_up'
# is the postgres scrape working? (1 = up)
curl -s 'http://localhost:8428/api/v1/query?query=pg_up'
```

or browse them in the VM UI at http://localhost:8428/vmui. Useful datastore
metrics behind those scrapes: `redis_connected_clients`,
`redis_memory_used_bytes`, `redis_keyspace_hits_total`, `pg_stat_database_numbackends`,
`pg_stat_database_tup_returned`, and `pg_size_bytes`-style per-database gauges.

## Port map

| Port | Service        | Notes                          |
|------|----------------|--------------------------------|
| 4000 | LiteLLM        | OpenAI-compatible gateway + MCP gateway (`/mcp`) |
| 3333 | llama.ui       | browser-hosted WebUI (data in IndexedDB, no volume) |
| 5432 | PostgreSQL     | LiteLLM + Phoenix databases    |
| 9187 | Postgres exporter | Prometheus `/metrics` for PostgreSQL |
| 6379 | Redis          | LiteLLM cache                  |
| 9121 | Redis exporter | Prometheus `/metrics` for Redis |
| 8080 | llama.cpp      | API-only (`--no-webui`), only with `--profile llamasrv` |
| 8000 | vLLM           | only with `--profile vllm`     |
| 30000| SGLang         | only with `--profile sglang`   |
| 8081 | llama.cpp embed| nomic-embed, port shared by CPU (F16) & GPU (Q8) configs, manual `--profile embed-cpu` / `embed-gpu` |
| 6006 | Phoenix        | UI + OTLP HTTP + MCP           |
| 4317 | Phoenix        | OTLP gRPC                      |
| 8428 | VictoriaMetrics| metrics UI / query API         |
| 8000 | VM MCP         | MCP server for VictoriaMetrics (conflicts with vllm profile) |
| 4001 | LiteLLM MCP    | MCP admin tools for LiteLLM (external server) |

All admin MCP servers (Phoenix, VictoriaMetrics, LiteLLM) also aggregate behind
the LiteLLM MCP gateway at `http://localhost:4000/mcp` — one endpoint, tools
namespaced per server (`phoenix-*`, `victoriametrics-*`, `litellm_admin-*`).
Authenticate with the master key header
(`x-litellm-api-key: Bearer <LITELLM_MASTER_KEY>`). The `litellm-gateway` entry
in `opencode.json.example` hard-codes the default demo key — substitute your
real `LITELLM_MASTER_KEY` from `docker/.env` in a local copy.

## MCP Toolsets

A toolset is a curated, named subset of tools pulled from across the three
upstream admin MCP servers (Phoenix, VictoriaMetrics, LiteLLM). Granting toolsets
instead of whole servers means agents see fewer tokens (only the tools you want)
and lets you scope per-team access to a specific slice of the aggregate gateway.

Create the sample `monitoring` toolset (10 tools, idempotent — skips if it
already exists):

```sh
./docker/mcp_toolset.sh
```

The script authenticates with `LITELLM_ADMIN_KEY` from `docker/.env` — a
dedicated `proxy_admin` user (`litellmadm`) provisioned on first boot so toolset
creation works without exposing the raw master key. The raw master key only
resolves as proxy_admin after `litellm_config.yaml` sets it as
`general_settings: master_key: os.environ/LITELLM_MASTER_KEY` (the
`os.environ/...` prefix that LiteLLM actually resolves).

Verify the toolset:

```sh
curl -s http://localhost:4000/v1/mcp/toolset \
  -H "Authorization: Bearer $LITELLM_ADMIN_KEY"
```

An agent uses the toolset through the Responses/Chat API as an MCP reference — a
LiteLLM-internal route (no public URL), so `require_approval` is `never`:

```json
{"type": "mcp", "server_label": "monitoring",
 "server_url": "litellm_proxy/mcp/monitoring", "require_approval": "never"}
```

Toolsets are stored in LiteLLM's database (not `litellm_config.yaml`), so they
persist across restarts but are instance-per-DB — re-run the script if you wipe
the Postgres volume.

| Server | Toolset role | Tools in `monitoring` |
|--------|--------------|----------------------|
| Phoenix | observability | `search`, `list_tools` |
| VictoriaMetrics | metrics / alerts | `query`, `query_range`, `metrics`, `alerts` |
| LiteLLM admin | gateway admin | `list_spend_logs`, `list_keys`, `check_health`, `get_global_spend_report` |

## Model aliases in LiteLLM

| Alias        | Backend        | Engine profile |
|--------------|----------------|----------------|
| `local-gguf` | llama.cpp      | `llamasrv`   |
| `local-llama`| vLLM           | `vllm`         |
| `local-vllm` | vLLM           | `vllm`         |
| `local-sglang`| SGLang        | `sglang`       |
| `nomic-embed-llama` | llama.cpp (nomic-embed, 768-dim) | `embed-cpu` (F16) or `embed-gpu` (Q8) |
| `gpt-4o`     | OpenAI         | external       |
| `claude-sonnet-4-20250514` | Anthropic | external |
| `deepseek-chat` | DeepSeek    | external       |

All three engines serve the same logical model id `LiquidAI/LFM2.5-2.6B`;
vLLM and SGLang run the AutoRound W8A16 quantization, llama.cpp the Q8_0 GGUF.
The embed alias instead serves `nomic-embed-text-v1.5` (768-dim) on llama.cpp
(CPU/F16 or GPU/Q8).

## Project links

| Product | Used for | Upstream |
|---------|----------|----------|
| LiteLLM | OpenAI-compatible gateway + MCP gateway | https://github.com/BerriAI/litellm |
| LiteLLM MCP | MCP admin tools for LiteLLM | https://github.com/TETRA-2023/litellm-mcp |
| Phoenix (Arize) | LLM observability, traces, evals | https://github.com/Arize-ai/phoenix |
| VictoriaMetrics | metrics storage and querying | https://github.com/VictoriaMetrics/VictoriaMetrics |
| VictoriaMetrics MCP | MCP server for VictoriaMetrics | https://github.com/VictoriaMetrics/mcp-victoriametrics |
| llama.cpp | local inference engine (GGUF) | https://github.com/ggml-org/llama.cpp |
| llama.ui | browser-hosted WebUI (chat) | https://github.com/olegshulyakov/llama.ui |
| vLLM | local inference engine (W8A16) | https://github.com/vllm-project/vllm |
| SGLang | local inference engine (W8A16) | https://github.com/sgl-project/sglang |
| PostgreSQL | LiteLLM + Phoenix databases | https://www.postgresql.org |
| Postgres exporter | Prometheus `/metrics` for PostgreSQL | https://github.com/prometheus-community/postgres_exporter |
| Redis | LiteLLM cache | https://redis.io |
| Redis exporter | Prometheus `/metrics` for Redis | https://github.com/oliver006/redis_exporter |
