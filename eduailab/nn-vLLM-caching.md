# vLLM KV caching (L1 → L2 → L3)

vLLM splits its KV story across the same three tiers as the other engines: a global
LRU block cache on the GPU, an offload tier in pinned host RAM, and — when you ask
for it — a tier that spills completed blocks to a filesystem directory (SSD, or a
tmpfs ramdisk for the cheap version). The interesting bit for a lab is that the L2/L3
mechanics are all sold as one knob: `--kv-transfer-config`, a JSON blob that picks a
connector and a spec.

## 1. Cache model L1/L2/L3

### L1 — GPU: PagedAttention + prefix caching

KV lives in fixed-size pages via PagedAttention, and prefix reuse is a block-hash
game:

- `--enable-prefix-caching` — Automatic Prefix Caching. Same-hash blocks are shared
  across sequences instead of recomputed, and the cache is **global, LRU-evicted** —
  blocks from any sequence stick around until the GPU budget forces them out.
- **Status:** this repo's compose now sets it on `cheap-vllm` (between
  `--max-num-seqs 4` and the healthcheck), so the out-of-the-box lab runs with
  the L1 tier live. Verify with `docker inspect cheap-vllm` or by watching
  `vllm:prefix_cache_hits_total` after two prompts that share a prefix.
- Watch: `vllm:prefix_cache_queries_total` / `vllm:prefix_cache_hits_total`
  (both in tokens), timed demo in `smoketests/cinematic-01` `--cache-mode 1level`.

### L2 — CPU RAM: the OffloadingConnector

The L2 tier is the `OffloadingConnector` (`kv_connector: "OffloadingConnector"`),
which pushes completed KV blocks into **pinned host RAM** with async DMA
(`cudaMemcpyAsync`) so the transfer overlaps with model compute instead of stalling
it. Its spec controls the rest:

- `CPUOffloadingSpec` (default) — one CPU tier, `cpu_bytes_to_use` caps the pinned
  buffer. House standard: **3 GB** → `"cpu_bytes_to_use": 3221225472` (bytes).
- Hits promote blocks back GPU-side on demand (LRU with `eviction_policy: lru`).
- `kv_role: "kv_both"` means the instance reads and writes the shared cache.

### L3 — disk: TieringOffloadingSpec

Give the OffloadingConnector `spec_name: "TieringOffloadingSpec"` plus a
`secondary_tiers` list, and completed blocks get staged from the CPU tier (the only
tier with direct GPU access) down to the `fs` tier:

```json
{
  "type": "fs",
  "root_dir": "/var/lib/vllm-kv",
  "n_read_threads": 16,
  "n_write_threads": 16
}
```

- **Persistent and shareable across instances** — vLLM shards blocks underneath
  `root_dir` as `<model>_<digest>_r<rank>/<hhh>/<hh>_g<group>/<hash>.bin`, so
  "show me the cached blocks on disk" is a `find` away (recipe below).
- Cross-process sharing works by default: block content hashes use a fixed seed
  (`NONE_HASH`). Only the `xxhash`/`xxhash_cbor` `--prefix-caching-hash-algo` modes
  seed per-process — those need a matching `PYTHONHASHSEED` on every instance to
  share a cache directory.
- Only the CPU tier has direct GPU access; L3 traffic always stages through RAM.
  `block_size`/`blocks_per_chunk` control offload chunking, and
  `eviction_policy: lru` (or `arc`) governs the CPU tier.

## 2. How the 4 seats shape cache reuse

`--max-num-seqs 4` bounds concurrent sequences, and the rest of the picture falls
out of the memory budget (measured: KV 6.62 GiB at `--gpu-memory-utilization 0.92`,
docker/README.md):

- **4 seats with divergent prompts** → L1 blocks churn under LRU constantly; each new
  request evicts yesterday's winners. The offload connector exists for exactly this:
  completed prefill blocks get parked in L2/L3 instead of dying, so tomorrow's
  re-prompt only pays L1→L2/L3→L1 fetch, not full prefill.
- **4 seats sharing a system prompt / few-shot prefix** → prefix-caching dedups the
  shared pages GPU-side; the offload tiers barely get touched, which is also the
  healthy state to verify against in metrics.
- **Fewer than 4 seats busy** → with `kv_both` offloading, idle-block eviction to
  disk frees VRAM for bigger batches, at the price of L3 read latency on wake-up —
  the tiering spec's staged CPU buffer is what keeps that latency from stalling
  decode.

## 3. Verification

