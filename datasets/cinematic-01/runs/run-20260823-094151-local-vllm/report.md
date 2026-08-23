# cinematic-01 smoke run: run-20260823-094151-local-vllm

- **model**: `local-vllm` — LFM2.5-2.6B W8A16 (vLLM)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, vLLM (W8A16, prefix cache))
- **cache mode**: `both` — all modes
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `154` rows (round-robin across studios)
- **mode**: `disabled` reasoning, `4` workers
- **run_at**: `2026-08-23T09:49:40+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **47/154** (30%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **132/154** (86%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.61** | 0.8 | **FAIL** |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 154 | 43 | 111 | 60329 | 1.83s |
| 2 | 154 | 7 | 147 | 52069 | 2.14s |
| 3 | 154 | 47 | 107 | 64682 | 1.66s |

## Cache demo — per-mode prefix/Redis reuse

| Mode | Call | Prompt | Regime | Latency | engine cached_tokens |
|------|------|--------|--------|---------|---------------------|
| 1level | base 1 | variant | `litellm-redis-miss` | 1.9070s | — |
| 1level | base 2 | variant | `litellm-redis-miss` | 1.8920s | — |
| 1level | base 3 | variant | `litellm-redis-miss` | 1.8920s | — |
| 2level | Q1 | base | `litellm-redis-miss` | 1.9123s | — |
| 2level | Q2 | base | `litellm-redis-hit` | 0.0060s | — |
| 2level | Q3 | variant | `litellm-redis-miss` | 1.8946s | — |
| no-cache | N1 | variant | `litellm-redis-miss` | 1.9135s | — |
| no-cache | N2 | variant | `litellm-redis-miss` | 1.9110s | — |
| no-cache | N3 | variant | `litellm-redis-miss` | 1.9124s | — |

| Mode | vLLM prefix-cache Δ hits | Δ queries |
|------|--------------------------|-----------|
| 1level | 32 | 72 |
| 2level | 16 | 47 |
| no-cache | 0 | 62 |

In 2level, call Q2 reuses the Q1 response from Redis — the engine does no work. In 1level (LiteLLM bypassed) and no-cache, the `engine cached_tokens` column shows how many prompt tokens the engine replayed from its prefix cache (vLLM) or recomputed.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. Pictures |
| Walt Disney Pictures | The Lion King | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Dark Knight Rises | Warner Bros. |
| Universal Pictures | Jurassic Park | Amblin Entertainment |
| Paramount Pictures | Star Wars: Episode IV – A New Hope | 20th Century Fox |
| Sony Pictures | Spider-Man: Into the Spider-Verse | Sony Pictures Animation |
| Columbia Pictures | Gone with the Wind | Metro-Goldwyn-Mayer |
| 20th Century Studios | Ratatouille | Pixar Animation Studios |
| Lionsgate Films | The Fast and the Furious | 20th Century Fox |
| A24 | Get Out | 20th Century Fox |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| Focus Features | The Last Samurai | Columbia Pictures |
| Searchlight Pictures | Sully | — |
| Netflix | The Irishman | Universal Pictures |
| Marvel Studios | The Incredible Hulk | — |
| DC Studios | Batman v Superman: Dawn of Justice | — |
| Walt Disney Pictures | Frozen | Walt Disney Animation Studios |
| Warner Bros. Pictures | Harry Potter and the Sorcerer's Stone | Warner Bros. |
| Universal Pictures | The Godfather | Paramount Pictures |
| Paramount Pictures | The Sound of Music | Walt Disney Pictures |
| Columbia Pictures | Home Alone | Universal Pictures |
| 20th Century Studios | Cars | Pixar Animation Studios |
| Lionsgate Films | The Fast & Furious 7 | Universal Pictures |
| Legendary Entertainment | Furious 7 | Universal Pictures |
| New Line Cinema | The Big Lebowski | The Coen Brothers |
| Focus Features | The Mummy | Universal Pictures |
| Searchlight Pictures | Dunkirk | Legendary Pictures |
| DC Studios | Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Little Mermaid | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Fellowship of the Ring | New Line Cinema |
| Universal Pictures | Titanic | 20th Century Fox |
| Paramount Pictures | The Exorcist | Universal Pictures |
| Sony Pictures | Gravity | Paramount Pictures |
| Columbia Pictures | The Last of the Mohicans | — |
| Lionsgate Films | Transformers | Paramount Pictures |
| Metro-Goldwyn-Mayer | Casablanca | Warner Bros. |
| Legendary Entertainment | The Suicide Squad | Warner Bros. Pictures |
| New Line Cinema | The Departed | — |
| Focus Features | The Great Gatsby | Warner Bros. |
| Searchlight Pictures | The Imitation Game | Warner Bros. Pictures |
| Netflix | Bird Box | — |
| DC Studios | Wonder Woman | Warner Bros. Pictures |
| Walt Disney Pictures | Aladdin | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Two Towers | New Line Pictures |
| Universal Pictures | E.T. the Extra-Terrestrial | Paramount Pictures |
| Paramount Pictures | The Shining | — |
| Sony Pictures | The Lost City | — |
| Lionsgate Films | Transformers: Dark of the Moon | — |
| A24 | Us | Netflix |
| Metro-Goldwyn-Mayer | Mutiny on the Bounty | — |
| Legendary Entertainment | The Hobbit: The Desolation of Smaug | Warner Bros. |
| New Line Cinema | Pirates of the Caribbean: The Curse of the Black Pearl | Warner Bros. Pictures |
| Focus Features | The Martian | Red Bull Films |
| Searchlight Pictures | The Big Short | — |
| Netflix | The Gray Man | Paramount Pictures |
| DC Studios | Aquaman | Warner Bros. Pictures |
| Walt Disney Pictures | Beauty and the Beast | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Return of the King | — |
| Universal Pictures | The Super Mario Bros. Movie | Illumination |
| Paramount Pictures | The Ten Commandments | Metro-Goldwyn-Mayer |
| Sony Pictures | Creed | Columbia Pictures |
| Lionsgate Films | The Hunger Games | — |
| A24 | Tár | — |
| Metro-Goldwyn-Mayer | The Philadelphia Story | MGM |
| Legendary Entertainment | The Avengers: Age of Ultron | Marvel Studios |
| Focus Features | The Incredible Burt Wonderstone | Paramount Pictures |
| Netflix | The Old Guard | — |
| DC Studios | Shazam! | Warner Bros. Pictures |
| Walt Disney Pictures | Mulan | Walt Disney Studios |
| Pixar Animation Studios | Brave | Walt Disney Animation Studios |
| Warner Bros. Pictures | Batman Begins | — |
| Universal Pictures | Fast & Furious | New Line Cinema |
| Paramount Pictures | The Great Escape | Columbia Pictures |
| Sony Pictures | Alita: Battle Angel | Lightstorm Entertainment |
| Lionsgate Films | John Carter | Walt Disney Pictures |
| A24 | The Witch | — |
| New Line Cinema | The Social Network | — |
| Focus Features | The Adventures of Tintin | Studio 100 |
| Netflix | Don't Look Up | A24 |
| DC Studios | The Flash | Warner Bros. Pictures |
| Walt Disney Pictures | Toy Story | Pixar Animation Studios |
| Warner Bros. Pictures | Man of Steel | Warner Bros. |
| Universal Pictures | Back to the Future | Polaris Pictures |
| Sony Pictures | Venom | Marvel Studios |
| Lionsgate Films | The Expendables | Regency Entertainment |
| Focus Features | The Chronicles of Narnia: The Lion, the Witch and the Wardrobe | Walden Media |
| Netflix | The Power of the Dog | — |
| DC Studios | Zack Snyder's Justice League | Warner Bros. Pictures |
| Universal Pictures | The Wizard of Oz | Metro-Goldwyn-Mayer |
| Sony Pictures | Joy | — |
| DreamWorks Animation | Chicken Run | Aardman Animations |
| Lionsgate Films | The Mummy (2001) | Twentieth Century Fox |
| A24 | The Florida Project | — |
| Studio Ghibli | The Secret World of Arrietty | Ghibli Studios |
| Focus Features | The Hobbit: An Unexpected Journey | New Line Cinema |
| Netflix | The Fabelmans | — |
| DC Studios | The Batman | Warner Bros. Pictures |
| Walt Disney Pictures | Wreck-It Ralph | Walt Disney Animation Studios |
| Universal Pictures | Scooby-Doo | Warner Bros. |
| Sony Pictures | The Girl with the Dragon Tattoo | Fazer Film |
| Lionsgate Films | The Mummy: Tomb of the Dragon Emperor | Twentieth Century Fox |
| Focus Features | The Secret Life of Walter Mitty | 20th Century Fox |
| DC Studios | Shazam! Fury of the Gods | — |
| Walt Disney Pictures | Moana | Walt Disney Animation Studios |
| Lionsgate Films | The Mummy (2017) | Universal Pictures |
| A24 | The Menu | — |
| Studio Ghibli | From Up on Poppy Hill | Maggie's Poppies |

## Re-run

```sh
pixi run cinematic-01-test -- --model local-vllm --cache-mode both
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260823-094151-local-vllm/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260823-094151-local-vllm/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260823-094151-local-vllm/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-23T09:49:53+0200.*
