# SGLang KV caching (L1 → L2 → L3)

SGLang's cache story is the most explicitly "CPU cache" of the three engines:
RadixAttention on the GPU, HiCache in host RAM, and HiCache's pluggable storage
backends for L3. It also runs the weirdest L1 in the lab — a **unified radix tree**
that caches FULL attention, sliding-window (SWA) and Mamba (SSM/conv) state in *one*
tree, because our LFM2.5-2.6B is a hybrid model.

## 1. Cache model L1/L2/L3

### L1 — GPU: RadixAttention (default on)

- Requests share a **radix tree**: a path from root to leaf is a request's prefix,
  token spans dedup across requests, and idle GPU memory holds the tree —
  **no flag needed, it's on by default**. LRU eviction runs at the **leaf** level so
  hot shared prefixes survive while cold tails die.
- Matching is page-granular (`--page-size`), eviction-free for the hot part, and acts
  as the tree that L2/L3 hang off in HiCache.

### L2 — CPU RAM: HiCache host pool

HiCache is the official L2/L3 extension, and it mirrors the CPU three-level design:
L1/L2 private per instance, L3 shared (optionally) across instances.

- `--enable-hierarchical-cache` — required switch for the whole tier.
- `--hicache-size 3` (GiB, overrides ratio) or `--hicache-ratio 2.0`. House
  standard: **3 GB** — `--hicache-size 3`. The host pool must be **larger than the
  GPU KV pool** (ratio must be > 1), because host RAM is the buffering layer between
  GPU and disk. **Enabled in this repo's compose** on `cheap-sglang`.
- `--hicache-host-memory-mode cache` (default) treats the host pool as a persistent
  tier; `buffer_only` downgrades it to a staging buffer for L3 (`--hicache-write-policy
  write_back|write_through|write_through_selective` governs when data demotes).

### L3 — disk: HiCache storage backends

Enable with `--hicache-storage-backend`:

- `file` — the teaching/demo backend. It writes page files into a directory, so L3 is
  just a mount point. Directory comes from `SGLANG_HICACHE_FILE_BACKEND_STORAGE_DIR`
  (default `/tmp/hicache`). Point it at a tmpfs ramdisk or a persistent SSD mount.
- `mooncake`, `hf3fs`, `nixl`, `aibrix` — the cluster-grade backends (RDMA/distributed
  storage) that make L3 shared across instances. A lab shouldn't need them; they're
  the "where the enterprise goes" footnote.
- Prefetch policy: `--hicache-storage-prefetch-policy {best_effort,wait_complete,timeout}` —
  when a request misses L1/L2, HiCache queries L3 and prefetches ≥256 tokens of
  matching KV back into the host pool, up to the configured timeout.

**Hybrid-model nuance (the LFM part):** LFM2.5's FULL/SWA/MAMBA components all live
in one unified radix tree. Historically that needed `SGLANG_ENABLE_UNIFIED_RADIX_TREE=1`;
on current `main` the unified tree **is the default** (the env var is deprecated —
unset it). `--mamba-full-memory-ratio` (default `0.9`) partitions the tree's pool
between Mamba state memory and full-attention KV, and the Mamba **conv_state cache
(measured 1.84 GiB) is a separate buffer** — quantize the KV with `--kv-cache-dtype`
and the conv_state stays put.

> Note: `--enable-kv-cache-disk` does **not** exist in SGLang server_args — if a
> tutorial cites it, you read a fork or a hallucination. The real L3 path today is
> HiCache.

## 2. How the 4 seats shape cache reuse

`--max-running-requests 4` bounds concurrency; measured KV is 2.04 GiB K+V plus
1.84 GiB Mamba conv_state at the full 128K context (docker/README.md):

- **4 concurrent seats** → the radix tree shines when the four requests share a
  prefix (system prompt, RAG attachment). Shared nodes are stored once and all four
  slots ride the same path; leases/LRU leaf eviction handle contention.
- **Divergent prompts** → the tree fragments into four cold paths; the shared
  prefix is tiny, eviction pressure rises, and HiCache L3 prefetch becomes the
  difference between a 30-second re-prefill and a host-RAM read.
- **Agents re-asking the same question** → tree depth collapses (same prefix = one
  node), `sglang:cache_hit_rate` climbs, and the L3 write-back keeps the hot prefix
  propped up.

## 3. Verification

SGLang exposes `/metrics` on the engine port (30000; `--enable-metrics` is already in
the compose profile), scraped by VictoriaMetrics as
`job: llm-inference-engines, instance cheap-sglang:30000`. Confirm names at runtime —
metrics drift between releases.

| Metric | Type | What it tells you |
|---|---|---|
| `sglang:cache_hit_rate` | Gauge | radix tree hit ratio |
| `sglang:kv_used_tokens` / `sglang:kv_available_tokens` / `sglang:kv_evictable_tokens` | Gauge | GPU KV pool states |
| `sglang:kv_cache_memory_usage_gb` | Gauge | GPU KV pool footprint (baseline 2.04 GiB) |
| `sglang:hicache_host_used_tokens` / `sglang:hicache_host_total_tokens` | Gauge | L2 host pool occupancy vs cap (3 GB standard) |
| `sglang:cached_tokens_total` | Counter | tokens served from cache (cumulative) |
| `sglang:uncached_prompt_tokens_histogram` | Histogram | cold prefill token counts |
| `sglang:hicache_backup_*`, `sglang:hicache_dropped_tokens_total` | Counter | L2→L3 write-back traffic and drops |

