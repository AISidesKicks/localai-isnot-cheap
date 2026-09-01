# Extreme model and KV cache quantizations

We are targeting Qwen3.8-27B on a 12 GB GPU (RTX 4070) with 32K+ context using
[unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) - specifically
the **IQ3_XXS** (10.9 GB) and **IQ4_XS** (14.3 GB) quants.

Run Qwen3.8-27B on ANY GPU (8GB to 32GB): Here's How
https://www.youtube.com/watch?v=0xUxO_9zqTU

Qwen3.8-27B takes roughly 54 GB in full precision - but with the right quantization,
KV-cache settings, and CPU offloading strategy, you can run it on consumer GPUs with
anywhere from 8 GB to 32 GB of VRAM.

In this video I break down the best setup for each GPU tier: 8 GB, 12 GB, 16 GB, 24 GB,
and 32 GB. We compare modern low-bit GGUF quants, Q4 quality-focused configurations,
KV-cache precision, context limits, selective RAM offloading, and speculative decoding.

You'll learn:
- Which Qwen3.8-27B quant fits your GPU
- When to use a fully VRAM-resident model
- How to split weights between GPU and system RAM
- The best KV-cache settings for longer context
- Expected speed and quality compromises at each VRAM tier
- When GGUF, EXL3, and NVFP4 make sense
- How MTP and D-Flash 2 can improve generation speed

The video also covers example configurations for GPUs such as the RTX 3070, RTX 3060
12 GB, RTX 4060 Ti 16 GB, RTX 4070 Ti Super, RTX 3090, RTX 4090, RTX 5090, RX 5700 XT,
and RX 7900 XTX.

Chapters:
00:00 - Overview & Unquantized Footprint
00:19 - Hybrid DeltaNet Architecture Explained
01:04 - KV Cache & Context Memory Costs
01:33 - Total VRAM Budgeting Breakdown
01:54 - Control 1: Weight Quantization & GSQ-RCO
02:35 - Control 2: KV Cache Precision
02:51 - Control 3: CPU Offloading & RAM Speed
03:24 - 8 GB GPUs (RTX 3070 / 4060 / RX 5700 XT)
05:12 - 12 GB GPUs (RTX 3060 / RTX 4070)
06:26 - Question for the Comments
06:48 - 16 GB GPUs (RTX 4060 Ti / 4080 / RX 7800 XT)
07:52 - llama.cpp CUDA Context Caveat (27623)
08:21 - 24 GB GPUs (RTX 3090 / 4090 / RX 7900 XTX)
09:41 - 32 GB Cards & RTX 5090 NVFP4
10:23 - Advanced Speculative Drafting (D-Flash 2)
10:45 - Open-Weight Strategy & Final Takeaways

## Qwen3.8-27B Architectural Advantages

**Hybrid Attention Design:** Qwen3.8-27B uses a 3:1 hybrid across its **64 layers** [00:00].
Only **16 full-attention layers** grow a KV cache - the remaining **48 DeltaNet layers**
use a fixed ~250 MB/slot recurrent state that does NOT grow with context. This radically
changes VRAM math vs. dense models.

**KV Cache Efficiency:** Because KV only lives on 16 layers, per-token KV is roughly
**16 KB at 4-bit** (vs. ~64 KB for a dense 27B). A 64K context uses ~1 GB of 4-bit KV
cache; a full 256K context uses ~4 GB.

## Primary Controls for Memory Management

To fit the model onto constrained hardware, manage your memory budget across three levers:

**Weight Quantization:** Scaling from Q8 down to ultra-low-bit quants like IQ3_XXS
(**10.9 GB**, confirmed on Hugging Face) using GSQ-RCO methods.

**KV Cache Precision:** Using Q8 keys with Q4 values provides balanced quality, while
pure Q4 maximizes context on smaller cards.

**CPU Offloading:** Shifting feed-forward network tensors to system RAM. **Heavily
dependent on memory bandwidth** - the lab uses DDR4 (~25-30 GB/s effective), not DDR5
(~60+ GB/s). Expect 3-5 tok/s under heavy offload vs. the 9-10 tok/s estimates in the
video that assume DDR5.

## Hardware Tiers and Expected Performance

