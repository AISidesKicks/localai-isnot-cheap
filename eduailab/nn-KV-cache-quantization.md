# KV cache quantization — squeezing 2-4x more context out of the same VRAM

The KV cache quietly eats most of the VRAM in a long-context lab. In docker/README.md
you can feel it in the measured baselines on our RTX 4070 (12 GiB): llama.cpp KV lands
at **1.95 GiB** (of 5.0 GiB total), vLLM at **6.62 GiB** (of 11.4 GiB), SGLang at
**2.04 GiB** K+V plus **1.84 GiB** Mamba conv_state (of 9.37 GiB). On this little SLM
footprint the KV cache is already the single biggest resident on the card — so its
quantization is the cheapest lever we can pull for more context or more parallel seats.

## Why quantize the KV cache at all — the memory math

Every decoded token appends a K and a V vector **per layer** into the cache. Stored
plain, that is **2 bytes per value** (`fp16`). Cut the value to 1 byte (`fp8` / `q8_0`)
and the same VRAM holds **2x the tokens**; cut it to 4 bits (`fp4` / `q4_0`, 0.5 bytes)
and it holds **4x**. Nothing else in the stack scales this cheaply:

| KV value size | Bytes/value | Tokens in the same KV budget |
|---|---|---|
| `fp16` (default) | 2 | 1x |
| `fp8` / `q8_0` | 1 | 2x |
| `fp4` / `q4_0` | 0.5 | 4x |

For our 128K-context seats that's the difference between "half the card is cache" and
"the cache barely matters anymore".

## Quality physics — the reason it is not free

The 8-bit boundary is the sweet spot and 4-bit is where it starts to hurt:

- **8-bit (q8_0, fp8_e4m3, fp8_e5m2) is near-lossless** for most models and workloads.
  Prefill/decode quality and passkey-style tests hold up in practice.
- **4-bit (q4_0) genuinely degrades output**, and it gets worse exactly in the
  situations our lab runs into:
  - **Long contexts** — quantization error accumulates with context length; every
    token reads K/V values that are a little fuzzier, and the fuzz compounds.
  - **Attention-heavy prompts** — more tokens read the cache, so more of the error
    reaches the output.
  - **Small models** — a 2.6B SLM has less internal redundancy to paper over the
    error than a 70B model. What flies on a datacenter model can visibly roll a tiny
    edge model.
