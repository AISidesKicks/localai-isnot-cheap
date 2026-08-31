# KV cache streaming — running 100K+ context on a 12 GB card without OOM

The KV cache grows unbounded with context length. At 100K tokens a 7B model needs
~50 GB of KV cache; a 70B needs ~260 GB. You cannot fit that on any consumer card.
Streaming techniques bound the cache so you can serve arbitrarily long contexts on
a 12 GB RTX 4070 — by either dropping old tokens or moving them to host RAM.

## The problem: VRAM wall

Every decoded token appends K and V vectors for every layer. At fp16 that's 2 bytes
per value × 2 (K+V) × hidden_dim × num_layers. For a 7B model (32 layers, 4096 dim)
at 100K tokens: 32 × 4096 × 2 × 2 × 100 000 ≈ **50 GB**. For a 70B (80 layers,
8192 dim): ≈ **260 GB**. Even with KV quantization (see
[KV cache quantization](nn-extreme-quantizations.md)) at q8_0 you're still at 25 GB
for 7B / 130 GB for 70B — way past any consumer card's budget. You need to either
drop tokens or spill them off-device.

## StreamingLLM — attention sinks + sliding window

MIT-Han lab's [StreamingLLM](https://github.com/mit-han-lab/streaming-llm) (7.3k
stars) observes that initial tokens act as "attention sinks" — they receive
disproportionate attention regardless of content. The insight: keep the first 4
tokens (the sink) plus a sliding window of the last N tokens. Drop everything in
the middle. The KV cache is now bounded at **N + 4 tokens** regardless of input
length, so a 7B at fp16 with window=4096 needs ~2 GB of KV cache — trivially fits
on any card.

The tradeoff: the model **cannot attend to tokens outside the window**. Retrieval
over long documents works only if the answer is in the window. For conversational
chat where only recent context matters this is fine; for full-document
understanding it falls apart.

### Quality impact

- Prefill quality is near-identical (the sink preserves the initial system prompt).
- Decode quality degrades as the window moves past relevant context.
- Passkey-style tests fail once the target passes out of the window.
- Works best with models fine-tuned for windowed attention (most modern chat models
  already are).

### Concrete numbers on a 12 GB card

| Config | KV cache | VRAM headroom | Tok/s |
|---|---|---|---|
| 7B, fp16, window=4096 | ~2.0 GB | ~6 GB free | 25–40 |
| 7B, q8_0, window=4096 | ~1.0 GB | ~7 GB free | 30–45 |
| 7B, q4_0, window=4096 | ~0.5 GB | ~7.5 GB free | 35–50 |

On an RTX 4070 12 GB the VRAM headroom after model weights (7B at Q4_K_M ≈ 4 GB)
and KV cache leaves comfortable room for batch size 1 decode. PCIe bandwidth is
not a factor — everything fits on-device.

## H2O — heavy hitter eviction

FMInference's [H2O](https://github.com/FMInference/H2O) (532 stars) takes a
different approach: score each token's cumulative attention and keep only the
top 20% scoring tokens. When the cache fills, evict the lowest-scoring tokens.
The sliding window is implicit — recent tokens naturally accumulate high scores,
but an old token that continues to receive attention stays cached.

H2O preserves more long-range retrieval capability than a pure sliding window,
but it still **drops tokens permanently** — once evicted, a token cannot be
re-attended. The scoring heuristic is a post-hoc approximation of "what matters,"
not an exact optimization.

## Adaptive KV streaming — the llama.cpp fork

This is the technique the lab actually runs. The fork at
[RaymondHuang210129/llama.cpp-adaptive-kv-streaming](https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming)
(75 stars) is the key differentiator from the token-dropping approaches above:
**it preserves exact attention over the full context** by storing authoritative KV
tensors in pinned host RAM and keeping only a bounded working set on the GPU.

### How it works

Three ideas that together make it work:

1. **Pinned host memory as the authoritative store.** KV tensors are allocated in
   pinned (page-locked) host RAM via `cudaHostAlloc`. The GPU can DMA directly from
   pinned memory without a bounce buffer — PCIe bandwidth becomes the only limit.

2. **Bounded CUDA staging pool.** A fixed-size CUDA pool (controlled by
   `--kv-stream-stage-mib N`) holds the "active" KV window. When the pool fills,
   the oldest staged KV entries are evicted from VRAM but remain in pinned host
   memory — they are **not dropped**, just moved off-device.

3. **Overlapped prefetch.** While the GPU computes on the current layer, a worker
   thread prefetches the next layer's KV slices from pinned host RAM into the CUDA
   staging pool. This hides PCIe latency behind compute.

The runtime adapts the on-device / off-device split based on available VRAM. The
result: **exact attention over the full context**, no token dropping, no
approximation, no accuracy loss.

### Caveats

The README explicitly warns this is **research code optimized and
production-validated primarily for RTX 5070 Ti 16 GB** — it is untested on other
GPUs, KV quantization combinations, or parallel slots. The lab tested it on a
RTX 5070 Ti 16 GB + Qwen3.8-27B at 262K context; results below are from that
configuration. On a 12 GB card the pool must shrink proportionally.

## Comparison

