# llama.cpp KV caching (L1 → L2 → L3)

llama-server caches prefixes in three tiers that mirror how a CPU cache tree looks in
your head: a hot tier on the GPU, a cold tier in CPU RAM, and a persistent tier on
disk that survives restarts. Everything below is current-mode llama.cpp (b4900+); the
old pre-b4900 path-style saves (`/slots/0/save`) are dead — today it's the
`action`-style endpoints.

**The definitive guide is GitHub Discussion #20572, ["Tutorial: Persistent KV cache per
session with llama-server hooks"](https://github.com/ggml-org/llama.cpp/discussions/20572).**
The official fallback that survives doc churn is the server manual itself:
[tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) —
look for the `POST /slots/:id_slot?action=...` headings.

> Caveat: the community has been burned by AI-generated "summary" threads around
> caching (notably Discussion #20574, flagged as unreliable). Trust the server README
> and the tutorial above; treat rewrite symptoms and stray links with suspicion.

## 1. Cache model L1/L2/L3

### L1 — GPU: per-slot KV buffers + prompt matching

Every slot owns a KV buffer. Reuse between requests is driven by three flags:

- `--cache-prompt` — prompt caching, **on by default**. A request is matched against
  the slots' existing KV and only the unseen suffix gets evaluated.
- `--slot-prompt-similarity` (default `0.10`, `0.0` disables) — how much a request's
  prompt must overlap a slot's prompt before that slot is used. Lower = better reuse
  but dumber matching of unrelated prompts into hot slots.
- `--cache-reuse N` (default `0`) — **min chunk size to attempt reusing from the cache
  via KV shifting**. Note the modern semantics: it is not a probability (the old
  `0.2`/`0.8` readings were pre-b4900 folklore); it's the minimum token chunk size for
  KV-shift reuse, and it requires prompt caching to be on. `0` = disabled.

When LFM content (reasoning traces, tool calls) gets preserved across turns, the
GGUF conv-state / reasoning state participates in what's cached too — cache hits
shortcut prefill of the preserved context, which is why `--reasoning-preserve` makes
prompt reuse win more.

### L2 — CPU RAM: unified-KV spill + the prompt cache

Two mechanisms share the same RAM budget:

- **Unified KV spill** — with a single unified KV buffer (`--kv-unified`; enabled by
  default when the slot count is auto) and `--kv-offload` (**on by default**), KV that
  does not fit in VRAM overflows into host RAM instead of erroring. The llama.cpp
  profile in this repo starts with `--no-kv-unified` + an explicit `--parallel 4`, so
  the spill path is currently off — dropping `--no-kv-unified` restores it (see the
  recipe below).
- **Prompt cache in RAM** — `--cache-ram N` sizes a hot prompt cache for repeated
  prefixes (**default 8192 MiB**; `-1` = no limit, `0` = disabled), and
  `--cache-idle-slots` (on by default) saves idle slots into it on new tasks and
  clears them under unified KV. Our house standard is **3 GB (`--cache-ram 3072`)** —
  keep the rest of the 32 GB for the stack, your agents, and the L3 ramdisk.

### L3 — disk: slot save/restore

`--slot-save-path DIR` enables the persistent tier, then:

- `POST /slots/{id_slot}?action=save` — `{"filename": "slot_save_file.bin"}` writes
  the slot's KV cache into `DIR` (response `n_saved`, `n_written`, `timings.save_ms`).
- `POST /slots/{id_slot}?action=restore` — `{"filename": "..."}` reads it back
  (`n_restored`, `n_read`, `timings.restore_ms`) so a fresh process starts with the
  cache already in the buffer instead of re-prefilling.
- `POST /slots/{id_slot}?action=erase` — forget a saved cache (`n_erased`).

The saved files are GGUF — inspectable, filterable by search tool, and the basis of
the cold-restart demo below. Point `--slot-save-path` at `/dev/shm` for a volatile
ramdisk L3 or at an SSD dir for persistence across reboots.

## 2. How the 4 seats shape cache reuse

`--parallel 4` gives us four slots, and the model card's 128K context is split into
4 × 32K pre-allocated KV buffers (measured: KV 1.95 GiB, docker/README.md). Each of
the four concurrent sequences hogs its own slot:

- **4 busy agents with different topics** → each slot sees a different prefix, L1
  reuse drops to near zero, and `--slot-prompt-similarity` starts leeching
  dissimilar prompts into whichever slot matches "best" — the tradeoff for keeping
  the GPU fed.
- **Agents sharing a long system-prompt prefix** → slots are interchangeable, prompt
  cache hits everywhere, and `--cache-reuse` lets a later request KV-shift its way to
  the matching chunk instead of reprocessing it.
- CPU-RAM spill only pays off when the four seats actually overflow the VRAM KV
  budget — raise `--ctx-size` past the card's KV capacity and watch the spill happen
  (recipe below).

## 3. Verification

**`--metrics`** exposes `/metrics` on 8080. Real metric names (server README), scraped
by VictoriaMetrics as `job: llm-inference-engines, instance cheap-llamasrv:8080`:

| Metric | Type | What it tells you |
|---|---|---|
| `llamacpp:prompt_tokens_total` | Counter | prompt tokens processed (cold work) |
| `llamacpp:prompt_tokens_seconds` | Gauge | avg prompt throughput tokens/s |
| `llamacpp:n_decode_total` | Counter | llama_decode() calls |
| `llamacpp:n_busy_slots_per_decode` | Gauge | avg slots grinding per decode |
| `llamacpp:requests_processing` / `llamacpp:requests_deferred` | Gauge | request queue pressure |
| `llamacpp:tokens_predicted_total` | Counter | generation tokens |

Per-response cache visibility (there is **no** `llamacpp:prompt_tokens_cached_total` in
`/metrics` — cached tokens are only observable per request or per slot):

- `/completion` → `tokens_cached` (reused from a previous completion) and
  `tokens_evaluated`.
- `/v1/chat/completions` → `timings.cache_n` (prompt tokens reused from cache),
  `timings.prompt_n` (prompt tokens being processed), and
  `usage.prompt_tokens_details.cached_tokens`. Context total = `prompt_n + cache_n + predicted_n`.
- `GET /slots` → per-slot fields such as `cache_n` / `slot_prompt_n` are visible at
  runtime; the README documents them inside chat-completion timings, so treat the
  slots dump as "confirm at runtime".

VM query to watch reuse: `llamacpp:n_busy_slots_per_decode` over `rate`, and
`llamacpp:prompt_tokens_total` rate — when prompt tokens flatline while the
`n_busy_slots` metric climbs, the cache is doing the heavy lifting.

## 4. Recipes

### L2 spill demo — unified KV overflow to CPU RAM

*Optional / manual reconfig* — edits `docker-compose.yml` (`cheap-llamasrv` command):

```yaml
# remove: --no-kv-unified
# add:    --kv-offload            (default on; spill KV to CPU when VRAM is full)
# add:    --cache-ram 3072        (3 GiB prompt cache per house standard)
# add:    --ctx-size 200000       (blow past the card's KV capacity on purpose)
```

```sh
docker compose -f docker/docker-compose.yml --profile llamasrv up -d
watch -n1 nvidia-smi      # VRAM KV portion shrinks, compute stays
watch -n1 free -h         # host RAM grows — that's the spilled KV
curl -s 'http://localhost:8428/api/v1/query?query=llamacpp%3Aprompt_tokens_seconds'
```

### L3 cold-restart demo — save, restart, restore

The whole point of the persistent tier: TTF (time to first token) drops from
minutes-long prefill to ~0.2 s after restore on b4900+. With `--slot-save-path` set:

```sh
# 1) feed a long-ish prompt so slot 0 has something worth saving
curl -s http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"<long document, repeated a few times>"}]}' >/dev/null

# 2) persist slot 0
curl -s -X POST 'http://localhost:8080/slots/0?action=save' \
  -H 'Content-Type: application/json' -d '{"filename":"cold_restart.bin"}'
# {"id_slot":0,"filename":"cold_restart.bin","n_saved":...,"n_written":...,"timings":{"save_ms":...}}

# 3) cold restart the engine
docker compose -f docker/docker-compose.yml --profile llamasrv restart cheap-llamasrv

# 4) restore — prefill collapses
curl -s -X POST 'http://localhost:8080/slots/0?action=restore' \
  -H 'Content-Type: application/json' -d '{"filename":"cold_restart.bin"}'
# {"id_slot":0,"filename":"cold_restart.bin","n_restored":...,"n_read":...,"timings":{"restore_ms":...}}
```

Then re-run step 1 and compare first-token time against a no-restore cold start.
The timer-based auto-save trick from the community (cron hitting the save endpoint so
a crash doesn't lose long contexts) is exactly the wrapper that Issue #17107 collects.

### L3 ramdisk vs SSD

```yaml
--slot-save-path /dev/shm/llamacpp-kv      # volatile tmpfs ramdisk — fastest, lost on reboot
--slot-save-path /var/lib/llamacpp-kv      # SSD — survives reboots, used as persistent L3
```

**RAM budget:** while the ramdisk is mounted (our standard 2–4 GB in `/dev/shm`) it
co-resides in the same 32 GB as the L2 prompt cache — run `free -h` and, if the box
gets tight, drop `--cache-ram` to 2048 while the ramdisk is up.

### KV dtype

```sh
-ctk q8_0 -ctv q8_0   # 2x tokens per KV budget (see nn-KV-cache-quantization.md)
```

## 5. Comparison table

| | llama.cpp | vLLM | SGLang |
|---|---|---|---|
| L1 prefix cache | per-slot KV, `--cache-prompt` (default on), `--cache-reuse` (min chunk to reuse, default 0), `--slot-prompt-similarity` 0.10 | PagedAttention + `--enable-prefix-caching` (LRU blocks, global) | RadixAttention (default on; LRU leaf eviction) |
| L2 CPU RAM | unified KV spill (`--kv-offload` on) + `--cache-ram` prompt cache (8192 MiB default) | `--kv-transfer-config` OffloadingConnector, `cpu_bytes_to_use` (pinned host RAM, async DMA) | HiCache `--enable-hierarchical-cache` + `--hicache-ratio/-size` |
| L3 disk | `--slot-save-path` + `POST /slots/{id}?action=save\|restore` (persistent gguf; cold-restart demo) | TieringOffloadingSpec + `fs` tier `root_dir` (persists, shareable across instances) | HiCache `--hicache-storage-backend file` → dir (persists) |
| KV dtype flags | `-ctk/-ctv q8_0\|q4_0\|f16…` | `--kv-cache-dtype fp8_e5m2\|fp8_e4m3` + `--kv-cache-dtype-skip-layers` | `--kv-cache-dtype fp8_e4m3\|fp8_e5m2` (+ scale path) |
| Hybrid note | GGUF conv-state cached too | hybrid KV cache manager | LFM = FULL/SWA/MAMBA in one radix tree (`SGLANG_ENABLE_UNIFIED_RADIX_TREE=1`), `--mamba-full-memory-ratio` |

Quantization tradeoffs and engine flags: [nn-KV-cache-quantization.md](nn-KV-cache-quantization.md).
Sibling engine docs: [vLLM](nn-vLLM-caching.md), [SGLang](nn-SGLang-caching.md).

## 6. Sources

- llama.cpp server manual / OpenAPI tools spec: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Tutorial: Discussion #20572 "Persistent KV cache per session with llama-server hooks": https://github.com/ggml-org/llama.cpp/discussions/20572
- Community save-on-a-timer walkthrough: https://ai-muninn.com/en/blog/kv-cache-disk-restore-7x
- Feature request + wrapper scripts: https://github.com/ggml-org/llama.cpp/issues/17107
- Server manual discussion reference: https://github.com/ggml-org/llama.cpp/discussions/16979
- Measured VRAM baselines: docker/README.md (this repo)