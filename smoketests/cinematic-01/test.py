#!/usr/bin/env python3
"""cinematic-01 smoke test: studio recall, film+year match, year repeat + cache demo.

Reads the generated CSV (datasets/cinematic-01-dataset.csv) as ground truth
(studio names seeded, films/years model-generated — see design.md) and evaluates
the model against it:

  1. studio recall   — which studio produced a film (schema answer via StudioList)
  2. film+year match — model's year for a film within +/-2 of the dataset year
  3. year repeat     — deepeval ExactMatchMetric (threshold 0.8) over reworded
                       year prompts, so fresh Redis misses instead of hits
  + the preserved 3-repeat cache demo (Q1 redis miss, Q2 hit, Q3 suffix miss
    with llama.cpp KV reuse visible in timings.cache_n)

Writes datasets/cinematic-01-results.json (raw rows) and
datasets/cinematic-01-eval.json (scored scenarios).
"""

import argparse
import csv
import json
import os
import re
import sys
import time

from deepeval.metrics.exact_match.exact_match import ExactMatchMetric
from deepeval.test_case import LLMTestCase
from llm import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_TOKENS,
    MODEL,
    StudioList,
    YearAnswer,
    cache_regime,
    chat,
    completion_text,
    get_repo_root,
    health,
    timings,
    usage_fields,
)

YEAR_TOLERANCE = 2
REMINDER = "Please answer again:"

BASE_PROMPT = "Give me a short summary about Marvel Cinematic Universe."
Q3_SUFFIX = " - 3rd repeat"

DEFAULT_CSV = os.path.join(get_repo_root(), "datasets", "cinematic-01-dataset.csv")
RESULTS_PATH = os.path.join(get_repo_root(), "datasets", "cinematic-01-results.json")
EVAL_PATH = os.path.join(get_repo_root(), "datasets", "cinematic-01-eval.json")


def normalize(name):
    """Case/punctuation-insensitive token for comparing answers to studios."""
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def parse_model(text, schema):
    """Best-effort schema parse; None on malformed output."""
    if not text:
        return None
    try:
        return schema.model_validate_json(text)
    except Exception:  # noqa: BLE001 - malformed answers count as misses
        return None


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            year = (raw["year"] or "").strip()
            rows.append(
                {
                    "studio": raw["studio name"].strip(),
                    "film": raw["film name"].strip(),
                    "year": int(year) if year else None,
                }
            )
    return rows


def sample_rows(rows, n):
    """Up to n rows spread across studios (round-robin) for a sane smoke budget."""
    buckets = {}
    order = []
    for row in rows:
        if row["studio"] not in buckets:
            buckets[row["studio"]] = []
            order.append(row["studio"])
        buckets[row["studio"]].append(row)
    picked = []
    while len(picked) < n and any(buckets[s] for s in order):
        for studio in order:
            if len(picked) == n:
                break
            if buckets[studio]:
                picked.append(buckets[studio].pop(0))
    return picked


def scenario_studio_recall(sample, args):
    """Which studio produced each sampled film; exact normalized name match."""
    rows = []
    for row in sample:
        prompt = (
            f'Which studio produced the movie "{row["film"]}"? Reply with a '
            "JSON object listing one studio name."
        )
        resp, seconds = chat(
            prompt,
            max_tokens=args.max_tokens,
            response_format=StudioList,
        )
        text = completion_text(resp)
        parsed = parse_model(text, StudioList)
        guess = parsed.studios[0] if parsed else None
        correct = guess is not None and normalize(guess) == normalize(row["studio"])
        rows.append(
            {
                "studio": row["studio"],
                "film": row["film"],
                "guess": guess,
                "answer": text[:200],
                "correct": correct,
                "cache_regime": cache_regime(resp),
                "seconds": round(seconds, 3),
                "usage": usage_fields(resp),
            }
        )
        print(
            f"  recall {row['studio']:<28} -> {guess or '?'}"
            f"{'  OK' if correct else '  miss'} {round(seconds, 2)}s",
            flush=True,
        )
    correct = sum(1 for r in rows if r["correct"])
    return rows, correct


def scenario_year_match(sample, args):
    """Model's year for each film, within +/-2 of the dataset year."""
    rows = []
    for row in sample:
        if row["year"] is None:
            continue
        prompt = (
            f'In what year was the movie "{row["film"]}" released? Reply with '
            "a JSON object with the title and the year."
        )
        resp, seconds = chat(
            prompt,
            max_tokens=args.max_tokens,
            response_format=YearAnswer,
        )
        text = completion_text(resp)
        parsed = parse_model(text, YearAnswer)
        year = parsed.year if parsed else None
        ok = year is not None and abs(year - row["year"]) <= YEAR_TOLERANCE
        rows.append(
            {
                "studio": row["studio"],
                "film": row["film"],
                "expected": row["year"],
                "predicted": year,
                "correct": ok,
                "answer": text[:200],
                "cache_regime": cache_regime(resp),
                "seconds": round(seconds, 3),
                "usage": usage_fields(resp),
            }
        )
        print(
            f"  year   {row['film']:<40} {row['year']} vs {year}"
            f" {'OK' if ok else 'miss'} {round(seconds, 2)}s",
            flush=True,
        )
    correct = sum(1 for r in rows if r["correct"])
    return rows, correct


