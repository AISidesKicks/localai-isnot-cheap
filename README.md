# EDU AI LAB (localai.isnot.cheap)

Hey!!! Local AI is not CHEAP at ALL! - **Every AI token carries a COST!** 

Running **local AI** is far from free - it simply shifts the invoice from a cloud vendor to your own balance sheet. 

Between high-end GPU based systems, surging electricity and cooling bills, server maintenance, and the specialized engineering talent required to keep inference pipelines optimized, self-hosting carries in real lafe massive capital and operational expenses.

Metering and tracking internal teams by the token is essential: it creates accountability against wasteful compute loops and directly amortizes those upfront infrastructure, pipelines, and staffing investments.

## So how to measure and track AI tokens in small AI Lab? 

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
 - W8A16 [AutoRound W8A16 (8-bit weights / fp16 activations = 2.9 GB)](https://huggingface.co/plavno/LFM2.5-2.6B-AutoRound-W8A16)

The lab's vLLM and SGLang profiles run the AutoRound W8A16 checkpoint, while
llama.cpp serves the Q8_0 GGUF.

There are a lot of modified and uncensored variants of LFM2.5-2.6B:

 A Little Uncensored:

  - [LFM2.5-2.6B-Uncensored-GGUF](https://huggingface.co/SC117/LFM2.5-2.6B-Uncensored-GGUF)
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
=============================================================================================
         EDU AI LAB: localai.isnot.cheap  —  "Every AI token carries a COST!"
=============================================================================================

                                  [ Users / Teams / Apps ]
                                             │
                                             │ (1. API Request + Virtual Key)
                                             ▼
┌───────────────────────────────────────────────────────────── ──────────────────────────────┐
│                                     LITELLM (AI GATEWAY)                                   │
│                    • Request Interception & Quota Checks (Users/Teams/Apps)                │
│                    • Cache Layer: Exact / Semantic Response Matching                       │
│                    • Rate Limiting (TPM/RPM) & Dynamic Cost Calculation                    │
│                    • OTLP Trace Export to Phoenix                                          │
│                    • MCP Gateway: MCP and namespaced tools                                 │
└───────┬────────────────────────────────┬───────────────────────────────┬───────────────────┘
        │                                │                               │
        │ (2. Cache Lookup               │ (3. Cache Miss:               │ (4. OTLP Trace &)
        │     Auth Key Check)            │     Inference Request)        │     Usage Events)                        │
        ▼                                ▼                               ▼                                          ▼
┌───────────────────────┐ ┌───────────────────────────────┐ ┌────────────────────────────────┐
│        REDIS          │ │   LOCAL AI INFERENCE ENGINE   │ │    PHOENIX (OBSERVABILITY)     │
│ LiteLLM Cache:        │ │ [ llama.cpp | vLLM | SGLang ] │ │ • OTLP Trace Ingestion         │
│ • Response Cache Hit  │ │ • GPU / CPU Acceleration      │ │ • Token Counting & Model Costs │
│ • Auth Key Validation │ │ • Model Prefill & Decode      │ │ • Runtime / Latency Metrics    │
│ • TPM / RPM Counters  │ │ • Prefix / KV-Cache Hit       │ │ • MCP Server (/mcp)            │
└───────────────────────┘ └────────────┬──────────────────┘ └────────┬───────────────────────┘
                                       │                             │
    (8. MCP Tools)                     │ (5. Prometheus              │ (6. Spans, Token
                                       │     /metrics Scrape)        │     Counts & Costs)
                                       ▼                             ▼
┌───────────────────────┐ ┌───────────────────────────┐ ┌────────────────────────────────────┐
│   ADMIN MCP SERVERS   │ │     VICTORIAMETRICS       │ │         POSTGRESQL (SHARED)        │
│ • LiteLLM Admin MCP   │ │ • Engine Metrics Store    │ │ • LiteLLM DB: Spend Logs, Budgets  │
│ • VictoriaMetrics MCP │ │ • GPU / Host Utilization  │ │ • Phoenix DB: Traces, Spans, Cost  │
│ • Phoenix MCP         │ └───────────────┬───────────┘ └───────────────────┬────────────────┘                                                                               │ 
│                       │                 │                                 │
│  LiteLLM  MCP Gateway │                 │       (7. Query & Insights)     │
│ • all Admin MCPs      │                 ▼                                 ▼
│                       │         ┌─────────────────────────────────────────────────────┐
│  LiteLLM  MCP custom  │         │            CUSTOM REPORT SCRIPTS (API/MCP)          │
│ • NameSpaced tools    │         │       (per-team cost / size / latency reports)      │
└───────────────────────┘         └─────────────────────────────────────────────────────┘
```
---

### How it Flows

1. **API Request with a Virtual Key (Users/Teams/Apps $\rightarrow$ LiteLLM):**
Every call enters through the gateway carrying a **virtual key** that identifies the user, team, or app behind it. LiteLLM intercepts the request, runs its quota and budget checks, and enforces **TPM/RPM** rate limits before anything heavy happens.

2. **Cache Lookup & Fast-Path Return (LiteLLM $\leftrightarrow$ Redis):**
LiteLLM checks **Redis** for an exact-match or semantic response first. On a hit, it serves the answer in sub-5ms with **zero compute cost** — the GPU never even wakes up.

3. **Inference Execution (LiteLLM $\rightarrow$ llama.cpp / vLLM / SGLang):**
On a cache miss, LiteLLM routes the prompt down to the local engine. The engine processes it using its own internal **KV/prefix cache** and streams back the generated tokens.

4. **Observability Emission (LiteLLM $\rightarrow$ Phoenix):**
LiteLLM exports an OTLP trace to Phoenix carrying the full usage footprint — prompt, completion, and **KV-cached** token counts — so every call can be priced and timed.

5. **Engine Metrics Collection (Engines $\rightarrow$ VictoriaMetrics):**
The engines and hosts expose their own metrics, which **VictoriaMetrics** scrapes and stores as GPU and host utilization data.

6. **Persistence & Insights (Phoenix $\rightarrow$ PostgreSQL):**
Phoenix persists the ingested spans, token counts, and cost attributes into the shared **PostgreSQL**, making the whole lab's usage queryable.

7. **Query & Insights (PostgreSQL $\leftarrow$ Report Scripts):**
Custom report scripts query the persisted trace and spend data to build per-team cost, size, and latency reports — the raw materials for the team accountability story.

8. **Agentic Access via MCP Tools (Agents $\rightarrow$ LiteLLM MCP Gateway $\rightarrow$ Admin MCPs):**
Agents don't touch raw infrastructure. Instead they reach it through governed MCP access, three ways:
   - **Direct (Admin MCPs):** agents talk straight to an individual admin MCP server — Phoenix, VictoriaMetrics, or the LiteLLM admin MCP.
   - **Aggregated (MCP Gateway):** all three admin MCPs surface behind the gateway's single MCP endpoint, tools namespaced per server (`phoenix-*`, `victoriametrics-*`, `litellm_admin-*`).
   - **Managed (Toolsets):** curated, named subsets of tools pulled from across the servers, so each team only gets the slice of the lab they're meant to see.

---

*Footnote: I have dyslexia, so from time to time I let the LLMs give my English a power-up — think of it as a GPU-accelerated spellchecker running at a few hundred tokens per second. If any sentence here reads a little too polish, that was the model showing off, not me.*
