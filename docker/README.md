# Docker stack

Full EDU AI LAB stack: LiteLLM gateway, Redis cache, local inference engines
(llama.cpp / vLLM / SGLang), PostgreSQL, and the Lago billing trio.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- NVIDIA GPU + `nvidia-container-toolkit` for the GPU profiles
  (`--profile vllm`, `--profile llamacpp`, `--profile sglang`); the core
  stack (gateway, cache, billing, postgres, redis) runs without a GPU
- `docker compose version` to check Compose v2 (no `version:` key needed)

## Setup

1. Copy the environment template:

   ```sh
   cp docker/.env.example docker/.env
   ```

   The stack runs out of the box with defaults; edit keys only if you want
   the external model fallbacks (gpt-4o / claude / deepseek) to work.

2. Download the GGUF checkpoint into `docker/models/Q8/` (llama.cpp profile;
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

## Run

Core stack (gateway + cache + billing + postgres + redis, no engines):

```sh
docker compose -f docker/docker-compose.yml up -d
```

With a local inference engine (pick one profile):

```sh
docker compose -f docker/docker-compose.yml --profile llamacpp up -d
docker compose -f docker/docker-compose.yml --profile vllm up -d
docker compose -f docker/docker-compose.yml --profile sglang up -d
```

Or set `INFERENCE_PROFILE` in `docker/.env` and use the environment-driven
`COMPOSE_PROFILES` mechanism:

```sh
# INFERENCE_PROFILE=llamacpp | vllm | sglang
COMPOSE_PROFILES="$INFERENCE_PROFILE" docker compose -f docker/docker-compose.yml up -d
```

The core stack starts without engines (plain `docker compose up -d`), but when
a profile is active LiteLLM waits for the selected engine's `/health` before
starting — activate two profiles at once and it waits for both.

Stop / tear down:

```sh
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml down -v   # wipes volumes too
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

## Port map

| Port | Service        | Notes                          |
|------|----------------|--------------------------------|
| 4000 | LiteLLM        | OpenAI-compatible gateway      |
| 5432 | PostgreSQL     | LiteLLM + Lago databases       |
| 6379 | Redis          | cache (DB 1) + Lago queue (DB 0) |
| 8080 | llama.cpp      | only with `--profile llamacpp` |
| 8000 | vLLM           | only with `--profile vllm`     |
| 30000| SGLang         | only with `--profile sglang`   |
| 3001 | Lago API       | REST + GraphQL billing API     |
| 8085 | Lago web       | billing dashboard UI           |

## Model aliases in LiteLLM

| Alias        | Backend        | Engine profile |
|--------------|----------------|----------------|
| `local-gguf` | llama.cpp      | `llamacpp`   |
| `local-llama`| vLLM           | `vllm`         |
| `local-sglang`| SGLang        | `sglang`       |
| `gpt-4o`     | OpenAI         | external       |
| `claude-sonnet-4-20250514` | Anthropic | external |
| `deepseek-chat` | DeepSeek    | external       |

All three engines serve the same logical model id `LiquidAI/LFM2.5-2.6B`;
vLLM and SGLang run the AutoRound W8A16 quantization, llama.cpp the Q8_0 GGUF.
