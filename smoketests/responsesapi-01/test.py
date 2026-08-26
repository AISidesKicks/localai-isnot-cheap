#!/usr/bin/env python3
"""responsesapi-01 smoke test: rAPI memproxy Responses-API surface.

Drives the `cheap-rAPI-memproxy` component (OpenResponses-compatible cache and
routing shim in front of LiteLLM) with the Responses-API subset it exposes on
:6644. The test is stdlib-only (urllib/json) so it runs on a bare Python 3.12:
it probes /health up front, then runs one row per scenario:

  - litellm_route   POST /v1/responses `litellm@local-vllm`, store:true
  - vllm_route      POST /v1/responses `vllm@LiquidAI/LFM2.5-2.6B`, store:true
  - header_route    POST with `x-model-provider: vllm` header instead of model@
  - stream_route    POST stream:true on the vllm route (SSE body)
  - retrieve        GET /v1/responses/{id} for a stored response
  - continue_flow   POST with previous_response_id to extend the same flow
  - input_items     GET /v1/responses/{id}/input_items for the stored response
  - bad_alias       POST `nope@bogus` -> expect HTTP 400
  - stats           GET /stats, assert service/requests/responseStore/cache/memory
  - metrics         GET /metrics + /prometheus, assert meter names

Writes per-run datasets/responsesapi-01/runs/<run-id>/results.json (raw rows)
and eval.json (pass/fail summary), plus refreshed "latest" copies.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "datasets", "responsesapi-01", "runs")
RESULTS_PATH = os.path.join(REPO_ROOT, "datasets", "responsesapi-01", "results.json")
EVAL_PATH = os.path.join(REPO_ROOT, "datasets", "responsesapi-01", "eval.json")

DEFAULT_BASE_URL = "http://localhost:6644"
VLLM_MODEL = "LiquidAI/LFM2.5-2.6B"
LITELLM_ALIAS = "local-vllm"
DEMO_KEY = "sk-1234-master-key-4321"
TIMEOUT_S = 90


def get_master_key():
    """Runtime master key: env var, then docker/.env, then a demo placeholder."""
    key = os.environ.get("LITELLM_MASTER_KEY")
    if key:
        return key.strip().strip("\"'")
    env_file = os.path.join(REPO_ROOT, "docker", ".env")
    try:
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("LITELLM_MASTER_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    print("WARNING: LITELLM_MASTER_KEY not found, using demo default", file=sys.stderr)
    return DEMO_KEY


def http_json(
    url, *, method="GET", payload=None, key=None, headers=None, timeout=TIMEOUT_S
):
    """Do an HTTP call and return (status, parsed-json-or-None, body-text)."""
    req_headers = {"Content-Type": "application/json"}
    if key:
        req_headers["Authorization"] = f"Bearer {key}"
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(body)
            except (ValueError, json.JSONDecodeError):
                parsed = None
            return resp.status, parsed, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            parsed = None
        return exc.code, parsed, body
    except (OSError, urllib.error.URLError) as exc:
        return None, None, f"transport error: {exc}"


def health(url):
    """True if GET url returns HTTP 200."""
    status, _, _ = http_json(url, timeout=10)
    return status == 200


def stream_payload(base, payload, key):
    """POST a streaming request and consume the SSE body.

    Returns dict with collected deltas, whether response.completed was seen,
    and the tail of the raw body.
    """
    url = base + "/v1/responses"
    req_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=req_headers)
    deltas = []
    done = False
    tail = ""
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                tail = line
                if line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue
                chunk = line[len("data:") :].strip()
                try:
                    obj = json.loads(chunk)
                except (ValueError, json.JSONDecodeError):
                    continue
                if obj.get("type") == "response.output_text.delta":
                    deltas.append(obj.get("delta", ""))
                elif obj.get("type") == "response.completed":
                    done = True
    except (OSError, urllib.error.URLError) as exc:
        return {"deltas": deltas, "completed": done, "error": f"transport error: {exc}"}
    return {"deltas": deltas, "completed": done, "tail": tail[:200]}


def main():
    parser = argparse.ArgumentParser(description="Run the responsesapi-01 smoke test.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="rAPI base URL")
    parser.add_argument("--run-id", default=None, help="run identifier")
    parser.add_argument("--skip-health", action="store_true", help="skip health probes")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    key = get_master_key()

    targets = {
        "rapi": (base + "/health", "rAPI memproxy"),
        "vllm": ("http://localhost:8000/health", "vLLM (direct engine leg)"),
        "litellm": ("http://localhost:4000/health/liveliness", "LiteLLM (gateway leg)"),
    }
    if not args.skip_health:
        for name, (url, label) in targets.items():
            ok = health(url)
            print(f"  health[{name}] {label}: {'UP' if ok else 'DOWN'}")
            if not ok:
                sys.exit(f"pre-flight health failed: {label} at {url}")

    run_id = args.run_id or f"run-{time.strftime('%Y%m%d-%H%M%S')}-responsesapi"
    run_dir = os.path.join(RUNS_DIR, run_id)
    run_results = os.path.join(run_dir, "results.json")
    run_eval = os.path.join(run_dir, "eval.json")
    print(f"run id: {run_id}")

    responses_url = base + "/v1/responses"
    rows = []

    def row(name, status, ok, detail):
        rows.append(
            {
                "scenario": name,
                "http_status": status,
                "ok": bool(ok),
                "detail": detail,
            }
        )
        print(f"  {name:<16} http={status} ok={bool(ok)} {detail[:120]}", flush=True)

    # --- litellm_route ---------------------------------------------------
    status, body, raw = http_json(
        responses_url,
        method="POST",
        key=key,
        payload={
            "model": f"litellm@{LITELLM_ALIAS}",
            "input": "What is a weighted cache in one sentence?",
            "store": True,
        },
    )
    ok = status == 200 and isinstance(body, dict) and body.get("object") == "response"
    row("litellm_route", status, ok, f"model={body.get('model') if body else raw}")

    # --- vllm_route ------------------------------------------------------
    status, body, raw = http_json(
        responses_url,
        method="POST",
        key=key,
        payload={
            "model": f"vllm@{VLLM_MODEL}",
            "input": "Return the word alpha.",
            "store": True,
        },
    )
    ok = status == 200 and isinstance(body, dict) and body.get("object") == "response"
    row("vllm_route", status, ok, f"model={body.get('model') if body else raw}")

    stored_id = body.get("id") if isinstance(body, dict) else None

    # --- header_route ----------------------------------------------------
    status, body, raw = http_json(
        responses_url,
        method="POST",
        key=key,
        headers={"x-model-provider": "vllm"},
        payload={"model": VLLM_MODEL, "input": "Return the word beta.", "store": True},
    )
    ok = status == 200 and isinstance(body, dict) and body.get("model") == VLLM_MODEL
    row("header_route", status, ok, f"model={body.get('model') if body else raw}")

    # --- stream_route ----------------------------------------------------
    sres = stream_payload(
        base,
        {
            "model": f"vllm@{VLLM_MODEL}",
            "input": "Return the word gamma.",
            "stream": True,
        },
        key,
    )
    ok = bool(sres.get("deltas")) and sres.get("completed")
    row(
        "stream_route",
        200,
        ok,
        f"deltas={len(sres.get('deltas', []))} completed={sres.get('completed')}",
    )

    # --- retrieve --------------------------------------------------------
    status, body, raw = 0, None, "no stored id"
    if stored_id:
        status, body, raw = http_json(f"{responses_url}/{stored_id}", key=key)
    ok = (
        stored_id is not None
        and status == 200
        and isinstance(body, dict)
        and body.get("id") == stored_id
    )
    row("retrieve", status, ok, f"id={stored_id}")

    # --- continue_flow ---------------------------------------------------
    status, body, raw = 0, None, "no stored id"
    if stored_id:
        status, body, raw = http_json(
            responses_url,
            method="POST",
            key=key,
            payload={
                "model": f"vllm@{VLLM_MODEL}",
                "input": "Now return omega.",
                "previous_response_id": stored_id,
                "store": True,
            },
        )
    ok = (
        status == 200
        and isinstance(body, dict)
        and body.get("previous_response_id") == stored_id
    )
    row(
        "continue_flow",
        status,
        ok,
        f"prev={body.get('previous_response_id') if isinstance(body, dict) else raw}",
    )

    # --- input_items -----------------------------------------------------
    status, body, raw = 0, None, "no stored id"
    if stored_id:
        status, body, raw = http_json(
            f"{responses_url}/{stored_id}/input_items", key=key
        )
    ok = status == 200 and isinstance(body, dict) and body.get("object") == "list"
    row(
        "input_items",
        status,
        ok,
        f"object={body.get('object') if isinstance(body, dict) else raw}",
    )

    # --- bad_alias -------------------------------------------------------
    status, body, raw = http_json(
        responses_url,
        method="POST",
        key=key,
        payload={"model": "nope@bogus", "input": "hi"},
    )
    ok = status == 400
    row("bad_alias", status, ok, f"expect 400 got {status}")

    # --- stats -----------------------------------------------------------
    status, stats, raw = http_json(base + "/stats", key=key)
    s_ok = status == 200 and isinstance(stats, dict)
    checks = {}
    if s_ok:
        checks = {
            "service": stats.get("service") == "open-responses-memproxy",
            "requests.total>0": int(stats.get("requests", {}).get("total", 0)) > 0,
            "responseStore.entries>0": int(
                stats.get("responseStore", {}).get("entries", 0)
            )
            > 0,
            "cache.mode==on": stats.get("cache", {}).get("mode") == "on",
            "memory.maxBytes==3221225472": stats.get("memory", {}).get("maxBytes")
            == 3221225472,
            "maximumWeightBytes==2147483648": stats.get("responseStore", {}).get(
                "maximumWeightBytes"
            )
            == 2147483648,
        }
    else:
        checks = {
            k: False
            for k in (
                "service",
                "requests.total>0",
                "responseStore.entries>0",
                "cache.mode==on",
                "memory.maxBytes==3221225472",
                "maximumWeightBytes==2147483648",
            )
        }
    ok = s_ok and all(checks.values())
    row("stats", status, ok, json.dumps(checks) if checks else raw)

    # --- metrics ---------------------------------------------------------
    status, mbody, _mraw = http_json(base + "/metrics", key=key)
    names = mbody.get("names", []) if isinstance(mbody, dict) else []
    m_ok = (
        status == 200 and "http.server.requests" in names and "jvm.memory.used" in names
    )
    pstatus, _, pbody = http_json(base + "/prometheus", key=key)
    p_ok = pstatus == 200 and "jvm_memory_used_bytes" in pbody
    ok = m_ok and p_ok
    row(
        "metrics",
        status,
        ok,
        f"http.server.requests={'Y' if 'http.server.requests' in names else 'n'} jvm_memory_used_bytes={'Y' if p_ok else 'n'}",
    )

    # --- meta + artifacts ------------------------------------------------
    passed = sum(1 for r in rows if r["ok"])
    meta = {
        "name": "responsesapi-01",
        "test": "smoketests/responsesapi-01/test.py",
        "run_id": run_id,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base,
        "litellm_alias": LITELLM_ALIAS,
        "vllm_model": VLLM_MODEL,
        "scenarios": len(rows),
    }
    results = {"meta": meta, "rows": rows}
    eval_summary = {
        "meta": meta,
        "scenarios_passed": f"{passed}/{len(rows)}",
        "rows": {r["scenario"]: r["ok"] for r in rows},
    }

    os.makedirs(run_dir, exist_ok=True)
    for path, payload in ((run_results, results), (run_eval, eval_summary)):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
    for path in (RESULTS_PATH, EVAL_PATH):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                results if path == RESULTS_PATH else eval_summary,
                fh,
                indent=2,
                ensure_ascii=False,
            )
    print(f"wrote {run_results} and {run_eval}")
    print(f"latest copies at {RESULTS_PATH} and {EVAL_PATH}")
    print(f"scenarios passed: {passed}/{len(rows)}")
    sys.exit(0 if passed == len(rows) else 1)


if __name__ == "__main__":
    main()