**8 GB VRAM (RTX 3070, 4060, RX 5700 XT):** Requires aggressive CPU offloading with
low-bit quants. Expect ~7-24 tok/s depending on backend and quantization aggressiveness.

**12 GB VRAM (RTX 3060, 4070):** The sweet spot. A 3-bit quant (10.9 GB IQ3_XXS) fits
with room for KV cache. With K=8/V=4, 32-64K context runs at native GPU speeds yielding
10-15 tok/s.

**16 GB VRAM (RTX 4060 Ti, 4080, RX 7800 XT):** High-grade quants run fully resident.
Sustains ~45 tok/s at low context, ~40 tok/s at 21K context. Note the llama.cpp CUDA
bug that collapses throughput past 80K context.

**24 GB VRAM (RTX 3090, 4090, RX 7900 XTX):** Q4KM runs at 42 tok/s, up to 65.6 tok/s
with multi-token prediction. Enough headroom for the full 262K context window on a
single card.

**32GB+ & Next-Gen:** Workstation cards support Q5KM or Q6K. RTX 5090 with NVFP4 in
vLLM + 4-bit TurboQu KV pushes ~160 tok/s across the full 262K context.

## Recipes

### Download

```sh
huggingface-cli download unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-IQ3_XXS.gguf --local-dir docker/models/
huggingface-cli download unsloth/Qwen3.8-27B-GGUF Qwen3.8-27B-UD-IQ4_XS.gguf --local-dir docker/models/
```

### Config A - IQ3_XXS (10.9 GB, fits 12 GB card)

Target: RTX 4070 12 GB, 32-64K context, fully VRAM-resident.

Recommended KV cache: K at 8-bit (`q8_0`), V at 4-bit (`q4_0`). This protects
needle-in-a-haystack retrieval (8-bit keys prevent forgetting) while halving the value
footprint. On Qwen3.8's 16-layer KV, this combo leaves almost all 12 GB for the weights.

```sh
llama-server \
  -m /models/Qwen3.8-27B-UD-IQ3_XXS.gguf \
  -ngl 99 \
  --ctx-size 64000 \
  --cache-type-k q8_0 \
  --cache-type-v q4_0 \
  --flash-attn auto
```

(Older versions used `-ctk q8_0 -ctv q4_0`; long-form flags are preferred in b4900+.)

### Config B - IQ4_XS (14.3 GB, requires CPU offload on 12 GB)

Target: RTX 4070 12 GB, needs RAM offload for weights. Better quality than IQ3_XXS
at the cost of speed (DDR4 penalty applies).

```sh
llama-server \
  -m /models/Qwen3.8-27B-UD-IQ4_XS.gguf \
  -ngl 30 \
  --ctx-size 32000 \
  --cache-type-k q8_0 \
  --cache-type-v q4_0 \
  --flash-attn auto
```

`-ngl 30` offloads ~8 GB of weights to CPU RAM. On DDR4 expect 3-5 tok/s; the video's
9-10 tok/s estimate assumes DDR5.

### KV Config Comparison

| KV Cache Config | VRAM Impact | Quality | Use Case |
|---|---|---|---|
| K q8_0 / V q4_0 | Very Low | Near perfect | Best choice - max accuracy with 12 GB headroom |
| K q4_0 / V q4_0 | Lowest | Good | Only if OOM at high contexts |
| fp16 / fp16 | High | Perfect | Avoid on 12 GB - forces CPU offloading |

### MTP note

The Hugging Face repo also hosts multi-token prediction GGUFs (`MTP Q4_0`, 1.37 GB).
The video mentions D-Flash 2 for speculative decoding speed gains - worth experimenting
with if generation latency is a priority.

===============================
# KV cache quantization - squeezing 2-4x more context out of the same VRAM

The KV cache quietly eats most of the VRAM in a long-context lab. On a **dense model**
every decoded token appends K and V for every layer. Qwen3.8-27B changes this math
dramatically - only 16 of 64 layers grow KV - but when you do run a dense model (or
push Qwen3.8 past 128K), quantization still pays off.

