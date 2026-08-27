#!/usr/bin/env python3
"""Render a reproducible report.md for a responsesapi-01 smoke run.

Reads the per-run artifacts written by test.py
(datasets/responsesapi-01/runs/<run-id>/results.json and eval.json) and renders
a human-readable report.md from the numbers ALONE — no live rAPI calls.
Re-rendering the same run-id therefore always produces the same report
(modulo the rendered_at timestamp).

Usage:
  python smoketests/responsesapi-01/report.py [--run-id <id>] [--out <path>]

Defaults:
  --run-id  latest run (newest runs/<run-*/eval.json)
  --out     datasets/responsesapi-01/runs/<run-id>/report.md

Example:
  pixi run responsesapi-01-test && pixi run responsesapi-01-report
"""

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "datasets", "responsesapi-01", "runs")

SCENARIO_LABELS = {
    "litellm_route": "POST /v1/responses litellm@local-vllm (gateway leg)",
    "vllm_route": "POST /v1/responses vllm@LiquidAI/LFM2.5-2.6B (direct leg)",
    "payload_wire": "payload cleanliness: no isValid/sequence_number, millis created_at",
    "header_route": "POST with x-model-provider: vllm",
    "stream_route": "SSE stream:true on vllm route",
    "stream_wire": "SSE cleanliness: no leaked sequence_number/isValid",
    "retrieve": "GET /v1/responses/{id}",
    "continue_flow": "POST previous_response_id continuation",
    "input_items": "GET /v1/responses/{id}/input_items",
    "engine_down_502": "POST sglang@LiquidAI/LFM2.5-2.6B (engine down) -> expect 502 upstream_error",
    "bad_alias": "POST nope@bogus -> expect HTTP 400",
    "stats": "GET /stats field + requests.failedBy assertions",
    "metrics": "GET /metrics + /prometheus meter + store gauge names",
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def latest_run_id():
    runs = []
    for name in os.listdir(RUNS_DIR):
        run_dir = os.path.join(RUNS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        eval_path = os.path.join(run_dir, "eval.json")
        if os.path.isfile(eval_path):
            runs.append((os.path.getmtime(eval_path), name))
    if not runs:
        sys.exit(f"no runs under {RUNS_DIR}; run responsesapi-01-test first")
    return max(runs)[1]


def render(results, eval_summary, run_id):
    meta = results["meta"]
    rows = results["rows"]
    passed = sum(1 for r in rows if r["ok"])

    lines = []
    a = lines.append
    a(f"# responsesapi-01 smoke run: {run_id}")
    a("")
    a(f"- **service**: `{meta['base_url']}` (cheap-rAPI-memproxy :6644)")
    a(f"- **gateway alias**: `{meta.get('litellm_alias')}` → vLLM :8000")
    a(f"- **direct model**: `{meta.get('vllm_model')}`")
    a(f"- **scenarios**: `{meta.get('scenarios', 0)}`")
    a(f"- **run_at**: `{meta['run_at']}`")
    a(f"- **test**: `{meta['test']}`")
    a("")
    a("## Summary")
    a("")
    a(f"**{passed}/{len(rows)} scenarios passed**")
    a("")

    a("| Scenario | Result | Route / check |")
    a("|----------|--------|---------------|")
    ok_by_name = {r["scenario"]: r["ok"] for r in rows}
    for name, label in SCENARIO_LABELS.items():
        mark = "PASS" if ok_by_name.get(name) else "FAIL"
        a(f"| `{name}` | **{mark}** | {label} |")
    a("")

    a("## Per-scenario detail")
    a("")
    a("| Scenario | http_status | ok | detail |")
    a("|----------|-------------|----|--------|")
    for r in rows:
        detail = (r.get("detail") or "").replace("|", "\\|")
        a(
            f"| `{r['scenario']}` | {r.get('http_status')} | "
            f"{'Y' if r.get('ok') else 'n'} | {detail} |"
        )
    a("")

    a("## Re-run")
    a("")
    a("```sh")
    a("pixi run responsesapi-01-test")
    a("pixi run responsesapi-01-report")
    a("```")
    a("")
    a(
        "Artifacts for this report:"
        if os.path.isdir(os.path.join(RUNS_DIR, run_id))
        else "Artifacts:"
    )
    a("")
    a(f"- `datasets/responsesapi-01/runs/{run_id}/results.json` — raw rows")
    a(f"- `datasets/responsesapi-01/runs/{run_id}/eval.json` — pass/fail summary")
    a(f"- `datasets/responsesapi-01/runs/{run_id}/report.md` — this report")
    a("- latest copies: `datasets/responsesapi-01/results.json`, `eval.json`")
    a("")
    a("---")
    a("")
    a(
        f"*Rendered by `smoketests/responsesapi-01/report.py` "
        f"at {time.strftime('%Y-%m-%dT%H:%M:%S%z')}.*"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render a reproducible report.md")
    parser.add_argument(
        "--run-id", default=None, help="run id; defaults to the latest run"
    )
    parser.add_argument(
        "--out", default=None, help="output path; defaults to the run dir"
    )
    args = parser.parse_args()

    run_id = args.run_id or latest_run_id()
    run_dir = os.path.join(RUNS_DIR, run_id)
    results_path = os.path.join(run_dir, "results.json")
    eval_path = os.path.join(run_dir, "eval.json")
    if not (os.path.isfile(results_path) and os.path.isfile(eval_path)):
        sys.exit(
            f"missing artifacts for run {run_id}: need {results_path} and {eval_path}"
        )
    out_path = args.out or os.path.join(run_dir, "report.md")

    results = load_json(results_path)
    eval_summary = load_json(eval_path)
    report = render(results, eval_summary, run_id)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(report + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
