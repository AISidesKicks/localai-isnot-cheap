#!/usr/bin/env python3
"""Render a reproducible report.md for a toolcalling-01 smoke run.

Reads the per-run artifacts written by test.py
(datasets/toolcalling-01/runs/<run-id>/results.json and eval.json) and renders
a human-readable report.md from the numbers ALONE — no live gateway calls.
Re-rendering the same run-id therefore always produces the same report
(modulo the rendered_at timestamp).

Usage:
  python smoketests/toolcalling-01/report.py [--run-id <id>] [--out <path>]

Defaults:
  --run-id  latest run (newest runs/<run-*/eval.json)
  --out     datasets/toolcalling-01/runs/<run-id>/report.md

Example:
  pixi run toolcalling-01-test && pixi run toolcalling-01-report
"""

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS_DIR = os.path.join(REPO_ROOT, "datasets", "toolcalling-01", "runs")

MODEL_ALIASES = {
    "local-sglang": "LFM2.5-2.6B W8A16 (SGLang)",
    "local-llama": "LFM2.5-2.6B W8A16 (vLLM)",
    "local-vllm": "LFM2.5-2.6B W8A16 (vLLM)",
    "local-gguf": "LFM2.5-2.6B Q8_0 GGUF (LocalAI llama.cpp)",
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
        sys.exit(f"no runs under {RUNS_DIR}; run toolcalling-01-test first")
    return max(runs)[1]


def render(results, eval_summary, run_id):
    meta = results["meta"]
    model_alias = meta.get("model_alias", "local-sglang")
    model_hw = MODEL_ALIASES.get(model_alias, model_alias)

    lines = []
    a = lines.append
    a(f"# toolcalling-01 smoke run: {run_id}")
    a("")
    a(f"- **model**: `{model_alias}` — {model_hw}")
    a(f"- **gateway**: `{meta['base_url']}` (LiteLLM + Redis cache)")
    a(f"- **dataset**: `{meta['dataset']}`")
    a(f"- **scenarios**: `{meta.get('scenarios', 0)}`")
    a(f"- **temperature**: `{meta.get('temperature', 0.1)}`")
    a(f"- **workers**: `{meta.get('workers', 4)}`")
    a(f"- **run_at**: `{meta['run_at']}`")
    a(f"- **test**: `{meta['test']}`")
    a("")

    a("## Tool-call scoring")
    a("")
    a("| Criterion | Score | Fraction |")
    a("|-----------|-------|----------|")
    for key, label in (
        ("tool_calls_emitted", "tool_calls emitted"),
        ("correct_tool_name", "correct tool name"),
        ("correct_arguments", "correct arguments"),
        ("pythonic_syntax", "pythonic syntax"),
    ):
        d = eval_summary.get(key, {})
        a(f"| {label} | **{d.get('score', '—')}** | {d.get('fraction', 0.0):.0%} |")
    rt = eval_summary.get("round_trip", {})
    a(
        f"| mock round-trip | **{rt.get('score', '—')}** | {rt.get('fraction', 0.0):.0%} |"
    )
    a("")

    rows = results["rows"]
    a("## Per-scenario detail")
    a("")
    a(
        "| Scenarios | tool_calls | name_ok | args_ok | syntax_ok | pythonic | round_trip_ok | exec_ok | executor | exec_sec | seconds |"
    )
    a(
        "|-----------|------------|---------|---------|-----------|----------|---------------|---------|----------|----------|---------|"
    )
    for r in rows:
        pythonic = r.get("pythonic") or "—"
        if pythonic and len(pythonic) > 48:
            pythonic = pythonic[:45] + "..."
        a(
            f"| {r['scenario']} | {r.get('tool_calls', 0)} | "
            f"{'Y' if r.get('tool_name_ok') else 'n'} | "
            f"{'Y' if r.get('args_ok') else 'n'} | "
            f"{'Y' if r.get('syntax_ok') else 'n'} | `{pythonic}` | "
            f"{'Y' if r.get('round_trip_ok') else 'n'} | "
            f"{'Y' if r.get('executed_ok') else 'n'} | "
            f"{r.get('executor_mode', '—')} | "
            f"{r.get('exec_seconds', 0.0):.2f}s | "
            f"{r.get('seconds', 0.0):.2f}s |"
        )
    a("")

    a("## Re-run")
    a("")
    a("```sh")
    a(
        f"pixi run toolcalling-01-test -- --model {model_alias} "
        f"--temperature {meta.get('temperature', 0.1)}"
    )
    a("pixi run toolcalling-01-report")
    a("```")
    a("")
    a(
        "Artifacts for this report:"
        if os.path.isdir(os.path.join(RUNS_DIR, run_id))
        else "Artifacts:"
    )
    a("")
    a(f"- `datasets/toolcalling-01/runs/{run_id}/results.json` — raw rows")
    a(f"- `datasets/toolcalling-01/runs/{run_id}/eval.json` — scored scenarios")
    a(f"- `datasets/toolcalling-01/runs/{run_id}/report.md` — this report")
    a("- latest copies: `datasets/toolcalling-01/results.json`, `eval.json`")
    a("")
    a("---")
    a("")
    a(
        f"*Rendered by `smoketests/toolcalling-01/report.py` "
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
