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
reconfig labs (no compose changes in this repo yet); measure the cache with the
engine's own metrics or `nvidia-smi`.

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
--kv-cache-dtype fp8_e4m3       # 8-bit, E4M3 (more precision, fewer range than E5M2)
--kv-cache-dtype fp8_e5m2       # 8-bit, E5M2 (more range, less precision)
--kv-cache-dtype-skip-layers 4  # keep the first N layers fp16 — they see every token
```

Measure: `vllm:kv_cache_usage_perc` and `vllm:prefix_cache_hits` on `/metrics`, plus the
VRAM baseline in docker/README.md (KV 6.62 GiB of 11.4 GiB at the default fp16).

### SGLang

```sh
--kv-cache-dtype fp8_e4m3       # 8-bit (also fp8_e5m2)
```

SGLang also runs a separate **scale path** for the quantized cache — verify the scale
tensors are present, otherwise the dtype flag is a no-op. Measure: `sglang:kv_cache_memory_usage_gb`
and `sglang:cache_hit_rate`. Baselines: 2.04 GiB K+V + 1.84 GiB Mamba conv_state.
Note the Mamba **conv_state and SSM state are *not* covered by `--kv-cache-dtype`** —
they live in their own buffers (`--mamba-ssm-dtype` controls the SSM state) — so a
hybrid model keeps a chunk of cache in high precision no matter what you ask for.

## The lab's translation

- Our LFM2.5-2.6B is a small hybrid — the perfect worst case for 4-bit. If the 8-bit
  caches pass your QA, stay there and pocket the 2x.
- Squeeze order on a fixed 12 GiB card: quantize KV (8-bit) > trim context > drop a seat.
  Quantizing KV first means the other two knobs get easier.
- Full cache-model context for each engine: [llama.cpp](nn-llamacpp-caching.md),
  [vLLM](nn-vLLM-caching.md), [SGLang](nn-SGLang-caching.md).

## Sources

- llama.cpp server manual, `-ctk` / `-ctv` flags: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- vLLM KV-cache dtype args: https://github.com/vllm-project/vllm/blob/main/vllm/engine/arg_utils.py
- SGLang `--kv-cache-dtype` args: https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/server_args.py
- Measured baselines: docker/README.md (this repo)
- KIVI and KVQuant papers — further reading on per-channel / per-head KV quantization design