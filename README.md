# EDU AI LAB (localai.isnot.cheap)

Hey!!! Local AI is not CHEAP at ALL! - **Every AI token carries a COST!** 

## So how to measure and bill AI tokens in small AI Lab? 

This is tricky architectural and engineering challenge with lot of tradeoffs.

I put here minimal setups from large ones I use in enterprise workshops to demonstrate complexity of Local AI Interference Engendering in practice and role of caching. 

Setup is prepared to be executed as educational lab on gamming PC with 32GB RAM and Nvidia GPU (12GB VRAM).

## EDU AI LAB localai.isnot.cheap OVERVIEW:

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

5. **Billing & Wallet Deductions (Lago $\rightarrow$ PostgreSQL & Redis DB 0):**
Lago processes the event via its **Redis** worker queue, applies discounts for cached tokens, and writes balance deductions to its **PostgreSQL** ledger.