- **Scaling factors are the real knob.** Storing 8-bit values is only half the story;
  you also need scales to map back to the fp16 range:
  - **Per-tensor vs per-head scaling** changes accuracy materially — per-head (what
    llama.cpp's fused quant kernels use) tracks the real per-key/per-value range,
    per-tensor averages it out and loses precision.
  - **The default-scale = 1.0 pitfall** — if the engine falls back to scale `1.0`
    (identity) instead of learned/calibrated scales, the "quantized" cache is
    effectively truncated fp16: modules that rely on the caller passing the scales
    silently lose precision. When comparing numbers, always check that scales are
    actually in play, not just that the dtype flag says "8-bit".

Further reading (the actual research lineage): **KIVI** and **KVQuant** are the two
papers this whole area grew out of — both explain the per-channel/per-head scaling
designs and why 2-bit/4-bit KV cache only works when the scales are handled right.

## Engine samples — exact flags + what to measure

All three engines can store KV at lower precision today. Flags below are manual
reconfig labs; `cheap-vllm` in this repo now ships `fp8_per_token_head` live
(see the vLLM sample). Measure the cache with the engine's own metrics or
`nvidia-smi`.

### llama.cpp

```sh
# 2x tokens in the same KV budget:
-ctk q8_0 -ctv q8_0        # K and V quantized, per-block scales
# 4x tokens, watch quality on long contexts:
-ctk q4_0 -ctv q4_0

# swaps the default -ctk f16 -ctv f16
```

Measure: `nvidia-smi` VRAM before/after, or VictoriaMetrics `llamacpp:prompt_tokens_seconds`
(prefill throughput rises when the KV fits tighter). Baselines: KV 1.95 GiB of 5.0 GiB
at `-ctk f16 -ctv f16` on LFM2.5-2.6B-Q8_0, 128K context.

### vLLM

```sh
--kv-cache-dtype fp8_per_token_head  # live in-repo: scale-free fp8 (default for cheap-vllm)
--kv-cache-dtype fp8_e4m3            # 8-bit, E4M3 (static scales — hybrid trap)
--kv-cache-dtype fp8_e5m2            # 8-bit, E5M2 (static scales — hybrid trap)
--kv-cache-dtype-skip-layers 4       # keep the first N layers fp16 — they see every token
```

The repo's `cheap-vllm` container runs `fp8_per_token_head` — vLLM's scale-free
8-bit. It needs no `kv_scales.json` and no `--calculate-kv-scales` pass: dynamic
per-token-head scales get computed at runtime (the validator logs *"Dynamic
per-token-head scales will be computed at runtime"*). That sidesteps the exact
hybrid trap — `fp8_e4m3`/`fp8_e5m2` carry static scales that silently fall back
to `1.0` when the calibration pass is disabled on recurrent layers (vLLM
#52793, #52475). Verified live: the container resolves the dtype and the kernel
reports ~7.16 GiB / ~882k tokens of cache vs 6.62 GiB fp16.

Measure: `vllm:kv_cache_usage_perc` and `vllm:prefix_cache_hits` on `/metrics`, plus the
VRAM baseline in docker/README.md (KV 6.62 GiB of 11.4 GiB at the default fp16).

### SGLang

```sh
--kv-cache-dtype fp8_e4m3                    # 8-bit (also fp8_e5m2)
--quantization-param-path kv_scales.json     # per-layer KV-cache scaling factors
```

SGLang runs a separate **scale path** for the quantized cache — verify the scale
tensors are present, otherwise the dtype flag is a no-op. Point the path at a JSON of
per-layer KV-cache scaling factors (`kv_scales.json` above); without it SGLang
defaults those scales to `1.0`, which `server_args` warns "may cause accuracy issues".
Measure: `sglang:kv_cache_memory_usage_gb` and `sglang:cache_hit_rate`. Baselines:
2.04 GiB K+V + 1.84 GiB Mamba conv_state.
Note the Mamba **conv_state and SSM state are *not* covered by `--kv-cache-dtype`** —
they live in their own buffers (`--mamba-ssm-dtype` controls the SSM state) — so a
hybrid model keeps a chunk of cache in high precision no matter what you ask for.

**Baseline snapshot (cinematic-01, non-quantized fp16 default):** the current
`cheap-sglang` block has no `--kv-cache-dtype`/`--quantization-param-path`, so it
runs the KV cache at the default fp16-ish dtype — treat these as the *unquantized*
reference, not an 8-bit result. From the live run: `sglang:cache_hit_rate` **0.0**,
`sglang:kv_cache_memory_usage_gb` **1.93** (warm cache resident), `nvidia-smi` **9455
MiB** / 12282 MiB used. Quality gate (sample 154, `--cache-mode both`): S1 studio recall
**51/154** (33%), S2 year match **134/154** (87%), S3 year repeat **0.844** (PASS, thresh
0.8). Determinism held on this fp16 run — SGLang #35938 flags that a *quantized* KV is
where determinism can break, so an fp8 follow-up must re-gate S3.

## The lab's translation

- Our LFM2.5-2.6B is a small hybrid — the perfect worst case for 4-bit. If the 8-bit
  caches pass your QA, stay there and pocket the 2x.
- Squeeze order on a fixed 12 GiB card: quantize KV (8-bit) > trim context > drop a seat.
  Quantizing KV first means the other two knobs get easier.
- Full cache-model context for each engine: [llama.cpp](nn-llamacpp-caching.md),
  [vLLM](nn-vLLM-caching.md), [SGLang](nn-SGLang-caching.md).

### LFM2.5-2.6B specifics: does Q8/FP8 KV actually work?

Don't assume the model is KV-quant optimized just because the engines can do it. Our
LFM2.5-2.6B is **not** — all official quantization is weight-side (Q8_0/W8A16 GGUF
families and the QAD-Q4_0 quantization-aware-distillation checkpoint); the model card,
GGUF repo README, Liquid blog, and the LFM2 technical report
([arXiv:2511.23404](https://arxiv.org/abs/2511.23404)) never mention KV-cache
quantization, and the LEAP configs ship weight-quant only. What "works" here is
engine-level support, with per-engine caveats:

- **Architecture split dictates where KV even lives**: 30 layers = 22 `conv` + 8
  full-attention GQA layers (`head_dim` 64, 8 KV heads, 128K ctx) — so KV exists for
  **8 of 30 layers only**; the conv layers keep SSM/conv state instead of K/V.
- **llama.cpp q8_0 works.** Quantized V requires FlashAttention — auto-enabled under
  `--flash-attn auto`, hard error if FA is disabled — and llama.cpp auto-applies a
  Walsh-Hadamard rotation to quantized K/V whenever `head_dim % 64 == 0`
  (`src/llama-kv-cache.cpp`), which LFM's `head_dim` 64 ticks. Block-size check also
  passes (q8_0 block 32 divides 64).
- **vLLM fp8 works on hybrids only with per-layer-type scale calibration** that skips
  the recurrent layers — vLLM issue #52793 explicitly "unblocks" fp8 KV on hybrids.
  Warning sign: issue #52475 (repetition collapse with `turboquant_*` KV) happened on
  a *different* hybrid, so calibrate, don't just flip the flag.
- **SGLang fp8 needs the scale-path JSON** (see the SGLang sample above): without
  `--quantization-param-path`, scales default to `1.0` and `server_args` warns this
  may cause accuracy issues. SGLang issue #35938 additionally notes quantized KV can
  break deterministic inference.
- **Quantization ceiling — about half the cache is out of reach**: `--kv-cache-dtype`
  covers only the K+V buffers (measured 2.04 GiB). The 1.84 GiB **conv_state is a
  separate buffer** and is NOT covered — only `--mamba-ssm-dtype` (SSM state) moves
  with this flag's siblings. So ~53% of cached state is quantizable: at 8-bit you save
  **~1 GiB, not 2x everything**, and the unquantized conv/SSM buffers stay fp16
  regardless.

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
- KIVI and KVQuant papers — further reading on per-channel / per-head KV quantization design