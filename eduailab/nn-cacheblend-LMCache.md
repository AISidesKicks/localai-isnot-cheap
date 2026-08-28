# LMCache + CacheBlend — External KV Cache Daemon

## 1. What It Is

[LMCache](https://github.com/LMCache/LMCache) is an engine-external KV cache
layer that runs as a standalone daemon (Multi-Process / MP mode). It decouples
KV cache storage from GPU memory and serves multiple inference engines over the
network.

[CacheBlend](https://docs.lmcache.ai/kv_cache_optimizations/cacheblend.html)
(Best Paper, ACM EuroSys 2025) is the optimisation engine inside LMCache that
breaks prefix-caching limits — it fuses precomputed KV blocks from arbitrary
(non-prefix) positions in the prompt, enabling cache hits even when retrieved
chunks are reordered.

### Our lab: 32 GiB host RAM → L1 for KV pool

We run a single LMCache server container alongside one inference engine at a
time. The KV pool lives in host memory; for larger workloads it can spill to
SSD (L2) or Redis (L3).

### Three storage tiers

| Tier | Backend | Latency | Capacity (lab) |
|---|---|---|---|
| L1 | CPU DRAM | ~100 ns | 4 GiB configurable |
| L2 | NVMe SSD (filesystem) | ~10 µs | 4 GiB configurable |
| L3 | Redis (cheap-redis:6379) | ~1 ms | Unlimited (skipped — single node) |

---

## 2. How to Run the LMCache Server (Docker)

### 2a. L1 only — 4 GiB RAM (teaching scenario)

```bash
docker run --rm -it --network cheap-net \
  --name cheap-lmcache \
  python:3.12-slim \
  sh -c "pip install -q lmcache && lmcache server \
    --port 5555 \
    --http-port 8080 \
    --l1-size-gb 4 \
    --eviction-policy LRU \
    --engine-type blend"
```

> **Port 5555**: Confirmed unused in the lab (`grep` on all docker-compose ports
> found no conflict). LMCache's default ZMQ port has varied across releases; pin
> it explicitly with `--port 5555`.

### 2b. L1 + L2 — 4 GiB RAM + 4 GiB SSD (filesystem backend)

```bash
mkdir -p /data/l2

docker run --rm -it --network cheap-net \
  --name cheap-lmcache \
  -v /data/l2:/data/l2 \
  python:3.12-slim \
  sh -c "pip install -q lmcache && lmcache server \
    --port 5555 \
    --http-port 8080 \
    --l1-size-gb 4 \
    --eviction-policy LRU \
    --engine-type blend \
    --l2-adapter '{\"type\": \"fs\", \"base_path\": \"/data/l2\"}'"
```

### 2c. L1 + L2 + L3 (Redis) — noted but skipped for lab

The L3 adapter uses Redis as a remote cache:

```bash
--l2-adapter '{"type": "resp", "host": "cheap-redis", "port": 6379}'
```

This adds value in multi-node deployments. In our single-node lab, L1 + L2
covers all practical scenarios. Skipping L3 avoids gratuitous Redis load.

### Docker Compose Snippet

Add to your `docker-compose.yml` under `services:`:

```yaml
cheap-lmcache:
  image: python:3.12-slim
  container_name: cheap-lmcache
  command: >
    sh -c "pip install -q lmcache &&
           lmcache server
           --port 5555
           --http-port 8080
           --l1-size-gb 4
           --eviction-policy LRU
           --engine-type blend
           --l2-adapter '{\"type\": \"fs\", \"base_path\": \"/data/l2\"}'"
  ports:
    - "5555:5555"
    - "8080:8080"
  volumes:
    - /data/l2:/data/l2
  networks:
    - cheap-net
  restart: unless-stopped
```

> **pip install note**: `python:3.12-slim` may lack build dependencies for
> compiled extensions in `lmcache` (e.g. Cython/CUDA stubs). If `pip install`
> fails, switch to `python:3.12` (full image, +~400 MB) or install
> `build-essential` first. CUDA is not required — LMCache server (MP mode)
> runs on CPU only.

> **Override file note**: `docker-compose.lmcache.yml` (referenced in §3 for vLLM env vars) does not exist in this repo yet. The lab currently manages all 16 services in a single `docker-compose.yml` — no separate override pattern has been established. Creating the override file is a future step when integrating LMCache into the running stack.

> **Image choice**: We use `python:3.12-slim` with `pip install lmcache`
> instead of the official `lmcache/vllm-openai` images because our vLLM and
> SGLang are managed separately. A dedicated Python container keeps the
> LMCache server lightweight (~300 MB).

---

## 3. How to Integrate in the Lab

### vLLM

Override file: `docker/docker-compose.lmcache.yml` (does not modify the
original compose file). Merge with:

```yaml
services:
  cheap-vllm:
    environment:
      KV_TRANSFER_CONFIG: >
        {"kv_connector":"LMCacheMPConnector",
         "kv_role":"kv_both",
         "kv_connector_extra_config":
           {"lmcache.mp.host":"cheap-lmcache",
            "lmcache.mp.port":5555}}
```

| Old flag | Replacement |
|---|---|
| `--kv-transfer-config '{"kv_connector":"OffloadingConnector",...}'` | `"kv_connector":"LMCacheMPConnector"` with host/port pointing to `cheap-lmcache` |

> **Note**: vLLM's `LMCacheMPConnector` is built in since v0.6.x. No separate
> pip install required inside the vLLM container.

### SGLang

Replace existing hierarchical-cache flags:

```bash
# old
--enable-hierarchical-cache --hicache-size 3

# new
--enable-lmcache
```

SGLang's `--enable-lmcache` flag hooks into the local `lmcache` config. For
MP mode (external server), follow the
[examples/sgl_integration/README.md](https://github.com/LMCache/LMCache/tree/main/examples/sgl_integration)
approach.

> **TBD**: The MP-mode integration with SGLang needs testing in our lab.
> The in-process `--enable-lmcache` flag uses LMCache as a library inside the
> SGLang process (not MP). To connect to our external server, SGLang requires
> the connector approach documented in the LMCache examples. Until tested,
> consider this experimental.

### OTEL Tracing

LMCache supports OpenTelemetry export of cache events. Our lab uses
`http/protobuf` — LMCache docs show gRPC (`:4317`) but it also accepts HTTP:

```bash
--enable-tracing \
--otlp-endpoint http://cheap-phoenix:6006/v1/traces
```

This matches our existing lab stack (LiteLLM uses the same endpoint). The
`OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` default in LMCache's exporter
sends to `/v1/traces` on port 6006.

| Lab convention | LMCache flag |
|---|---|
| `http://cheap-phoenix:6006/v1/traces` with `http/protobuf` | `--enable-tracing --otlp-endpoint http://cheap-phoenix:6006/v1/traces` |
| gRPC fallback (untested) | `--enable-tracing --otlp-endpoint http://cheap-phoenix:4317` |

> **Phoenix dual-port**: Port 6006 serves both the UI and OTLP HTTP (`/v1/traces`);
> port 4317 is gRPC only. The lab never uses gRPC. Python SDKs (like LMCache's)
> send the full `/v1/traces` path — unlike the Java SDK in `cheap-rAPI-memproxy`
> which appends it automatically.

### VictoriaMetrics / Prometheus

LMCache exposes Prometheus metrics at `http://0.0.0.0:8080/metrics`. Add a
scrape job to VictoriaMetrics:

```yaml
# vm-scrape.yml snippet
scrape_configs:
  - job_name: lmcache
    static_configs:
      - targets: ['cheap-lmcache:8080']
    metric_relabel_configs:
      - source_labels: [__address__]
        target_label: component_type
        replacement: lmcache
```

---

## 4. How to Test It

### Evaluating hints

Evaluating the performance difference between a standard prefix engine (like vLLM’s RadixCache) and the CacheBlend engine reveals two starkly different behaviors based on how prompts are structured.
In standard conversation loops where text is strictly appended to the end, the prefix engine performs exceptionally well. However, as soon as the prompt order varies—such as in Retrieval-Augmented Generation (RAG) or Multi-Agent systems—the prefix cache completely breaks down, and CacheBlend vastly outperforms it. [1, 2, 3, 4] 
------------------------------
## Core Performance Metrics Comparison
According to official LMCache and EuroSys evaluation benchmarks on multi-document RAG and agent datasets (like OpenClaw and MTRAG), the performance impacts split across three key areas: [3, 5, 6] 

| Metric | Standard Prefix Engine | CacheBlend Engine (blend) | Real-World Impact |
|---|---|---|---|
| Cache Hit Rate | Drops to 0% – 48% (When documents rearrange or dynamic text shifts to the middle) | Maintains 85% – 98% (Can reuse standalone pre-cached text blocks at any position) | CacheBlend completely eliminates redundant prompt recalculations. |
| Time-to-First-Token (TTFT) | High Latency (Triggers full GPU prefill recomputation) | 2.2× to 4.5× Faster (42%–70% overall reduction in initial wait time) | Users see the first generated characters significantly faster. |
| System Throughput | Baseline (GPU stays bottlenecked by prompt processing) | 2.8× to 5.0× Higher (Serves significantly more concurrent requests) | Drastically lowers hardware operational costs per token. |


### Metrics thresholds

When evaluating CacheBlend vs prefix-only, expect these minimum deltas:

| Metric | Threshold | Condition |
|---|---|---|
| Cache hit rate (prefix engine) | < 50 % | Reordered prompts (RAG shuffle) |
| Cache hit rate (CacheBlend) | > 80 % | Same reordered prompts |
| TTFT reduction | ≥ 2× | Prompt with ≥ 2 shuffled docs |
| `lmcache_mp_lookup_hit_tokens_total` | > 0 | After second (reordered) request |
| `lmcache_mp_lookup_requested_tokens_total` | == `hit_tokens` + `miss_tokens` | Sanity — sum check |

If numbers fall short of these thresholds, run the validation checklist below.

### Validation checklist

Run through these checks in order when diagnosing a low hit-rate or missing TTFT drop:

1. **LMCache server is reachable** — `curl -s http://cheap-lmcache:8080/health` returns `200`
2. **Engine type is `blend`** — `docker logs cheap-lmcache 2>&1 \| grep engine` shows `blend`
3. **Connector points to cheap-lmcache:5555** — in vLLM env check `KV_TRANSFER_CONFIG` has `"lmcache.mp.host":"cheap-lmcache"` and `"lmcache.mp.port":5555`
4. **Prometheus counter is non-zero** — query `lmcache_mp_lookup_hit_tokens_total` — if zero, LMCache is running but no client connected
5. **Logs show retrieve activity** — `docker logs cheap-lmcache 2>&1 \| grep -E "retrieve hit\|store blocks"` — if empty, connector or port mismatch
6. **Cache was actually warmed** — the first request (Document A+B) must finish before the second, and both must use the same model

### Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| TTFT does not drop after reorder | Engine not in `blend` mode | Add `--engine-type blend` to lmcache server args |
| `lmcache_mp_lookup_hit_tokens_total` is always 0 | Connector host/port wrong or engine not using LMCacheMPConnector | Verify `KV_TRANSFER_CONFIG` points to `cheap-lmcache:5555` |
| LMCache crashes on startup | Missing build deps for compiled extensions | Use `python:3.12` (full) image or install `build-essential` |
| `/v1/traces` returns 404 from Phoenix | Port mismatch — gRPC vs HTTP | Use `http://cheap-phoenix:6006/v1/traces` (not `:4317`) |
| Hit rate high but TTFT still high | L1 size too small for working set | Increase `--l1-size-gb` or enable L2 spillover |
| vLLM logs `LMCacheMPConnector not found` | vLLM version < 0.6.x | Upgrade vLLM or use `--kv-transfer-config OffloadingConnector` as fallback |

### Document re-ordering test

1.  **Warm the cache** — send a prompt with Document A + Document B:
    ```bash
    curl http://cheap-litellm:4000/v1/chat/completions \
      -d '{"model":"lfm-2.5-2.6b","messages":[
        {"role":"user","content":"Context: [A] ... [B] ... Question: ..."}
      ]}'
    ```

2.  **Shuffle and measure** — send the reordered prompt:
    ```bash
    curl http://cheap-litellm:4000/v1/chat/completions \
      -d '{"model":"lfm-2.5-2.6b","messages":[
        {"role":"user","content":"Context: [B] ... [A] ... Question: ..."}
      ]}'
    ```

3.  **Check TTFT** — compare Time-to-First-Token between the two runs.
    Without CacheBlend, the second request recomputes the full prefix (TTFT
    spike). With CacheBlend, it finds matching KV blocks and blends them
    (TTFT stays low).

### Cache hit metrics

Monitor LMCache's Prometheus counters:

```promql
# Cache hit ratio (last 5 min)
rate(lmcache_mp_lookup_hit_tokens_total[5m])
/
rate(lmcache_mp_lookup_requested_tokens_total[5m])
```

### Logs

Watch LMCache server logs for store/retrieve lines:

```
LMCache store blocks=42 chunks=2
LMCache retrieve hit blocks=40 chunks=2
```

---

## 5. What Must Be Disabled

| Current lab flag | LMCache replacement | Action |
|---|---|---|
| `--kv-transfer-config '{"kv_connector":"OffloadingConnector",...}'` (vLLM) | `"kv_connector":"LMCacheMPConnector"` host/port | Replace |
| `--enable-hierarchical-cache --hicache-size 3` (SGLang) | `--enable-lmcache` | Replace |
| Redis L3 cache block (if any) | LMCache L3 via `--l2-adapter resp` | Leave disabled; not needed |
| `lmcache.yaml` config file with `enable_blending`, `blend_special_str`, `use_layerwise`, `blend_check_layers`, `blend_recompute_ratios` | CLI flags only (MP mode ignores YAML) | Delete |

> **MP mode vs YAML**: The old `lmcache.yaml` config file approach applies to
> the in-process library mode. Multi-Process (MP) mode uses CLI flags passed
> to `lmcache server`. Remove any `lmcache.yaml` mounts from your vLLM/SGLang
> containers.

---

## 6. Storage Tier Scenarios (32 GiB Host RAM)

Our lab has 32 GiB host RAM available. GPU VRAM is 12 GiB (occupied by model
weights + active KV). Here is how much L1 we can spare:

| Scenario | L1 | L2 | Sessions | Use case |
|---|---|---|---|---|
| L1-only (4 GiB) | 4 GiB | — | ~4-8 | Teaching, minimal overhead |
| L1 + L2 (4+4 GiB) | 4 GiB | 4 GiB NVMe | ~8-16 | Larger evals, SSD spillover |
| L1 + L2 + Redis | 4 GiB | 4 GiB NVMe | — | Skipped (multi-node only) |

**L1-only (4 GiB)**: Default teaching configuration. 4 GiB of CPU DRAM holds
~4-8 sessions of KV cache (depending on context length). Zero disk dependency,
minimal moving parts.

**L1 + L2 (4 + 4 GiB)**: Adds a 4 GiB NVMe filesystem backend as L2 spillover.
When L1 fills, least-recently-used KV blocks migrate to SSD. Useful for larger
evaluation sets where the working set exceeds 4 GiB.

**L1 + L2 + Redis**: Skipped. The Redis L3 tier provides value in multi-node
deployments where a central Redis cluster serves multiple LMCache servers. In a
single-node lab, L2 SSD provides sufficient cold storage.

---

## Ports Reference

| Service | Container | Port | Protocol | Purpose |
|---|---|---|---|---|
| LMCache ZMQ | `cheap-lmcache` | 5555 | TCP | vLLM/SGLang connector |
| LMCache HTTP | `cheap-lmcache` | 8080 | HTTP | Healthcheck, Prometheus `/metrics` |
| Phoenix OTLP | `cheap-phoenix` | 6006 | HTTP | OpenTelemetry traces (`/v1/traces`) |
| Phoenix OTLP | `cheap-phoenix` | 4317 | gRPC | OpenTelemetry traces (alternative) |
| VictoriaMetrics | `cheap-victoriametrics` | 8428 | HTTP | Prometheus scrape target |
| Redis | `cheap-redis` | 6379 | TCP | L3 cache (skipped) |