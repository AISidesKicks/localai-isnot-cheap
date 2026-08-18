# EDU AI LAB (localai.isnot.cheap)

Hey!!! Local AI is not CHEAP at ALL! - **Every AI token carries a COST!** 

Running **local AI** is far from free - it simply shifts the invoice from a cloud vendor to your own balance sheet. 

Between high-end GPU based systems, surging electricity and cooling bills, server maintenance, and the specialized engineering talent required to keep inference pipelines optimized, self-hosting carries in real lafe massive capital and operational expenses.

Metering and billing internal teams by the token is essential: it creates accountability against wasteful compute loops and directly amortizes those upfront infrastructure, pipelines, and staffing investments.

## So how to measure and bill AI tokens in small AI Lab? 

This is tricky architectural and engineering challenge with lot of tradeoffs, ideal EDU AI LAB material.

I put here minimal setups from large ones I use in enterprise workshops to demonstrate complexity of Local AI Interference Engendering in practice and role of caching. 

Setup is prepared to be executed as educational lab on gamming PC with 32GB RAM and Nvidia GPU with 12GB VRAM (RTX 4070 in my case).

If you are new to LLM serving aka Interference Engeneering, I am recomnding you to look into EDU sources first ->

## Selecting AI heart for LAB - small, but capable LLM (~3B size will be fine)

