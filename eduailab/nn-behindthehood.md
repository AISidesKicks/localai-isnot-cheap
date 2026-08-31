# Educational Mini Nano LLM Engine derivates

## mini-SGLang and nano-vLLM
Most popular are [Mini-SGLang](https://github.com/sgl-project/mini-sglang) and [Nano-vLLM](https://github.com/GeeeekExplorer/nano-vllm). These are two popular, minimalist, and highly optimized educational frameworks designed for running and understanding Large Language Model (LLM) inference.
Both projects were created as lightweight "distillations" of massive production systems (SGLang and vLLM). They aim to show developers and researchers exactly how advanced LLM engines work under the hood without forcing them to wade through hundreds of thousands of lines of complex production code.
Here is a direct comparison of the two systems:

### Comparison

| Feature / Project | Mini-SGLang | Nano-vLLM |
|---|---|---|
| Origin | Derived from the production SGLang framework. | Derived from vLLM (built by a DeepSeek engineer). |
| Code Size | Roughly 5,000 lines of clean Python. | Extremely compact, roughly 1,200 lines of code. |
| Core Advantage | Peak performance via Overlap Scheduling (hiding CPU/GPU overhead). | Maximum simplicity, allowing line-by-line debugging in Eager mode. |
| Advanced Features | Radix Cache (prefix sharing), Chunked Prefill, Tensor Parallelism. | Prefix Cache, CUDA graphs, Torch Compile. |
| Performance | Matches full SGLang throughput on NVIDIA Hopper architectures. | Outperforms stock vLLM in specific low-overhead or hardware-constrained setups. |

### Key Takeaways:

* Educational Value: Both are perfect tools for learning how advanced memory architectures like PagedAttention operate, and how engines manage the transition between the prefill (compute-bound) and decode (memory-bound) phases.
* Interfaces: Mini-SGLang provides a fully functional OpenAI-compatible API server as well as an interactive shell mode.
* Hardware Accessibility: Because they lack bloated enterprise abstractions, they are highly efficient and easy to deploy on consumer hardware (like a single RTX 4070/4090).

To help you choose the right path, let me know:

* Are you looking into these for educational/research purposes, or to benchmark a specific model?
* What hardware (GPU) do you have available for testing?
* Would you like a step-by-step guide to install and run a quick demo script?

## nano-vLLM

Nano-vLLM is a highly popular, minimal (~1,200 lines of Python) education-focused replication of the vLLM engine. It helps ML engineers understand KV caching, PagedAttention, and CUDA graphs without digging through production-bloated codebases.

Here is a structured list of essential repositories, deep-dives, and community-driven resources for nano-vLLM: [1] 

### Core Codebases
* 
* [GeeeekExplorer / nano-vllm GitHub Repository](https://github.com/GeeeekExplorer/nano-vllm): The definitive main implementation of the project. It includes tensor parallelism, prefix caching, and supports Qwen3-0.6B benchmarks right out of the box. [5] 
* [ovshake / nano-vllm (with Tutorial Mode)](https://github.com/ovshake/nano-vllm/): An educational variation that includes an interactive command-line step-by-step tour (--tutorial) featuring built-in architecture quizzes. [6] 
* [Wenyueh / MinivLLM](https://github.com/Wenyueh/MinivLLM): A fork built directly on top of nano-vLLM that provides a completely self-contained implementation of FlashAttention and PagedAttention. [7] 
* 

## Hugging Face Technical Articles

* 
* [Introduction to nano-vLLM](https://huggingface.co/blog/zamal/introduction-to-nano-vllm): A thorough walkthrough hosted on Hugging Face written by community members detailing prompt tokenization, Triton kernels, and memory formatting. [4, 8] 
* [Nano-vLLM meets Inference Endpoints](https://huggingface.co/blog/angt/nano-vllm-meets-inference-endpoints): A deployment-focused manual outlining how to rewrite the engine class into an asynchronous Worker thread to seamlessly host nano-vLLM on official Hugging Face cloud endpoints. [9, 10] 
* 

## Engineering Deep-Dives & Series

* 
* [Inside the Inference Engine Series (Neutree AI) - part1](https://neutree.ai/blog/nano-vllm-part-1): A comprehensive engineering analysis that breaks down how the engine orchestrates its runtime, batches sequences, and handles variable tokens.
* [Inside the Inference Engine Series (Neutree AI - part2)](https://neutree.ai/blog/nano-vllm-part-2): A comprehensive engineering analysis that breaks down how the engine orchestrates its runtime, batches sequences, and handles variable tokens.
lock tables.
* [Build-from-Scratch Architectural Labs (HackMD)](https://hackmd.io/9Ivogn3dRwm3WgA4Kl3fJQ): A technical blueprint mapping out the interaction loops between the Central Scheduler, the Paged Memory Manager, and the GPU Sampler.
* [The 1,200-Line Inference Engine Breakdown (Morph Labs)](https://www.morphllm.com/nano-vllm): A granular structural map explaining the 4 distinct operational layers (llm_engine.py, model_runner.py, scheduler.py, and block_manager.py).
*

## Mini-SGLang

Mini-SGLang is a highly optimized, lightweight educational distillation of the massive SGLang engine. Spanning roughly 5,000 lines of Python code, it abstracts away production bloat while preserving the core algorithms that make SGLang state-of-the-art—namely Radix Cache, Overlap Scheduling, Chunked Prefill, and Tensor Parallelism. [1, 2, 3, 4] 
Here is a structured directory of core codebases, official platform articles, and architectural series for mini-sglang:

## Core Codebases

* 
* [sgl-project / mini-sglang GitHub Repository](https://github.com/sgl-project/mini-sglang): The official project repository hosted by LMSYS. It serves as a fully type-annotated, weekend-readable reference engine that boots an OpenAI-compatible API server right out of the box. [1, 2, 5, 6] 
* [yottalabsai / mini-sglang-neuron](https://github.com/yottalabsai/mini-sglang-neuron): A community fork that adapts mini-sglang's ultra-clean scheduling and architecture to an XLA-oriented runtime, custom-tailored for AWS Trainium and Inferentia chips. [7] 
* 

## Hugging Face & Launch Announcements

* 
* [Transformers Backend Integration in SGLang](https://huggingface.co/blog/transformers-backend-sglang): The primary Hugging Face technical article introducing SGLang's universal fallback architecture. It outlines the structural design patterns that inspired the decoupled worker layout used in mini-sglang. [8, 9] 
* [LMSYS Mini-SGLang Official Announcement](https://www.lmsys.org/blog/2025-12-17-minisgl/): The launch post detailing why the engine was built. It outlines how it serves as a lightweight research sandbox for testing standalone TVM FFI bindings, FlashAttention-3 kernels, and custom CUDA modifications without breaking system invariants. [3, 10] 
* 

## Engineering Deep-Dives & Series

* 
* [Mini-SGLang Mintlify Documentation Series](https://sgl-project-mini-sglang.mintlify.app/introduction): The dedicated, multi-chapter reference manual covering the explicit execution lifecycle of user requests as they pass through ZeroMQ (ZMQ) control layers and NCCL GPU communication lines.
* [LocalLLaMA Architecture Deep Dive](https://www.reddit.com/r/LocalLLaMA/comments/1pp4ax0/minisglang_released_learn_how_llm_inference/): A community technical breakdown tailored for systems engineers. It analyzes how the project manages its internal tokenization loops, custom batching queues, and KV cache memory boundaries.
* Mini-SGLang Structural Maps [tructures.md](https://github.com/sgl-project/mini-sglang/blob/main/docs/structures.md) A granular code breakdown within the repository mapping out the individual roles of the four core structural processes: the API Server, Tokenizer Worker, Detokenizer Worker, and the multi-GPU Scheduler Worker.
* 
