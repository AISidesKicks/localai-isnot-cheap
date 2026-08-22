#!/usr/bin/env python3
"""Generate the cinematic-01 micro dataset: 10 parody studios x 20 fake films.

Each entry is a generated blurb: invented title, fake release year and a
comedic premise, produced by the llama.cpp-backed LFM2.5-2.6B through the
LiteLLM gateway (alias `local-gguf`). Every request is sent with `"cache": {}`
so LiteLLM's Redis cache is enabled; the dataset records the cache regime each
call landed in (`x-litellm-cache-key` response header present = Redis hit).

The model runs with deepseek-style reasoning (`--reasoning on`), which eats
the whole output budget before any answer if left alone. The prompt tells it
to skip the thinking phase; we still take `content` first and fall back to
`reasoning_content`, and best-effort extract a title + year from the text.

Stdlib only (urllib), so it runs on any box with a python3.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

STUDIOS = [
    {"name": "marwell", "parody_of": "Marvel Studios"},
    {"name": "parampout", "parody_of": "Paramount / DreamWorks Animation"},
    {"name": "deesee", "parody_of": "DC Studios"},
    {"name": "soney", "parody_of": "Sony Pictures"},
    {"name": "netflop", "parody_of": "Netflix"},
    {"name": "dismey", "parody_of": "Disney"},
    {"name": "warbler", "parody_of": "Warner Bros"},
    {"name": "univurse", "parody_of": "Universal Pictures"},
    {"name": "lionheats", "parody_of": "Lionsgate"},
    {"name": "foxelle", "parody_of": "20th Century Fox"},
]

MODEL = "local-gguf"
DEFAULT_BASE_URL = "http://localhost:4000"
DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "cinematic-01-dataset.json",
)
CACHE_PARAM = {}  # enabled LiteLLM Redis caching; boolean True 400s on 1.98.0

DEFAULT_MAX_TOKENS = 700
MAX_TRIES = 2
TIMEOUT_S = 120
BLURB_CAP = 1200


def get_master_key(repo_root):
    """Master key: exported env var wins, then docker/.env, else demo default."""
    key = os.environ.get("LITELLM_MASTER_KEY")
    if key:
        return key.strip().strip('"').strip("'")
    env_file = os.path.join(repo_root, "docker", ".env")
    try:
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("LITELLM_MASTER_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    print("WARNING: LITELLM_MASTER_KEY not found, using demo default", file=sys.stderr)
    return "sk-1234-master-key-4321"


def get_repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def health(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def chat_call(base_url, bearer, content, max_tokens):
    """Single chat completion through LiteLLM; returns (resp_json, headers, seconds)."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "cache": CACHE_PARAM,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + bearer,
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            headers = {k.lower(): v for k, v in resp.headers.items()}
        return payload, headers, time.perf_counter() - t0
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def response_text(payload):
    """Model answer: `content` first, then the reasoning trace fallback."""
    choices = payload.get("choices") or []
    message = (choices[0] or {}).get("message") or {} if choices else {}
    text = message.get("content") or ""
    if not text.strip():
        text = message.get("reasoning_content") or ""
    return text.strip()[:BLURB_CAP]


def extract_metadata(text):
    """Best-effort title + year out of free-form prose."""
    year = None
    m = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", text)
    if m:
        year = int(m.group(1))
    title = None
    lines = [ln.strip(" *#-–•\"'") for ln in text.splitlines() if ln.strip()]
    if lines:
        candidate = lines[0].rstrip(".")
        title = (
            candidate
            if len(candidate) <= 120
            else re.split(r"[.!?]\s", candidate, maxsplit=1)[0][:120]
        )
    return title or None, year


def generate_blurb(base_url, bearer, studio, slot, films_per_studio, max_tokens):
    prompt = (
        "IMPORTANT: Do NOT plan, do NOT think aloud, do NOT reason. Just answer now.\n\n"
        "You work at a parody film studio. "
        f"Studio: {studio['name']} (parodies {studio['parody_of']}). "
        f"Write a blurb for parody film entry #{slot} of {films_per_studio}: one line "
        "with the invented movie title, then 2-3 sentences with a fake release year "
        "and the comedic premise. No markdown."
    )
    last_err = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            payload, headers, seconds = chat_call(base_url, bearer, prompt, max_tokens)
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(1.0 * attempt)
            continue
        text = response_text(payload)
        if text:
            return text, prompt, None, seconds, headers, payload
        last_err = "empty response text"
        time.sleep(0.5)
    return "", prompt, last_err, 0.0, {}, {}