Liguid AI relase new [LFM2.5-2.6B: Deploy Agents Everywhere](https://www.liquid.ai/blog/lfm2-5-2-6b) on 4 August 2026!

Small anought LLM with reasoning and tool calling, it's has 128K context so the model can handle the long inputs that agentic workloads - it's hybrid architecture will allow us to utilize full 128K context window.

It has full support in all 3 engines we will use:
 - llama.cpp — GGUF checkpoints for efficient edge inference
 - vLLM — GPU-accelerated serving for production throughput
 - SGLang — GPU-accelerated serving for production throughput
 - MLX — Optimized inference for Apple Silicon
 - ONNX — Cross-platform inference across diverse accelerators

Usefull quatizations:

Full LFM2.5-2.6B model is 5.4 GB in bf16, we can easily run 8bit quantizations:

 - GGUF [Official LiguidAI (8-bit Q8_0 = 2.87 GB)](https://huggingface.co/LiquidAI/LFM2.5-2.6B-GGUF)
 - W8A16 [AutoRound W8A16 (8-bit weights / fp16 activations = 2.9 GB)] (https://huggingface.co/plavno/LFM2.5-2.6B-AutoRound-W8A16)

There are a lot of modified and uncensored variants of LFM2.5-2.6B:

 A Little Uncensored:

  - [LFM2.5-2.6B-Uncensored-GGUF](SC117/LFM2.5-2.6B-Uncensored-GGUF)
  - [LFM2.5-2.6B-Heretic-Abliterated-GGUF](https://huggingface.co/Abiray/LFM2.5-2.6B-Heretic-Abliterated-GGUF)
  - [LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS](https://huggingface.co/KridgeDookie/LFM2.5-2.6B-UNCENSORED-ABLITERATED-PHILADELPHIA-CLASS)

 A Little Specilized:

  - [LFM-2.5-Coder-2.6B GGUF](https://huggingface.co/Schnuckade/LFM-2.5-Coder-2.6B)
  - [LFM2.5-2.6b-fable5-coding-agent](https://huggingface.co/AyoubChLin/lfm2.5-2.6b-fable5-coding-agent) [GGUF](https://huggingface.co/AyoubChLin/LFM2.5-2.6B-fable5-coding-agent-GGUF) 
  - [LFM2.5-2.6B-Terminal-SFT](https://huggingface.co/jacepark12/LFM2.5-2.6B-Terminal-SFT) [GGUF](https://huggingface.co/mradermacher/LFM2.5-2.6B-Terminal-SFT-GGUF) 
  - [LFM2.5-2.6B-CyberSec](https://huggingface.co/reaperdoesntknow/LFM2.5-2.6B-CyberSec) [GGUF](https://huggingface.co/mradermacher/LFM2.5-2.6B-Terminal-SFT-GGUF) 

**PS:** *No vision*, this will limit simulated tests, but multimodal pandora box will stay closed.

I recommend you to familiarize yoursef with LFM 2.5 2.6N model in [LM studio](https://lmstudio.ai/).

## EDU AI LAB "Local AI is not cheap!" OVERVIEW:

```text
==================================================================================================
                 EDU LAB: localai.isnot.cheap  —  "Every AI token carries a COST!"
==================================================================================================

                                  [ Users / Teams / Apps ]
                                             │
                                             │ (1. API Request + Virtual Key)
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     LITELLM (AI GATEWAY)                                       │
│  • Request Interception & Quota Checks                                                         │
│  • Cache Layer: Exact / Semantic Response Matching                                             │
│  • Rate Limiting (TPM/RPM) & Dynamic Cost Calculation                                          │
└───────┬───────────────────────────────────┬────────────────────────────────────┬───────────────┘
        │                                   │                                    │
        │ (2a. Direct Cache Lookup/Store    │ (2b. Cache Miss:                   │ (4. Async Usage
        │      & Auth Key Checks)           │      Inference Request)            │     Events & Costs)
        ▼                                   ▼                                    ▼
┌───────────────────────┐   ┌───────────────────────────────┐   ┌────────────────────────────────┐
│   REDIS (SHARED)      │   │    LOCAL INFERENCE ENGINE     │   │     LAGO (BILLING ENGINE)      │
│                       │   │ [ llama.cpp | vLLM | SGLang ] │   │                                │
│ [DB 1] LiteLLM Cache: │   │ • GPU / CPU Acceleration      │   │ • Virtual Credit Wallets       │
│ • Response Cache Hit  │   │ • Model Prefill & Decode      │   │ • Pricing Rules & Tier Rating  │
│   (Bypasses Engine!)  │   │ • Prefix / KV-Cache Hit       │   │ • Internal Team Chargeback     │
│ • Auth Key Validation │   │   Reporting                   │   │                                │
│ • TPM / RPM Counters  │   └───────────────┬───────────────┘   └───────────────┬────────────────┘
│                       │                   │                                   │
│ [DB 0] Lago Queue:    │                   │ (3. Tokens &                      │ (5. Wallet
│ • Async Job Worker    │                   │     KV-Cache Stats)               │     Ledger Updates)
│   (Sidekiq)           │                   └───────────────┬───────────────────┘
└───────────────────────┘                                   │
        ▲                                                   │
        │ (Background Jobs)                                 ▼
        │                                   ┌────────────────────────────────────────────────────┐
        └───────────────────────────────────┤                POSTGRESQL (SHARED)                 │
                                            │ • LiteLLM DB: Spend Logs, Virtual Keys, Budgets    │
                                            │ • Lago DB: Ledgers, Invoices, Customer Balances    │
                                            └────────────────────────────────────────────────────┘

```
---

### How it Flows

1. **Gateway Caching & Fast-Path Return (LiteLLM $\leftrightarrow$ Redis DB 1):**
When a request arrives, LiteLLM first checks **Redis** for an exact-match or semantic response. If found, it immediately serves the response from memory in sub-5ms with **zero compute cost** and bypasses the GPU backend entirely.

2. **Inference Execution (LiteLLM $\rightarrow$ llama.cpp / vLLM / SGLang):**
On a gateway cache miss, LiteLLM routes the prompt down to the local engine. The engine processes it using its own internal **KV/prefix cache** and streams back the generated tokens.

3. **Usage Emission to Lago (LiteLLM $\rightarrow$ Lago):**
LiteLLM captures the full usage footprint (prompt, completion, and engine KV-cached tokens) and dispatches an asynchronous billing event to Lago.

4. **Billing & Wallet Deductions (Lago $\rightarrow$ PostgreSQL & Redis DB 0):**
Lago processes the event via its **Redis** worker queue, applies discounts for cached tokens, and writes balance deductions to its **PostgreSQL** ledger.