Measured baselines on our RTX 4070 (12 GiB) with a small dense SLM: llama.cpp KV lands
at **1.95 GiB** (of 5.0 GiB total), vLLM at **6.62 GiB** (of 11.4 GiB), SGLang at
**2.04 GiB** K+V plus **1.84 GiB** Mamba conv_state (of 9.37 GiB). On that dense
footprint the KV cache is the biggest GPU resident. For Qwen3.8 the KV share is far
smaller - the 2x/4x quantization claim applies to **dense** contexts; on the Qwen hybrid,
KV quantization is a secondary lever after weight quantization.

## Why quantize the KV cache at all - the memory math

Every decoded token appends a K and a V vector **per KV-growing layer** into the cache.
Stored plain, that is **2 bytes per value** (`fp16`). Cut the value to 1 byte (`fp8` /
`q8_0`) and the same VRAM holds **2x the tokens**; cut it to 4 bits (`fp4` / `q4_0`,
0.5 bytes) and it holds **4x**. The tokens-in-budget math below assumes **dense K/V
per layer** - on Qwen3.8 (16 of 64 layers) multiply the "tokens" column by ~0.25:

| KV value size | Bytes/value | Tokens in the same KV budget |
|---|---|---|
| `fp16` (default) | 2 | 1x |
| `fp8` / `q8_0` | 1 | 2x |
| `fp4` / `q4_0` | 0.5 | 4x |

For a 128K-context seat on a dense model that's the difference between "half the card
is cache" and "the cache barely matters anymore". On Qwen3.8 you start with a tiny
cache anyway, so the gain is less dramatic but still valuable for extreme contexts.

## Quality physics - the reason it is not free

The 8-bit boundary is the sweet spot and 4-bit is where it starts to hurt:

- **8-bit (q8_0, fp8_e4m3, fp8_e5m2) is near-lossless** for most models and workloads.
  Prefill/decode quality and passkey-style tests hold up in practice.
- **4-bit (q4_0) genuinely degrades output**, and it gets worse exactly in the
  situations our lab runs into:
  - **Long contexts** - quantization error accumulates with context length; every
    token reads K/V values that are a little fuzzier, and the fuzz compounds.
  - **Attention-heavy prompts** - more tokens read the cache, so more of the error
    reaches the output.
  - **Small models** - a 27B model has more redundancy than a 2.6B SLM but less than
    a 70B. The Qwen3.8 hybrid helps by reducing the number of layers that touch
    quantized KV.