| | StreamingLLM | H2O | Adaptive KV streaming |
|---|---|---|---|
| **Memory bound** | N + 4 tokens | ~20% of tokens | Staging pool + pinned host RAM |
| **Attention fidelity** | Approximate (windowed) | Approximate (evicted) | **Exact** (no token dropped) |
| **Hardware requirement** | Any GPU | Any GPU | GPU + sufficient host RAM + PCIe 4.0 |
| **Stars** | 7.3k | 532 | 75 |
| **Limitation** | No out-of-window retrieval | Permanent eviction | PCIe bandwidth bottleneck; research code |

## RTX 4070 12 GB + 32 GB RAM — concrete numbers

The lab's RTX 4070 (12 GB VRAM, 32 GB host RAM, PCIe 4.0 ×16) is the target.
Here is how the three approaches pencil out:

**StreamingLLM on 7B (INT4):** model weights ~4 GB, KV cache window=4096 at q4_0
~0.5 GB. Total ~4.5 GB — plenty of headroom. 25–40 tok/s, no PCIe pressure.

**Adaptive KV on 27B (Q3_K_XL):** model weights ~3.5 GB at Q3_K_XL quantization,
staging pool ~2.3 GB (conservative for a 12 GB card — the fork's tested config
used a larger pool on 16 GB). Pinned host memory holds the full 262K context. The
GPU-to-host link is PCIe 4.0 ×16 (~25 GB/s real-world) and is the bottleneck:
~2–4 tok/s for 262K context. At shorter contexts (32K–64K) the staging pool covers
more of the working set and throughput rises to 8–15 tok/s.

**The bottleneck is PCIe, not compute.** At 2–4 tok/s the GPU is idle most of the
time waiting for KV slices to arrive from host RAM. This is the tradeoff for exact
attention — the token-dropping approaches pay zero PCIe tax but lose context.

### VRAM budget breakdown for adaptive streaming on 12 GB

| Component | Size |
|---|---|
| Model weights (27B, Q3_K_XL) | ~3.5 GB |
| KV staging pool (--kv-stream-stage-mib 2300) | ~2.3 GB |
| CUDA kernels + overhead | ~1.5 GB |
| Unused (room for batch, scratch) | ~4.7 GB |

Total consumed: ~7.3 GB. The remaining ~4.7 GB is available for larger staging
pools or higher batch sizes — but the README warns the fork is untested on 12 GB
cards, so conservative tuning is advised.

## How to build and run

```sh
git clone https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming
cd llama.cpp-adaptive-kv-streaming
mkdir build && cd build
cmake .. -DLLAMA_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89  # RTX 4070 = sm_89
cmake --build . --config Release -j$(nproc)
```

Server invocation:

```sh
./llama-server \
  --model Qwen3.8-27B-UD-Q3_K_XL.gguf \
  --ctx-size 262144 \
  -ngl 100 \
  --kv-stream --kv-stream-stage-mib 2300 \
  -ctk q8_0 -ctv q4_0 \
  -b 512 -ub 512 \
  --temp 0.0
```

Flag breakdown:
- `--kv-stream` enables adaptive KV streaming (replaces the default contiguous cache).
- `--kv-stream-stage-mib N` sets the CUDA staging pool in MiB. Start at 60% of
  available VRAM after weights. On 12 GB with a 3.5 GB model that is ~5000 MiB;
  on 16 GB you can go higher. The tested config used 2300 MiB on the 16 GB card
  alongside the 27B model — be generous but leave room for CUDA overhead.
- `-ctk q8_0 -ctv q4_0` quantizes the KV cache (see
  [KV cache quantization](nn-extreme-quantizations.md) for the quality tradeoffs).
- `-b 512 -ub 512` sets batch size and unbatch size — larger batches improve
  prefetch overlap.

Optional unified memory (experimental): set `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`
in the environment to make model buffers managed memory. The KV streaming pool
itself stays `cudaMalloc`-allocated in VRAM — UM only affects the weight tensors.

### Tuning the staging pool

The `--kv-stream-stage-mib` value is the main tuning knob:
- **Too small:** frequent evictions from the staging pool increase PCIe traffic.
  Prefetch cannot keep up and throughput drops.
- **Too large:** the pool competes with model weights for VRAM. GPU falls back to
  system RAM for weight layers (`-ngl` partial offload), which is slower than
  unified memory.
- **Sweet spot:** enough to cover the active KV window for your typical decode
  batch. For single-token decode at 27B / 262K context, 2–3 GiB is sufficient.
  For larger batch sizes, increase proportionally.

## Sources

- GitHub repo (adaptive KV streaming fork):
  https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming
- Official project story (Medium):
  https://medium.com/@raymond860909/enabling-long-context-inference-on-16gb-vram-gpu-using-adaptive-kv-cache-streaming-in-llama-cpp-84c1592b90c5
- YouTube walkthrough:
  https://www.youtube.com/watch?v=n_ggLjIgRcM
- StreamingLLM paper — attention sinks and sliding window:
  https://arxiv.org/abs/2309.17453
- H2O paper — heavy hitter eviction:
  https://arxiv.org/abs/2306.14048
- llama.cpp caching tiers (general context):
  [llama.cpp caching](nn-llamacpp-caching.md)
- KV cache quantization (complementary technique):
  [KV cache quantization](nn-extreme-quantizations.md)