def scenario_year_repeat(sample, args, threshold):
    """Reworded year re-answer scored with deepeval ExactMatchMetric."""
    metric = ExactMatchMetric(threshold=threshold)
    rows = []
    for row in sample:
        if row["year"] is None:
            continue
        prompt = (
            f'{REMINDER} what year was the movie "{row["film"]}" released? '
            "Reply with a JSON object with the title and the year."
        )
        resp, seconds = chat(
            prompt,
            max_tokens=args.max_tokens,
            response_format=YearAnswer,
        )
        text = completion_text(resp)
        parsed = parse_model(text, YearAnswer)
        year = parsed.year if parsed else None
        predicted = str(year) if year is not None else ""
        metric.measure(
            LLMTestCase(
                input=prompt,
                actual_output=predicted,
                expected_output=str(row["year"]),
            )
        )
        row_out = {
            "studio": row["studio"],
            "film": row["film"],
            "expected": str(row["year"]),
            "predicted": predicted,
            "metric_score": metric.score,
            "answer": text[:200],
            "cache_regime": cache_regime(resp),
            "seconds": round(seconds, 3),
            "usage": usage_fields(resp),
        }
        rows.append(row_out)
        print(
            f"  repeat {row['film']:<40} {row['year']} vs {predicted}"
            f" {'OK' if metric.score == 1.0 else 'miss'} {round(seconds, 2)}s",
            flush=True,
        )
    score = sum(r["metric_score"] for r in rows) / len(rows) if rows else 0.0
    return rows, score, score >= threshold


def cache_demo(args):
    """Preserved 3-repeat demo: identical base prompt, then a suffix variant."""
    calls = [
        {"call": "Q1", "content": BASE_PROMPT},
        {"call": "Q2", "content": BASE_PROMPT},
        {"call": "Q3", "content": BASE_PROMPT + Q3_SUFFIX},
    ]
    rows = []
    for spec in calls:
        resp, seconds = chat(spec["content"], max_tokens=256)
        regime = cache_regime(resp)
        row = {
            "call": spec["call"],
            "observed_regime": regime,
            "base_only": spec["content"] == BASE_PROMPT,
            "seconds": round(seconds, 4),
            "usage": usage_fields(resp),
            "timings": timings(resp),
            "content_head": completion_text(resp)[:160],
        }
        rows.append(row)
        print(
            f"  {row['call']} {regime:<20} {round(seconds, 4):>8.4f}s "
            f"cache_n={row['timings'].get('cache_n')}",
            flush=True,
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Run the cinematic-01 smoke test.")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="dataset CSV path")
    parser.add_argument(
        "--sample",
        type=int,
        default=20,
        help="films to probe per scenario (default 20)",
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--threshold", type=float, default=0.8, help="ExactMatchMetric threshold"
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="LiteLLM gateway URL"
    )
    parser.add_argument("--results", default=RESULTS_PATH, help="raw results JSON path")
    parser.add_argument("--eval", default=EVAL_PATH, help="scored eval JSON path")
    parser.add_argument("--skip-health", action="store_true", help="skip health probes")
    args = parser.parse_args()

    if not args.skip_health and not health(args.base_url + "/health/readiness"):
        sys.exit(f"gateway not ready at {args.base_url}/health/readiness")
    print(f"gateway {args.base_url} healthy; dataset {args.csv}")

    rows = load_rows(args.csv)
    if not rows:
        sys.exit("empty dataset; run cinematic-01-generate first")
    sample = sample_rows(rows, args.sample)
    print(f"{len(rows)} rows loaded, sampling {len(sample)} ({args.sample})")

    recall, recall_ok = scenario_studio_recall(sample, args)
    print(f"scenario 1 studio recall: {recall_ok}/{len(recall)}")

    year_match, year_ok = scenario_year_match(sample, args)
    print(f"scenario 2 year match (+/-{YEAR_TOLERANCE}): {year_ok}/{len(year_match)}")

    year_repeat, exact_score, exact_passed = scenario_year_repeat(
        sample, args, args.threshold
    )
    print(
        f"scenario 3 year repeat ExactMatchMetric: {exact_score:.2f} "
        f"({'PASS' if exact_passed else 'FAIL'})"
    )

    demo = cache_demo(args)
    print("cache demo Q1/Q2/Q3 done")

    meta = {
        "name": "cinematic-01",
        "test": "smoketests/cinematic-01/test.py",
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model_alias": MODEL,
        "base_url": args.base_url,
        "dataset": args.csv,
        "sample": len(sample),
        "year_tolerance": YEAR_TOLERANCE,
    }
    results = {
        "meta": meta,
        "scenario_1_studio_recall": {
            "score": f"{recall_ok}/{len(recall)}",
            "rows": recall,
        },
        "scenario_2_year_match": {
            "score": f"{year_ok}/{len(year_match)}",
            "rows": year_match,
        },
        "scenario_3_year_repeat": {
            "score": f"{exact_score:.2f}",
            "rows": year_repeat,
        },
        "cache_demo": {"rows": demo},
    }
    eval_summary = {
        "meta": meta,
        "scenario_1_studio_recall": {
            "metric": "manual exact match",
            "score": f"{recall_ok}/{len(recall)}",
            "fraction": round(recall_ok / len(recall), 3) if recall else 0.0,
        },
        "scenario_2_year_match": {
            "metric": f"abs diff <= {YEAR_TOLERANCE}",
            "score": f"{year_ok}/{len(year_match)}",
            "fraction": round(year_ok / len(year_match), 3) if year_match else 0.0,
        },
        "scenario_3_year_repeat": {
            "metric": "deepeval.ExactMatchMetric",
            "threshold": args.threshold,
            "score": round(exact_score, 3),
            "passed": exact_passed,
        },
    }
    os.makedirs(os.path.dirname(args.results), exist_ok=True)
    with open(args.results, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    with open(args.eval, "w", encoding="utf-8") as fh:
        json.dump(eval_summary, fh, indent=2, ensure_ascii=False)
    print(f"wrote {args.results} and {args.eval}")


if __name__ == "__main__":
    main()
