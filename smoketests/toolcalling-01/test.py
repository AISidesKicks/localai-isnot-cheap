#!/usr/bin/env python3
"""toolcalling-01 smoke test: native tool-call parsing against local-sglang.

Reads datasets/toolcalling-01/scenarios.json (mock tools + tool-requiring Q/A
pairs) and scores each scenario against the engine over the LiteLLM gateway
(alias `local-sglang`):

1. tool_calls emitted at all (vs a plain-text answer)
2. correct tool name matched
3. correct argument key(s) extracted
4. arguments are valid Pythonic syntax `fn(arg="value")` so a local mock can
   actually exec them
5. optional round-trip: feed a mock tool result back and confirm a final answer

Writes per-run datasets/toolcalling-01/runs/<run-id>/results.json (raw rows) and
eval.json (scored scenarios), plus refreshed "latest" copies.
"""

import argparse
import ast
import concurrent.futures
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from executor import detect_executor
from llm import (
    DEFAULT_BASE_URL,
    DEFAULT_TEMPERATURE,
    MODEL,
    cache_regime,
    chat,
    completion_text,
    get_repo_root,
    health,
    reasoning_content,
    timings,
    tool_calls,
    usage_fields,
)
from sandbox import SandboxContext, stop_and_remove

DEFAULT_SCENARIOS = os.path.join(
    get_repo_root(), "datasets", "toolcalling-01", "scenarios.json"
)
RUNS_DIR = os.path.join(get_repo_root(), "datasets", "toolcalling-01", "runs")
RESULTS_PATH = os.path.join(
    get_repo_root(), "datasets", "toolcalling-01", "results.json"
)
EVAL_PATH = os.path.join(get_repo_root(), "datasets", "toolcalling-01", "eval.json")

MAX_TRIES = 3
REMINDER = "Please answer again:"
MOCK_RESPONSES = {
    "get_weather": "The current weather in %(location)s is sunny, 22C.",
    "calculate": "The result of %(expression)s is 42.",
    "lookup_film_year": "%(title)s was released in 1988.",
}


