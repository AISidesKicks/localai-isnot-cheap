# Docker stack

Full EDU AI LAB stack: LiteLLM gateway, Redis cache, local inference engines
(llama.cpp / vLLM / SGLang), PostgreSQL, and the Lago billing trio.

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- NVIDIA GPU + `nvidia-container-toolkit` for the GPU profiles
  (`--profile vllm`, `--profile llama-cpp`, `--profile sglang`); the core
  stack (gateway, cache, billing, postgres, redis) runs without a GPU
- `docker compose version` to check Compose v2 (no `version:` key needed)

## Setup

1. Copy the environment template:

   ```sh
   cp docker/.env.example docker/.env
   ```

   The stack runs out of the box with defaults; edit keys only if you want
   the external model fallbacks (gpt-4o / claude / deepseek) to work.

2. Download the GGUF checkpoint into `docker/models/` (llama.cpp profile):

   ```sh
   # LiquidAI/LFM2.5-2.6B-GGUF, Q8_0 (2.87 GB)
   huggingface-cli download LiquidAI/LFM2.5-2.6B-GGUF \
     LFM2.5-2.6B-Q8_0.gguf --local-dir docker/models/
   ```

   vLLM and SGLang pull `LiquidAI/LFM2.5-2.6B` from Hugging Face on first
   start and cache it under `docker/models/hf-cache` (gitignored).

## Run

Core stack (gateway + cache + billing + postgres + redis, no engines):

```sh
docker compose -f docker/docker-compose.yml up -d
```

With a local inference engine (pick one profile):

```sh
docker compose -f docker/docker-compose.yml --profile llama-cpp up -d
docker compose -f docker/docker-compose.yml --profile vllm up -d
docker compose -f docker/docker-compose.yml --profile sglang up -d
```

Or set `INFERENCE_PROFILE` in `docker/.env` and use the environment-driven
`COMPOSE_PROFILES` mechanism:

```sh
# INFERENCE_PROFILE=llama-cpp | vllm | sglang
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

## Port map

| Port | Service        | Notes                          |
|------|----------------|--------------------------------|
| 4000 | LiteLLM        | OpenAI-compatible gateway      |
| 5432 | PostgreSQL     | LiteLLM + Lago databases       |
| 6379 | Redis          | cache (DB 1) + Lago queue (DB 0) |
| 8080 | llama.cpp      | only with `--profile llama-cpp` |
| 8000 | vLLM           | only with `--profile vllm`     |
| 30000| SGLang         | only with `--profile sglang`   |
| 3001 | Lago API       | REST + GraphQL billing API     |
| 8085 | Lago web       | billing dashboard UI           |

## Model aliases in LiteLLM

| Alias        | Backend        | Engine profile |
|--------------|----------------|----------------|
| `local-gguf` | llama.cpp      | `llama-cpp`    |
| `local-llama`| vLLM           | `vllm`         |
| `local-sglang`| SGLang        | `sglang`       |
| `gpt-4o`     | OpenAI         | external       |
| `claude-sonnet-4-20250514` | Anthropic | external |
| `deepseek-chat` | DeepSeek    | external       |