Response-level: `usage.prompt_tokens_details.cached_tokens` in
`/v1/chat/completions` — the warm-cache smoking gun in every response.

VM one-liner: `sglang:cache_hit_rate`, and prove L3 is doing work with
`rate(sglang:hicache_backup_tokens_total[5m])` while idle.

## 4. Recipes

### L2 — HiCache host pool (3 GB standard)

**Already on in this repo's compose** — `cheap-sglang` ships the flags below:

```yaml
- "--enable-hierarchical-cache"
- "--hicache-size"
- "3"
```

Verify after `up` — `docker logs cheap-sglang` dumps `server_args=` with
`enable_hierarchical_cache=True, hicache_size=3`, then allocates
`HiCache kv host pool ... host memory` and ends with
`Tree cache initialized: ... hierarchical=True`. Watch the pool fill at
`localhost:30000/metrics`: `sglang:hicache_host_used_tokens` /
`sglang:hicache_host_total_tokens`.

```sh
docker compose -f docker/docker-compose.yml --profile sglang up -d
curl -s 'http://localhost:8428/api/v1/query?query=sglang%3Ahicache_host_used_tokens'
```

### L3 — file backend on a ramdisk vs SSD

*Optional / manual reconfig.* The `file` backend needs a directory; the cartridge is
the env var:

```yaml
# in the cheap-sglang service environment:
SGLANG_HICACHE_FILE_BACKEND_STORAGE_DIR: /dev/shm/sglang-hicache   # volatile ramdisk L3
# or: /var/lib/sglang-hicache                                      # persistent SSD L3
# command additions:
- "--hicache-storage-backend"
- "file"
- "--hicache-storage-prefetch-policy"
- "timeout"
- "--hicache-write-policy"
- "write_back"
```

Warm the cache with a long prompt, then check what L3 physically holds:

```sh
docker compose -f docker/docker-compose.yml --profile sglang exec cheap-sglang ls -la /dev/shm/sglang-hicache
```

Re-prompt the same text after restarting `cheap-sglang` — the SSD-backed dir survives,
the ramdisk doesn't; `sglang:cache_hit_rate` tells the story either way.
**RAM budget:** the ramdisk (2–4 GB house standard) co-resides with the 3 GB L2 host
pool in the same 32 GB — run `free -h`; while the ramdisk is mounted, `--hicache-size 2`
is the approved squeeze.

### KV dtype

```sh
--kv-cache-dtype fp8_e4m3     # 8-bit KV; note the Mamba conv_state is NOT quantized by this flag:
--mamba-ssm-dtype float16     # SSM state keeps its own precision (see nn-KV-cache-quantization.md)
```

## 5. Comparison table

| | llama.cpp | vLLM | SGLang |
|---|---|---|---|
| L1 prefix cache | per-slot KV, `--cache-prompt` (default on), `--cache-reuse` (min chunk to reuse, default 0), `--slot-prompt-similarity` 0.10 | PagedAttention + `--enable-prefix-caching` (LRU blocks, global) | RadixAttention (default on; LRU leaf eviction) |
| L2 CPU RAM | unified KV spill (`--kv-offload` on) + `--cache-ram` prompt cache (8192 MiB default) | `--kv-transfer-config` OffloadingConnector, `cpu_bytes_to_use` (pinned host RAM, async DMA) | HiCache `--enable-hierarchical-cache` + `--hicache-ratio/-size` |
| L3 disk | `--slot-save-path` + `POST /slots/{id}?action=save\|restore` (persistent gguf; cold-restart demo) | TieringOffloadingSpec + `fs` tier `root_dir` (persists, shareable across instances) | HiCache `--hicache-storage-backend file` → dir (persists) |
| KV dtype flags | `-ctk/-ctv q8_0\|q4_0\|f16…` | `--kv-cache-dtype fp8_e5m2\|fp8_e4m3` + `--kv-cache-dtype-skip-layers` | `--kv-cache-dtype fp8_e4m3\|fp8_e5m2` (+ scale path via `--quantization-param-path`) |
| Hybrid note | GGUF conv-state cached too | hybrid KV cache manager | LFM = FULL/SWA/MAMBA in one radix tree (`SGLANG_ENABLE_UNIFIED_RADIX_TREE=1`), `--mamba-full-memory-ratio` |

Quantization tradeoffs and engine flags: [nn-KV-cache-quantization.md](nn-KV-cache-quantization.md).
Sibling engine docs: [llama.cpp](nn-llamacpp-caching.md), [vLLM](nn-vLLM-caching.md).

## 6. Sources

- HiCache system design (L1/L2/L3, prefetch, write-back, backends): https://docs.sglang.ai/docs/advanced_features/hicache_design.md
- `--enable-hierarchical-cache` / `--hicache-*` / `--kv-cache-dtype` / Mamba args: https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/server_args.py
- HiCache file backend (HiCacheFile, `SGLANG_HICACHE_FILE_BACKEND_STORAGE_DIR`): https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/mem_cache/hicache_storage.py
- Metrics collector (cache/hicache gauge + counter names): https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/observability/metrics_collector.py
- Measured VRAM baselines: docker/README.md (this repo)