vLLM serves `/metrics` on the API port (8000); VictoriaMetrics scrapes it as
`job: llm-inference-engines, instance cheap-vllm:8000`.

| Metric | Type | What it tells you |
|---|---|---|
| `vllm:kv_cache_usage_perc` | Gauge | KV block pool utilization % |
| `vllm:prefix_cache_queries` / `vllm:prefix_cache_hits` | Counter | global prefix cache hits vs lookup queries |
| `vllm:external_prefix_cache_queries` / `vllm:external_prefix_cache_hits` | Counter | hits coming from the offload connector's cache |
| `vllm:kv_offload_store_bytes` / `vllm:kv_offload_store_time` | Counter | bytes+time pushed GPU → offload tiers |
| `vllm:kv_offload_load_bytes` / `vllm:kv_offload_load_time` | Counter | bytes+time fetched back offload → GPU |
| `vllm:kv_offload_load_size` / `vllm:kv_offload_store_size` | Histogram | per-op transfer sizes |
| `vllm:kv_offload_allocation_failure` | Counter | offload store allocation failures (tune down `cpu_bytes_to_use`) |

Legacy labels still emitted: `vllm:kv_offload_total_bytes`, `vllm:kv_offload_total_time`
(with `transfer_type` label). Response-level: `/v1/chat/completions` returns
`usage.prompt_tokens_details.cached_tokens` — the count you want to watch go up as the
cache warms.

VM one-liner for reuse: `sum(rate(vllm:prefix_cache_hits[5m])) /
sum(rate(vllm:prefix_cache_queries[5m]))` and the offload pressure is
`rate(vllm:kv_offload_store_bytes[5m])`.

## 4. Recipes

### L2 — single-tier CPU offload (3 GB standard)

*Optional / manual reconfig* — edit the `cheap-vllm` command in `docker-compose.yml`:

```yaml
# add to the vllm command list:
- "--kv-transfer-config"
- '{"kv_connector":"OffloadingConnector","kv_role":"kv_both","kv_connector_extra_config":{"cpu_bytes_to_use":3221225472}}'
```

```sh
docker compose -f docker/docker-compose.yml --profile vllm up -d
# counter goes up as long prompts finish and their blocks get parked:
curl -s 'http://localhost:8428/api/v1/query?query=rate(vllm%3Akv_offload_store_bytes%5B5m%5D)'
```

### L3 — fs tier on a ramdisk vs SSD

*Optional / manual reconfig.* Add `--enable-prefix-caching` too so the L1 hashes match
what L3 stores:

```yaml
- "--enable-prefix-caching"
- "--kv-transfer-config"
- '{"kv_connector":"OffloadingConnector","kv_role":"kv_both","kv_connector_extra_config":{"spec_name":"TieringOffloadingSpec","cpu_bytes_to_use":3221225472,"block_size":16,"eviction_policy":"lru","secondary_tiers":[{"type":"fs","root_dir":"/dev/shm/vllm-kv"}]}}'
```

After a warm-up run, see the cached blocks on disk:

```sh
docker compose -f docker/docker-compose.yml --profile vllm exec cheap-vllm find /dev/shm/vllm-kv -name '*.bin' | head
```

**Ramdisk vs SSD:** point `root_dir` at `/dev/shm/vllm-kv` for the volatile, fastest
L3, or at `/var/lib/vllm-kv` for persistence across reboots (restart
`cheap-vllm`, then re-prompt the same text and watch
`vllm:prefix_cache_hits` — only the SSD tier survives the restart).
**RAM budget:** `/dev/shm` (2–4 GB house standard) co-resides with the 3 GB L2 in the
same 32 GB — run `free -h`; drop `cpu_bytes_to_use` to 2147483648 (2 GB) while the
ramdisk is mounted.

### KV dtype

```sh
--kv-cache-dtype fp8_e4m3     # 8-bit KV, 2x tokens per budget (see nn-KV-cache-quantization.md)
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
Sibling engine docs: [llama.cpp](nn-llamacpp-caching.md), [SGLang](nn-SGLang-caching.md).

## 6. Sources

- KV offloading usage guide (OffloadingConnector, TieringOffloadingSpec, fs tier, on-disk layout): https://github.com/vllm-project/vllm/blob/main/docs/features/kv_offloading_usage.md
- `--kv-transfer-config` / `--kv-cache-dtype` argument definitions: https://github.com/vllm-project/vllm/blob/main/vllm/engine/arg_utils.py
- Prefix caching docs and metrics: https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html
- Measured VRAM baselines: docker/README.md (this repo)