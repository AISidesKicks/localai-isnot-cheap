# MoE Expert Streaming & Offloading Landscape

Mixture-of-Experts (MoE) LLMs offer superior model quality at lower FLOPs per token, but their sheer size (often hundreds of billions of parameters) makes them impossible to fit on a single consumer GPU. A growing ecosystem of research projects tackles this via **expert offloading** — dynamically moving expert weights or activations between GPU, CPU RAM, and flash storage at inference time. This document surveys 12 projects spanning systems research (SOSP, EuroSys, ICLR) and production-quality tooling, sorted by community adoption.

## Comparison Tables

### Core Offloading Engines

| Feature | KTransformers | FreeToken | mixtral-offloading | BigMoeOnEdge |
|---|---|---|---|---|
| **Stars** | 19,351 | 10,278 | 2,333 | 514 |
| **Language** | Python/C++/CUDA | Python/CUDA | Python | C++ |
| **Target HW** | Consumer GPU + CPU | Edge (laptop/workstation) | Consumer GPU + Colab | Mobile flash storage |
| **Core Innovation** | CPU-GPU hybrid with AMX/AVX kernels | Bandwidth-adaptive CPU-GPU co-execution | Leverage MoE sparsity for offloading | Flash as memory hierarchy tier |
| **License** | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 |
| **Paper** | SOSP 2025 | arXiv:2608.16157 | arXiv:2312.17238 | — |

| Feature | MoE-Infinity | Fiddler | tinyserve | Sluice | ExpertFlow |
|---|---|---|---|---|---|
| **Stars** | 352 | 267 | 22 | 3 | N/A |
| **Language** | Python | Python | Python | Python | N/A (paper only) |
| **Target HW** | Personal machines | Consumer GPU + CPU | Laptop GPU (8 GB) | vLLM plugin (multi-GPU) | Simulated |
| **Core Innovation** | Sparsity-aware expert cache | Activations → CPU (not weights) | MXFP4 + GGUF zero-dequant | vLLM plugin router-split | Routing predictor + token scheduling |
| **License** | Apache-2.0 | Apache-2.0 | MIT | Apache-2.0 | N/A |
| **Paper** | arXiv:2401.14361 | ICLR 2025 | — | — | DAC 2026 |

### Related Works

| Feature | ProMoE | FineMoE |
|---|---|---|
| **Stars** | 51 | 16 |
| **Language** | Python | Python |
| **Domain** | Diffusion Transformers (image gen) | LLM MoE offloading |
| **Core Innovation** | Explicit routing guidance for DiT experts | Fine-grained expert selection & prefetch |
| **License** | MIT | Apache-2.0 |
| **Paper** | ICLR 2026 | EuroSys 2026 |

## Offloading Engines

### KTransformers

