#!/usr/bin/env python3
"""Shared LiteLLM helper for the toolcalling-01 smoke lab.

Resolves the gateway master key at runtime (env var, then docker/.env, else a
demo placeholder that is never the real key) and wraps the verified
`litellm.completion` call against the `local-sglang` alias with the native
OpenAI tool-calling payload (`tools=[...]`, `tool_choice="auto"`,
`temperature=0.1`) so the gateway forwards the tool schema to the engine.
Captures Redis regime, token counts, reasoning and timings the same way the
cinematic-01 helper does.

Mock tools (no external APIs) live in scenarios.json; this module only defines
the wire wrapper plus response introspection helpers.
"""

import os
import sys
import time
import urllib.error
import urllib.request

import litellm

MODEL = "local-sglang"
DEFAULT_BASE_URL = "http://localhost:4000"
DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.1
CACHE_PARAM = {}

# Cache-mode presets passed per call as the litellm `cache` kwarg, mirroring the
# cinematic-01 lab so the tool-call regime is reported the same way.
CACHE_MODES = {
    "1level": {"no-cache": True},
    "2level": {},
    "no-cache": {"no-cache": True},
}
DEMO_KEY = "sk-1234-master-key-4321"
TIMEOUT_S = 120


def get_repo_root():
    """Repo root: three levels up from smoketests/toolcalling-01/llm.py."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_master_key():
    """Runtime master key: env var, then docker/.env, then a demo placeholder."""
    key = os.environ.get("LITELLM_MASTER_KEY")
    if key:
        return key.strip().strip("\"'")
    env_file = os.path.join(get_repo_root(), "docker", ".env")
    try:
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("LITELLM_MASTER_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    print("WARNING: LITELLM_MASTER_KEY not found, using demo default", file=sys.stderr)
    return DEMO_KEY


def health(url):
    """Probe an endpoint; True on HTTP 200."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except (OSError, urllib.error.URLError):
        return False


def chat(
    content,
    tools,
    *,
    base_url=DEFAULT_BASE_URL,
    max_tokens=DEFAULT_MAX_TOKENS,
    temperature=DEFAULT_TEMPERATURE,
    tool_choice="auto",
    retries=3,
    messages=None,
    **kv,
):
    """Tool-calling completion via the LiteLLM SDK; returns (resp, seconds).

    `tools` is the OpenAI-style tool schema array; `tool_choice` defaults to
    "auto". `temperature` defaults to 0.1 per the Liquid AI recommendation for
    tool-calling pipelines. Extra `**kv` (model, cache_mode, reasoning, etc.)
    passes straight through to `litellm.completion`. On error, retries with a
    reminder suffix so a cached empty answer is not replayed.
    """
    cache_mode = kv.pop("cache_mode", None)
    model = kv.pop("model", None) or MODEL
    cache_param = CACHE_MODES.get(str(cache_mode) if cache_mode is not None else "", {})
    kwargs = {
        "model": model,
        "base_url": base_url,
        "custom_llm_provider": "openai",
        "api_key": get_master_key(),
        "cache": dict(cache_param),
        "messages": messages or [{"role": "user", "content": content}],
        "tools": tools,
        "tool_choice": tool_choice,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    kwargs.update(kv)
    t0 = time.perf_counter()
    for attempt in range(1, retries + 1):
        if attempt > 1:
            time.sleep(0.5 * attempt)
            kwargs["messages"] = messages or [
                {"role": "user", "content": "Please answer again: " + content}
            ]
        try:
            resp = litellm.completion(**kwargs)
            return resp, time.perf_counter() - t0
        except Exception as exc:  # noqa: BLE001 - retry on transient gateway faults
            if attempt == retries:
                print(
                    "chat: failing on final attempt",
                    f"{type(exc).__name__}: {exc}",
                    repr(content)[:160],
                    file=sys.stderr,
                )
                return None, time.perf_counter() - t0
    raise RuntimeError("unreachable")


def completion_text(resp):
    """Primary answer text from a completion response."""
    try:
        return (resp.choices[0].message.content or "").strip()
    except (AttributeError, IndexError):
        return ""


def reasoning_content(resp, limit=400):
    """Thinking snippet from a completion response, else None."""
    message = getattr(getattr(resp, "choices", [None])[0], "message", None)
    if message is None:
        return None
    text = getattr(message, "reasoning_content", None)
    if not isinstance(text, str) or not text:
        extra = getattr(message, "model_extra", None) or {}
        text = None
        for key in ("reasoning_content", "reasoning", "thinking"):
            candidate = extra.get(key)
            if isinstance(candidate, str) and candidate:
                text = candidate
                break
    if not isinstance(text, str) or not text:
        return None
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def tool_calls(resp):
    """List of tool-call dicts from a response, else []."""
    message = getattr(getattr(resp, "choices", [None])[0], "message", None)
    if message is None:
        return []
    calls = getattr(message, "tool_calls", None) or []
    out = []
    for c in calls:
        fn = getattr(getattr(c, "function", None), "name", None)
        args = getattr(getattr(c, "function", None), "arguments", None)
        out.append({"name": fn or "", "arguments": args or ""})
    return out


def cache_regime(resp):
    """litellm-redis-hit iff hidden params carry the x-litellm-cache-key header."""
    hidden = getattr(resp, "_hidden_params", None) or {}
    headers = hidden.get("additional_headers") or {}
    items = headers.items() if isinstance(headers, dict) else headers
    for key, _ in items:
        if "x-litellm-cache-key" in str(key).lower():
            return "litellm-redis-hit"
    return "litellm-redis-miss"


def usage_fields(resp):
    """Token counts from the response usage block."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def cached_tokens(resp):
    """Engine-prefix-reuse tokens from the response, or None."""
    usage = getattr(resp, "usage", None)
    details = (
        getattr(usage, "prompt_tokens_details", None) if usage is not None else None
    )
    value = None
    if details is not None:
        value = getattr(details, "cached_tokens", None)
    if value is None:
        extra = getattr(usage, "model_extra", None) if usage is not None else None
        details = (
            (extra or {}).get("prompt_tokens_details")
            if isinstance(extra, dict)
            else None
        )
        if isinstance(details, dict):
            value = details.get("cached_tokens")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def timings(resp):
    """llama.cpp prompt/cache timings; live in model_extra, not usage, here."""
    extra = getattr(resp, "model_extra", None) or {}
    if not isinstance(extra, dict):
        return {}
    t = extra.get("timings") or {}
    if not isinstance(t, dict):
        return {}
    return {
        "prompt_n": t.get("prompt_n"),
        "cache_n": t.get("cache_n"),
        "predicted_n": t.get("predicted_n"),
    }