def usage_fields(payload):
    usage = (payload or {}).get("usage") or {}
    timings = (payload or {}).get("timings") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cache_n": timings.get("cache_n"),
        "prompt_n": timings.get("prompt_n"),
    }


def write_dataset(entries, target_studios, args, t_start):
    """Build + atomically write the dataset JSON; used for checkpointing too."""
    ok = sum(1 for e in entries if e["ok"])
    dataset = {
        "meta": {
            "name": "cinematic-01",
            "generator": "smoketests/cinematic-01-generate.py",
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model_alias": MODEL,
            "cache_param": dict(CACHE_PARAM),
            "studios": len(target_studios),
            "films_per_studio": args.films,
            "total_expected": len(target_studios) * args.films,
            "total": len(entries),
            "ok": ok,
            "failed": len(entries) - ok,
            "elapsed_s": round(time.perf_counter() - t_start, 1),
            "complete": len(entries) == len(target_studios) * args.films,
        },
        "studios": target_studios,
        "films": entries,
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    tmp = args.output + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, args.output)
    return dataset


def main():
    parser = argparse.ArgumentParser(
        description="Generate the cinematic-01 micro dataset."
    )
    parser.add_argument(
        "--films", type=int, default=20, help="films per studio (default 20)"
    )
    parser.add_argument(
        "--studios",
        type=int,
        default=len(STUDIOS),
        help="studios to cover (default all)",
    )
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="LiteLLM gateway URL"
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="dataset JSON path")
    parser.add_argument(
        "--skip-health", action="store_true", help="skip pre-flight health checks"
    )
    args = parser.parse_args()

    repo_root = get_repo_root()
    bearer = get_master_key(repo_root)
    target_studios = STUDIOS[: args.studios]

    if not args.skip_health:
        if not health(args.base_url + "/health/readiness"):
            sys.exit(f"gateway not ready at {args.base_url}/health/readiness")
        engine = (
            args.base_url.replace(":4000", ":8080")
            if ":4000" in args.base_url
            else "http://localhost:8080"
        )
        if not health(engine + "/health"):
            sys.exit(f"llama.cpp engine not ready at {engine}/health")
    print(
        f"gateway {args.base_url} healthy; generating {len(target_studios)}x{args.films} films"
    )

    entries = []
    t_start = time.perf_counter()
    for studio in target_studios:
        t_studio = time.perf_counter()
        for slot in range(1, args.films + 1):
            text, prompt, error, seconds, headers, payload = generate_blurb(
                args.base_url, bearer, studio, slot, args.films, args.max_tokens
            )
            cache_hit = "x-litellm-cache-key" in headers
            title, year = extract_metadata(text)
            entry = {
                "id": f"{studio['name']}-{slot:02d}",
                "studio": studio["name"],
                "parody_of": studio["parody_of"],
                "slot": slot,
                "cache_param": dict(CACHE_PARAM),
                "cache_regime": "litellm-redis-hit"
                if cache_hit
                else "litellm-redis-miss",
                "ok": bool(text),
                "title": title,
                "year": year,
                "blurb": text,
                "prompt": prompt,
                "usage": usage_fields(payload),
                "seconds": round(seconds, 3),
            }
            if error:
                entry["error"] = error
            entries.append(entry)
            state = "ok " if entry["ok"] else "FAIL"
            print(
                f"  {entry['id']:<14} {state} {entry['seconds']:>6.2f}s "
                f"{entry['cache_regime']:<19} title={entry['title']!r}",
                flush=True,
            )
        print(
            f"studio {studio['name']} done in {time.perf_counter() - t_studio:.1f}s",
            flush=True,
        )
        dataset = write_dataset(entries, target_studios, args, t_start)  # checkpoint
        print(
            f"  checkpoint: {len(entries)}/{dataset['meta']['total_expected']} entries -> {args.output}",
            flush=True,
        )

    dataset = write_dataset(entries, target_studios, args, t_start)
    print(
        f"\nwrote {args.output}: {len(entries)} entries, {dataset['meta']['ok']} ok, "
        f"{dataset['meta']['failed']} failed, {dataset['meta']['elapsed_s']}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