- **Scaling factors are the real knob.** Storing 8-bit values is only half the story;
  you also need scales to map back to the fp16 range:
  - **Per-tensor vs per-head scaling** changes accuracy materially - per-head (what
    llama.cpp's fused quant kernels use) tracks the real per-key/per-value range,
    per-tensor averages it out and loses precision.
  - **The default-scale = 1.0 pitfall** - if the engine falls back to scale `1.0`
    (identity) instead of learned/calibrated scales, the "quantized" cache is
    effectively truncated fp16: modules that rely on the caller passing the scales
    silently lose precision. When comparing numbers, always check that scales are
    actually in play, not just that the dtype flag says "8-bit".

Further reading (the actual research lineage): **KIVI** and **KVQuant** are the two
papers this whole area grew out of - both explain the per-channel/per-head scaling
designs and why 2-bit/4-bit KV cache only works when the scales are handled right.

## Engine samples - exact flags + what to measure

All three engines can store KV at lower precision today. Flags below are manual
reconfig labs, not the in-repo default. Measure the cache with the engine's own
metrics or `nvidia-smi`.

### llama.cpp

```sh
# manual lab only (default in-repo is fp16):
--cache-type-k q8_0 --cache-type-v q8_0   # K and V quantized, per-block scales
# 4x tokens, watch quality on long contexts:
--cache-type-k q4_0 --cache-type-v q4_0
```

Measure: `nvidia-smi` VRAM before/after, or VictoriaMetrics
`llamacpp:prompt_tokens_seconds` (prefill throughput rises when the KV fits tighter).
Baselines: KV 1.95 GiB of 5.0 GiB at `--cache-type-k f16 --cache-type-v f16` on
LFM2.5-2.6B-Q8_0, 128K context.

### vLLM

```sh
--kv-cache-dtype fp8_per_token_head  # only if/when the hybrid gains explicit support
--kv-cache-dtype fp8_e4m3            # 8-bit, E4M3 (static scales - hybrid trap)
--kv-cache-dtype fp8_e5m2            # 8-bit, E5M2 (static scales - hybrid trap)
--kv-cache-dtype-skip-layers 4       # keep the first N layers fp16 - they see every token
```

**Default on our hybrid: fp16.** The repo's `cheap-vllm` container runs no
`--kv-cache-dtype`, so vLLM stores KV at the default fp16. `fp8_per_token_head` is
vLLM's scale-free 8-bit - it computes dynamic per-token-head scales at runtime
(`kv_scales.json` unneeded) and the validator logs *"Dynamic per-token-head scales
will be computed at runtime"* on dense models. But the scale-free path is **not** a
free pass on hybrids: recurrent layers still need scale calibration that skips them,
so use `fp8_per_token_head` only if/when the hybrid gains explicit support. The
`fp8_e4m3`/`fp8_e5m2` static scales silently fall back to `1.0` when calibration is
disabled on recurrent layers (vLLM #52793, #52475).

Measure: `vllm:kv_cache_usage_perc` and `vllm:prefix_cache_hits` on `/metrics`, plus
the VRAM baseline in docker/README.md (KV 6.62 GiB of 11.4 GiB at the default fp16).

### SGLang

```sh
--kv-cache-dtype fp8_e4m3                    # 8-bit (also fp8_e5m2)
--quantization-param-path kv_scales.json     # per-layer KV-cache scaling factors
```

SGLang runs a separate **scale path** for the quantized cache - verify the scale
tensors are present, otherwise the dtype flag is a no-op. Point the path at a JSON of
per-layer KV-cache scaling factors (`kv_scales.json` above); without it SGLang
defaults those scales to `1.0`, which `server_args` warns "may cause accuracy issues".
**On our LFM2.5-2.6B, fp8 is effectively unsupported here**: fp8 needs the
scale-path JSON, but the LFM2 model class has no scale-load path, so there is no way
to feed it calibrated scales. For **Qwen3.8** the same caveat applies - verify before
enabling. Measure: `sglang:kv_cache_memory_usage_gb` and `sglang:cache_hit_rate`.
Baselines: 2.04 GiB K+V + 1.84 GiB Mamba conv_state.
Note the Mamba **conv_state and SSM state are *not* covered by `--kv-cache-dtype`** -
they live in their own buffers (`--mamba-ssm-dtype` controls the SSM state) - so a
hybrid model keeps a chunk of cache in high precision no matter what you ask for.
Qwen3.8's DeltaNet state is similarly separate from the KV cache and does not grow
with context.

**Baseline snapshot (cinematic-01, non-quantized fp16 default):** the current
`cheap-sglang` block has no `--kv-cache-dtype`/`--quantization-param-path`, so it
runs the KV cache at the default fp16-ish dtype - treat these as the *unquantized*
reference, not an 8-bit result. From the live run: `sglang:cache_hit_rate` **0.0**,
`sglang:kv_cache_memory_usage_gb` **1.93** (warm cache resident), `nvidia-smi` **9455
MiB** / 12282 MiB used. Quality gate (sample 154, `--cache-mode both`): S1 studio recall
**51/154** (33%), S2 year match **134/154** (87%), S3 year repeat **0.844** (PASS, thresh
0.8). Determinism held on this fp16 run - SGLang #35938 flags that a *quantized* KV is
where determinism can break, so an fp8 follow-up must re-gate S3.

## The lab's translation for dense vs. hybrid

- **On dense models:** quantize KV (8-bit) > trim context > drop a seat. 8-bit gains
  a real 2x on a 12 GiB card.
- **On LFM2.5-2.6B (hybrid, 8/30 layers):** KV quantization isn't a top lever - the
  order shifts to trim context / drop a seat, since ~53% of cached state is unquantizable
  conv/SSM state.
- **On Qwen3.8-27B (hybrid, 16/64 layers):** KV is still a smaller share than weights.
  Weight quantization (`-ngl` balance) is the primary lever; KV quantization helps
  once context exceeds ~64K. The `--cache-type-k q8_0 --cache-type-v q4_0` combo is
  recommended for its quality/VRAM tradeoff without compromising passkey accuracy.
- Squeeze order on a fixed 12 GiB card (dense models): quantize KV (8-bit) > trim
  context > drop a seat.
- Full cache-model context for each engine: [llama.cpp](nn-llamacpp-caching.md),
  [vLLM](nn-vLLM-caching.md), [SGLang](nn-SGLang-caching.md).

### LFM2.5-2.6B specifics: does Q8/FP8 KV actually work?

Don't assume the model is KV-quant optimized just because the engines can do it. Our
LFM2.5-2.6B is **not** - all official quantization is weight-side (Q8_0/W8A16 GGUF
families and the QAD-Q4_0 quantization-aware-distillation checkpoint); the model card,
GGUF repo README, Liquid blog, and the LFM2 technical report
([arXiv:2511.23404](https://arxiv.org/abs/2511.23404)) never mention KV-cache
quantization, and the LEAP configs ship weight-quant only. What "works" here is
engine-level support, with per-engine caveats:

- **Architecture split dictates where KV even lives**: 30 layers = 22 `conv` + 8
  full-attention GQA layers (`head_dim` 64, 8 KV heads, 128K ctx) - so KV exists for
  **8 of 30 layers only**; the conv layers keep SSM/conv state instead of K/V.
- **llama.cpp q8_0 works.** Quantized V requires FlashAttention - auto-enabled under
  `--flash-attn auto`, hard error if FA is disabled - and llama.cpp auto-applies a
  Walsh-Hadamard rotation to quantized K/V whenever `head_dim % 64 == 0`
  (`src/llama-kv-cache.cpp`), which LFM's `head_dim` 64 ticks. Block-size check also
  passes (q8_0 block 32 divides 64).
- **vLLM fp8 works on hybrids only with per-layer-type scale calibration** that skips
  the recurrent layers - vLLM issue #52793 explicitly "unblocks" fp8 KV on hybrids.
  Warning sign: issue #52475 (repetition collapse with `turboquant_*` KV) happened on
  a *different* hybrid, so calibrate, don't just flip the flag.
- **SGLang fp8 needs the scale-path JSON** (see the SGLang sample above): without
  `--quantization-param-path`, scales default to `1.0` and `server_args` warns this
  may cause accuracy issues. SGLang issue #35938 additionally notes quantized KV can
  break deterministic inference.
- **Quantization ceiling - about half the cache is out of reach, so fp16 is the
  default**: `--kv-cache-dtype` covers only the K+V buffers (measured 2.04 GiB). The
  1.84 GiB **conv_state is a separate buffer** and is NOT covered - only
  `--mamba-ssm-dtype` (SSM state) moves with this flag's siblings. So ~53% of cached
  state is quantizable: at 8-bit you save **~1 GiB, not 2x everything**, and the
  unquantized conv/SSM buffers stay fp16 regardless. Given that ~half the cache is
  untouchable, the in-repo engines stay at fp16 KV.

**Qwen3.8 comparison:** Unlike LFM's conv/SSM state, Qwen3.8's DeltaNet recurrent
state is tiny (~250 MB/slot fixed) and separate from the KV cache. So the "ceiling"
problem is far less severe - almost all of the K+V is quantizable. This makes KV
quantization more effective on Qwen3.8 than on LFM2.5, despite both being hybrids.

## Sources

- llama.cpp server manual, `-ctk` / `-ctv` flags: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- vLLM KV-cache dtype args: https://github.com/vllm-project/vllm/blob/main/vllm/engine/arg_utils.py
- SGLang `--kv-cache-dtype` args + `--quantization-param-path` help text: https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/server_args.py
- Measured baselines: docker/README.md (this repo)
- LFM2 model card (weights, no KV-quant):
  https://huggingface.co/LiquidAI/LFM2.5-2.6B
- Official GGUF repo (weight-quant only): https://huggingface.co/LiquidAI/LFM2.5-2.6B-GGUF
- LFM2 technical report: https://arxiv.org/abs/2511.23404
- llama.cpp quantized-V/FV requirements (`src/llama-context.cpp`) and Hadamard
  rotation (`src/llama-kv-cache.cpp`): https://github.com/ggml-org/llama.cpp
- vLLM hybrid fp8 KV: issue #52793; repetition-collapse warning on a hybrid: https://github.com/vllm-project/vllm/issues/52475
- SGLang quantized-KV determinism issue #35938: https://github.com/sgl-project/sglang/issues/35938
- KIVI and KVQuant papers - further reading on per-channel / per-head KV quantization design