def load_scenarios(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_arguments(raw):
    """Parse tool-call arguments into a dict; None on malformed JSON."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001 - malformed args count as a miss
        return None
    return parsed if isinstance(parsed, dict) else None


def pythonic_syntax(name, args_parsed):
    """Valid Pythonic `fn(arg="value")` that ast can parse with keyword args."""
    if not name or not args_parsed:
        return None
    parts = [f"{key}={value!r}" for key, value in args_parsed.items()]
    source = f"{name}({', '.join(parts)})"
    try:
        node = ast.parse(source)
        call = node.body[0].value
        if not isinstance(call, ast.Call) or not call.keywords:
            return None
    except Exception:  # noqa: BLE001 - unparseable syntax counts as a miss
        return None
    return source


def execute_tool(tool_name, args_dict, executor):
    """Execute a tool call through the active executor."""
    import time as _time

    t0 = _time.monotonic()
    try:
        content = executor.execute(tool_name, args_dict)
    except Exception as exc:  # noqa: BLE001
        content = f"error: {exc}"
    elapsed = round(_time.monotonic() - t0, 3)
    return content, executor.mode, elapsed


def mock_result(call):
    """Return a mock tool output string (stub; never hits an external API)."""
    template = MOCK_RESPONSES.get(call.get("name"), "ok")
    args = call.get("_args") or {}
    try:
        return template % args
    except Exception:  # noqa: BLE001 - fall back to a safe stub
        return "ok"


def run_case(scenario, args, executor=None):
    """One scenario: emit tool calls, score name/args/syntax, optional round-trip."""
    data = load_scenarios(args.scenarios)
    tools = data["tools"]
    content = scenario["prompt"]
    expected_tool = scenario.get("tool")
    expected_args = scenario.get("args") or {}
    last_resp = None
    last_seconds = 0.0
    for attempt in range(1, MAX_TRIES + 1):
        payload = (REMINDER + " " + content) if attempt > 1 else content
        resp, seconds = chat(
            payload,
            tools=tools,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        last_resp, last_seconds = resp, seconds
        if tool_calls(resp):
            break

    calls = tool_calls(last_resp) if last_resp is not None else []
    selected = calls[0] if calls else None
    row = {
        "scenario": scenario["id"],
        "prompt": content,
        "tool_calls": len(calls),
        "tool_used": None,
        "expected_tool": expected_tool,
        "tool_name_ok": False,
        "arguments": selected["arguments"] if selected else None,
        "args_parsed": None,
        "expected_args": expected_args,
        "args_ok": False,
        "pythonic": None,
        "syntax_ok": False,
        "round_trip": None,
        "round_trip_ok": False,
        "final_answer": None,
        "reasoning": reasoning_content(last_resp) if last_resp else None,
        "cache_regime": cache_regime(last_resp) if last_resp else None,
        "timings": timings(last_resp) if last_resp else {},
        "seconds": round(last_seconds, 3) if last_seconds else 0.0,
        "usage": usage_fields(last_resp) if last_resp else {},
        "executed_ok": False,
        "executor_mode": executor.mode if executor else "local",
        "exec_seconds": 0.0,
    }

    if not selected:
        row["answer"] = completion_text(last_resp)[:200] if last_resp else ""
        return row

    name_ok = bool(expected_tool) and selected["name"] == expected_tool
    args_parsed = parse_arguments(selected["arguments"])
    args_ok = bool(args_parsed) and all(
        str(args_parsed.get(key)) == str(value) for key, value in expected_args.items()
    )
    pythonic = pythonic_syntax(selected["name"], args_parsed) if args_parsed else None

    row.update(
        {
            "tool_used": name_ok,
            "tool_name_ok": name_ok,
            "args_parsed": args_parsed,
            "args_ok": args_ok,
            "pythonic": pythonic,
            "syntax_ok": pythonic is not None,
        }
    )

    exec_content = None
    if args.round_trip and pythonic is not None and args_parsed is not None:
        if executor is not None:
            content_str, exe_mode, exe_sec = execute_tool(
                selected["name"], args_parsed, executor
            )
            row["executed_ok"] = True
            row["executor_mode"] = exe_mode
            row["exec_seconds"] = exe_sec
            exec_content = content_str
        else:
            exec_content = mock_result(selected)
        selected["_args"] = args_parsed
        rt = roundtrip(content, tools, selected, args, exec_content=exec_content)
        row["round_trip"] = rt
        row["round_trip_ok"] = bool(rt and rt.get("final_answer"))
        row["final_answer"] = rt.get("final_answer") if rt else None
    return row


def raw_args_json(call):
    """Render parsed args back to their raw JSON string form."""
    try:
        return json.dumps(call.get("_args") or {})
    except Exception:  # noqa: BLE001
        return "{}"


def roundtrip(content, tools, call, args, exec_content=None):
    """Feed a (mock or real) tool result back and ask for the final answer."""
    tool_result = exec_content if exec_content is not None else mock_result(call)
    messages = [
        {"role": "user", "content": content},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_mock",
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": raw_args_json(call),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_mock", "content": tool_result},
        {"role": "user", "content": "Using the tool result, give the final answer."},
    ]
    resp, seconds = chat(
        content,
        tools=tools,
        messages=messages,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    return {
        "final_answer": completion_text(resp) or None if resp else None,
        "round_seconds": round(seconds, 3) if seconds else 0.0,
        "round_tokens": usage_fields(resp) if resp else {},
    }


def default_run_id(model_alias):
    return f"run-{time.strftime('%Y%m%d-%H%M%S')}-{model_alias}"


def str_stat(ok, total):
    return f"{ok}/{total} ({round(ok / total, 3) if total else 0.0:.0%})"


def main():
    parser = argparse.ArgumentParser(description="Run the toolcalling-01 smoke test.")
    parser.add_argument(
        "--scenarios", default=DEFAULT_SCENARIOS, help="scenarios JSON path"
    )
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="sampling temperature (default 0.1)",
    )
    parser.add_argument("--workers", type=int, default=4, help="max concurrent calls")
    parser.add_argument(
        "--round-trip",
        action="store_true",
        help="feed a mock result back for a final answer after a valid tool call",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="LiteLLM gateway URL"
    )
    parser.add_argument(
        "--run-id", default=None, help="run identifier (default timestamp+model)"
    )
    parser.add_argument(
        "--model", default=MODEL, help="gateway model alias (default local-sglang)"
    )
    parser.add_argument("--skip-health", action="store_true", help="skip health probes")
    parser.add_argument(
        "--executor",
        default="auto",
        choices=["sandbox", "local", "auto"],
        help="tool executor mode (default auto: probe sandbox, fall back local)",
    )
    args = parser.parse_args()
    import llm as llm_mod

    llm_mod.MODEL = args.model

    if args.max_tokens is None:
        args.max_tokens = 512

    if not args.skip_health and not health(args.base_url + "/health/readiness"):
        sys.exit(f"gateway not ready at {args.base_url}/health/readiness")
    print(f"gateway {args.base_url} healthy; scenarios {args.scenarios}")

    run_id = args.run_id or default_run_id(args.model)
    run_dir = os.path.join(RUNS_DIR, run_id)
    run_results = os.path.join(run_dir, "results.json")
    run_eval = os.path.join(run_dir, "eval.json")
    print(f"run id: {run_id}")

    scenarios = load_scenarios(args.scenarios)["scenarios"]
    if not scenarios:
        sys.exit("empty scenarios file")
    print(f"{len(scenarios)} scenarios loaded")

    sandbox_ctx = SandboxContext()
    tool_executor = None
    executor_mode = "local"
    try:
        tool_executor, executor_mode = detect_executor(
            sandbox_ctx, prefer=args.executor
        )
        print(f"executor mode: {executor_mode}")
    except Exception as exc:  # noqa: BLE001
        print(f"executor detection failed ({exc}); using local mock", file=sys.stderr)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(run_case, s, args=args, executor=tool_executor)
            for s in scenarios
        ]
        for fut in concurrent.futures.as_completed(futures):
            rows.append(fut.result())
    rows.sort(key=lambda r: r["scenario"])

    if sandbox_ctx.sandbox is not None:
        stop_and_remove(sandbox_ctx)

    for row in rows:
        print(
            f"  {row['scenario']:<20} calls={row['tool_calls']} "
            f"tool={row.get('arguments') and row.get('args_parsed') or '-'} "
            f"name_ok={row['tool_name_ok']} args_ok={row['args_ok']} "
            f"syntax_ok={row['syntax_ok']} {row['seconds']}s",
            flush=True,
        )

    n = len(rows)
    tool_used = sum(1 for r in rows if r["tool_calls"] > 0)
    tool_ok = sum(1 for r in rows if r["tool_name_ok"])
    args_ok = sum(1 for r in rows if r["args_ok"])
    syntax_ok = sum(1 for r in rows if r["syntax_ok"])
    round_rows = [r for r in rows if r.get("round_trip") is not None]
    round_ok = sum(1 for r in round_rows if r.get("round_trip_ok"))

    meta = {
        "name": "toolcalling-01",
        "test": "smoketests/toolcalling-01/test.py",
        "run_id": run_id,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model_alias": args.model,
        "base_url": args.base_url,
        "dataset": args.scenarios,
        "scenarios": len(scenarios),
        "temperature": args.temperature,
        "workers": args.workers,
    }
    results = {"meta": meta, "rows": rows}
    eval_summary = {
        "meta": meta,
        "tool_calls_emitted": {
            "score": str_stat(tool_used, n),
            "fraction": round(tool_used / n, 3) if n else 0.0,
        },
        "correct_tool_name": {
            "score": str_stat(tool_ok, n),
            "fraction": round(tool_ok / n, 3) if n else 0.0,
        },
        "correct_arguments": {
            "score": str_stat(args_ok, n),
            "fraction": round(args_ok / n, 3) if n else 0.0,
        },
        "pythonic_syntax": {
            "score": str_stat(syntax_ok, n),
            "fraction": round(syntax_ok / n, 3) if n else 0.0,
            "check": "ast Call with keyword args",
        },
        "round_trip": {
            "score": str_stat(round_ok, len(round_rows)) if round_rows else "0/0",
            "fraction": round(round_ok / len(round_rows), 3) if round_rows else 0.0,
            "enabled": args.round_trip,
        },
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


if __name__ == "__main__":
    main()