**GitHub**: [kvcache-ai/ktransformers](https://github.com/kvcache-ai/ktransformers) | **Stars**: 19,351 | **Language**: Python / C++ / CUDA | **License**: Apache-2.0

Places hot (frequently activated) experts on GPU and cold experts on CPU with INT4/INT8 quantization, accelerated by Intel AMX/AVX kernels and NUMA-aware memory management. Achieves 3–28× speedup for DeepSeek-V3/R1 on a single 24 GB VRAM GPU.

**Paper**: SOSP 2025 — doi:10.1145/3731569.3764843

### FreeToken

**GitHub**: [FlashML-org/FreeToken](https://github.com/FlashML-org/FreeToken) | **Stars**: 10,278 | **Language**: Python / CUDA | **License**: Apache-2.0

Treats a personal machine as a unified elastic inference platform via bandwidth-adaptive CPU-GPU co-execution (the `q*` policy). Runs models from 35B on a laptop up to 753B (GLM-5.2) on a single workstation GPU. Deeply inspired by [mini-sglang](https://github.com/sgl-project/mini-sglang).

**Paper**: arXiv:2608.16157

**Talk**: [New Local AI Inference Engine You Should Be Using in 2027? (FreeToken)](https://www.youtube.com/watch?v=ZvZM4qnUVGI)

### mixtral-offloading

**GitHub**: [dvmazur/mixtral-offloading](https://github.com/dvmazur/mixtral-offloading) | **Stars**: 2,333 | **Language**: Python | **License**: MIT

Builds on parameter offloading algorithms, exploiting the sparse-activation property of MoE — only a fraction of expert layers are active per token. Runs Mixtral-8×7B with mixed quantization on consumer desktop hardware and free-tier Google Colab.

**Paper**: arXiv:2312.17238

### BigMoeOnEdge

**GitHub**: [Helldez/BigMoeOnEdge](https://github.com/Helldez/BigMoeOnEdge) | **Stars**: 514 | **Language**: C++ | **License**: Apache-2.0

On-demand MoE expert streaming from flash storage (UFS/NVMe). Only the small always-needed part of an MoE model is kept resident; per-token expert weights are read directly from flash via an LRU cache with I/O-compute overlap. Runs models several times larger than device RAM — e.g., DeepSeek V4 Flash 284B (~91 GB) on a 12 GB phone at ~0.94 tok/s. Built on llama.cpp with zero modifications.

### MoE-Infinity

**GitHub**: [EfficientMoE/MoE-Infinity](https://github.com/EfficientMoE/MoE-Infinity) | **Stars**: 352 | **Language**: Python | **License**: Apache-2.0

Exploits high activation sparsity in single-user, batch-1 settings: only a small set of experts are frequently reused during decode-phase token generation. Builds a sparsity-aware expert cache that traces these patterns and intelligently prefetches and replaces cached experts. Delivers 3.1–16.7× per-token latency improvements over vLLM, Ollama, DeepSpeed, and BrainStorm.

**Paper**: arXiv:2401.14361

### Fiddler

**GitHub**: [efeslab/fiddler](https://github.com/efeslab/fiddler) | **Stars**: 267 | **Language**: Python | **License**: Apache-2.0

Inverts the standard offloading approach: keeps expert weights stationary on GPU and moves only activations to CPU for compute in non-expert layers (attention, router, shared experts). Since activations are orders of magnitude smaller than weights, PCIe traffic is drastically reduced. Introduces an optimal execution strategy planner that decides which layers run on which device given GPU memory budget. Speedups: 1.26× (single batch), 1.30× (long prefill), 11.57× (beam search).

**Paper**: arXiv:2402.07033 — ICLR 2025

### tinyserve

**GitHub**: [e1n00r/tinyserve](https://github.com/e1n00r/tinyserve) | **Stars**: 22 | **Language**: Python | **License**: MIT

Achieves 30 tok/s decode for a 20B MoE model on an 8 GB laptop GPU (RTX PRO 2000) with flat throughput to 32K context via StreamingLLM. Uses native MXFP4 and GGUF formats via ggml CUDA kernels — zero dequantization. Supports GPT-OSS-20B/120B, Qwen 3.5 MoE 30B-A3B, DeepSeek-V3/R1.

### Sluice

**GitHub**: [Etelis/sluice](https://github.com/Etelis/sluice) | **Stars**: 3 | **Language**: Python | **License**: Apache-2.0

A plugin for vLLM v0.23 (not a fork) that keeps MoE expert weights in host RAM and streams only router-selected experts into a small per-layer GPU slot cache. Supports CUDA graphs via `SLUICE_ROUTER_SPLIT`. DeepSeek-V2-Lite achieves 147 tok/s at c=1 (55% of vanilla) and 1063 tok/s at c=8 (beats vanilla by +8%). Runs checkpoints up to ~805 GiB on 4×H100 where stock vLLM and SGLang OOM.

### ExpertFlow

**Paper**: arXiv:2410.17954 | **Venue**: DAC 2026 | **Code**: No public repository found

Proposes a routing predictor that anticipates future expert selection and a token scheduling mechanism to overlap expert loading with computation. Paper-only at this time — no public codebase surfaced.

## Related Works

### ProMoE

**GitHub**: [ali-vilab/ProMoE](https://github.com/ali-vilab/ProMoE) | **Stars**: 51 | **Language**: Python | **License**: MIT

**Not an LLM offloading project.** ProMoE addresses MoE routing in Diffusion Transformers (DiTs) for image generation. It proposes a two-step router with explicit routing guidance to improve expert specialization in MoE layers of diffusion models trained on ImageNet. Included here for completeness given the shared "MoE routing" vocabulary.

**Paper**: arXiv:2510.24711 — ICLR 2026

### FineMoE

**GitHub**: [IntelliSys-Lab/FineMoE-EuroSys26](https://github.com/IntelliSys-Lab/FineMoE-EuroSys26) | **Stars**: 16 | **Language**: Python | **License**: Apache-2.0

A fine-grained expert offloading system that extracts expert selection patterns and semantic hints from input prompts to guide prefetching, caching, and offloading. Prototyped on HuggingFace Transformers, deployed on a six-GPU testbed. Claims 47% lower inference latency and 39% higher expert hit rate vs. SOTA. EuroSys 2026 — details still emerging.

**Paper**: arXiv:2502.05370

## Key Takeaways

- **KTransformers and FreeToken dominate adoption** (19.4k + 10.3k stars) — both are CPU-GPU hybrid systems targeting consumer hardware, but KTransformers focuses on hot/cold expert placement with CPU-side quantization kernels, while FreeToken generalizes to arbitrary heterogeneous edge topologies.
- **Fiddler's activation-offload approach is unique** — moving activations (not weights) to CPU avoids the PCIe bottleneck that limits all weight-offloading systems.
- **There is no single dominant paradigm** — approaches range from flash-storage streaming (BigMoeOnEdge) to sparsity-aware caching (MoE-Infinity) to router-split plugins (Sluice) to paper-only proposals (ExpertFlow). The field is actively evolving across multiple venues (SOSP, ICLR, EuroSys, DAC).
- **Production readiness varies widely** — KTransformers, FreeToken, and mixtral-offloading have mature codebases; FineMoE and ExpertFlow are early-stage or paper-only.
