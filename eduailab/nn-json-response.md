# JSON / structured output: llama.cpp vs vLLM vs SGLang (the 2.6B, guided vs unguided)

Every cinematic-01 call goes through `llm.chat()` with a Pydantic `response_format`
(`StudioList` / `FilmList` / `YearAnswer`) — this was the llama.cpp-optimized
assumption in `design.md`: "The 2.6B camel is comfortable emitting small JSON." That
assumption holds for the Q8 GGUF engine and falls apart for vLLM. This note is the
field record of exactly how the two engines honor (and don't honor) the schema, why
the `guided` toggle and `query_schema`'s auto-disable landed, and the score deltas the
structured-output gap cost us. All numbers come from committed run artifacts, not a
fresh re-run.

## 1. llama.cpp (Q8_0, guided)

llama-server honors the schema via **guided decoding**: `response_format` + the
`enable_json_schema_validation=True` flag turn generation into a grammar-constrained
decode, so the output is **strict schema-compliant JSON** — no Markdown fences, no
prose around it. The parse hits the schema on the first pass, the answer lands in
`content` fast, and each prompt is cheap to re-ask because the KV cache absorbs the
shared prefix.

Baseline (run-211110-local-gguf, Q8_0):

| Scenario | Metric | Score |
|---|---|---|
| 1 Studio recall | manual exact match | **49/154** |
| 2 Year match (±2) | abs diff <= 2 | **126/154** |
| 3 Year repeat | deepeval.ExactMatchMetric (thr 0.8) | **0.805 PASS** |

KV reuse is visible per request: llama.cpp reports `timings.cache_n` (prompt tokens
replayed from cache) inside chat-completion responses, so a re-prompt with a shared
prefix shows `cache_n` climbing while `prompt_n` stays flat.

## 2. vLLM (W8A16 AutoRound, guided): empty completions

Flip the same `response_format` + `enable_json_schema_validation=True` onto the vLLM
engine and the guided/output-constraint path reliably returns **empty completions** —
`choices[0].message.content` is `''` with no content at all. The AutoRound quant +
guided decode combination just doesn't emit tokens. This is the exact symptom we hit,
and it's reproducible, not a fluke.

This motivated two changes:

- `llm.chat()` gained a `guided=False` toggle. `guided` gates both `response_format`
  and `enable_json_schema_validation`.
- `test.py`'s `query_schema()` auto-disables it: `guided = "vllm" not in llm.MODEL`,
  so the gate only forces strict guided decoding when the alias is NOT vLLM, and a
  parse-then-retry loop covers the unguided case instead.

## 3. vLLM (unguided): fences + shape inference

Drop `guided` entirely and vLLM does produce content — but it stops respecting the
schema and **wraps the JSON in Markdown fences** (```` ```json … ``` ````), and it
**infers the JSON key shape from the prompt alone** instead of from the schema. So a
prompt asking for `{"studios": ["Studio Name"]}` can come back as a flat
`{"studio": "…"}` object rather than the expected `{"studios": [ … ]}` list, and
validation fails.

Two fixes landed in `test.py`:

- `parse_model()` strips a fenced block before calling `schema.model_validate_json`.
- The scenario prompts now embed the exact JSON shape (`{"studios": ["Studio Name"]}`,
  `{"title": "Title", "year": 1995}`) so the unguided engine at least picks the right
  key shape.

## 4. Score deltas as evidence

| Scenario | llama.cpp Q8_0 GGUF | vLLM W8A16 | SGLang W8A16 | Notes |
|---|---|---|---|---|
| 1 Studio recall | 49/154 (0.318) | 51/154 (0.331) | 51/154 (0.331) | ≈ parity |
| 2 Year match (±2) | 126/154 (0.818) | 134/154 (0.870) | 134/154 (0.870) | vLLM/SGLang ahead |
| 3 Year repeat | 0.805 PASS | **0.623 FAIL** | **0.844 PASS** | guided clean; unguided regresses |

### SGLang (W8A16, guided) — the third data point

SGLang is a *third* engine riding the same `guided` toggle, and it behaves like llama.cpp,
not vLLM. Because `query_schema` gates on `guided = "vllm" not in llm.MODEL`, the SGLang
alias (`local-sglang`) is **not** vLLM, so it keeps strict guided decoding
(`response_format` + `enable_json_schema_validation=True`). The result: clean schema JSON,
S3 clears the bar at **0.844 PASS** — the exact scenario vLLM dropped to 0.623. That
confirms the story wasn't "the model can't do JSON," it is specifically the vLLM quantization
path that breaks guided decode.

The interesting one is S3 (exact year repeat, `deepeval.ExactMatchMetric`): it's the
strictest scenario, scoring exact `"year": N` fields. With llama.cpp's guided decode
those come back as clean integers and it clears the 0.8 bar. vLLM's unguided output —
even after fence-stripping — drifts toward wrapped/prose-y text instead of a strict
numeric year field, which drops exact-match from 0.805 down to 0.623. SGLang restores
the guided path (0.844 PASS), proving the regression is vLLM's, not the model's. That's
the whole story in one row: **the structured-output gap, not the model, is what cost the
vLLM S3 pass.**

## 5. Cross-ref: the cache demos

The vLLM run (`--cache-mode both`) ties structured output back to caching. On the
engine side, vLLM 0.27.1 does **not** return `usage.prompt_tokens_details.cached_tokens`
first-class (it's `null`), so the demo reads `/metrics` deltas instead and the report
shows prefix-cache reuse per mode:

| Mode | vLLM prefix-cache Δ hits | Δ queries |
|---|---|---|
| 1level | 32 | 72 |
| 2level | 16 | 47 |
| no-cache | 0 | 62 |

`1level` proves the engine prefix cache replayed ~32 prompt tokens across the three
`BASE_PROMPT + " - N"` suffixes (shared prefix), while `no-cache` (fully cold prompts)
replayed none.

The SGLang run's cache demo reads **gauges, not counters**: it reports
`sglang:cache_hit_rate` and `sglang:kv_cache_memory_usage_gb` rather than vLLM's
cumulative hit/query deltas. On the baseline run these came back as a 0.0 hit rate
and ~1.93 GB resident KV (the same warm-cache footprint the report shows), so it is a
point-in-time snapshot of the radix tree rather than a per-mode reuse tally — the
`cached_tokens` / `cache_n` replay columns stay unpopulated there (`—`).

The failure mode lands *inside* those numbers: an **empty guided completion is an
ordinary response**, so it gets Redis-cached like any other. A rerun with the same
prompt then replays the stale empty instead of re-asking, poisoning the rerun until
the prompt changes. That's why `query_schema` retries **prepend a reminder** (new
prompt → new cache key) rather than resending the identical text — and why `1level`'s
`cache={"no-cache": True}` bypass is the clean escape hatch: it stops Redis from
serving the poisoned empty so the engine has to actually generate.

### The generate.py hazard (latent, not fixed)

`generate.py`'s `ask_json()` still calls `chat()` with `response_format=schema` and
**no `guided` knob** — so it defaults to `guided=True`. `test.py` was patched,
`generate.py` was not. If anyone regenerates the dataset pointing at `local-vllm`,
every schema call beats on the guided path and lands on the empty-completion branch.
This is a footgun, not a feature — flagged here so a future regen knows to thread
`guided=False` (or wait for the vLLM guided path to be fixed) before rerunning. Not
fixed as part of this docs task by design.

Run artifacts backing this note:

- llama.cpp baseline: `datasets/cinematic-01/runs/run-20260822-211110-local-gguf/`
- vLLM run + cache-demo deltas: `datasets/cinematic-01/runs/run-20260822-223412-local-vllm/`
- SGLang baseline (guided, clean S3): `datasets/cinematic-01/runs/run-20260823-112134-local-sglang/`
- Design rationale: `smoketests/cinematic-01/design.md` (structured output section)

Sibling engine notes: [vLLM caching](nn-vLLM-caching.md),
[llama.cpp caching](nn-llamacpp-caching.md), [SGLang caching](nn-SGLang-caching.md).