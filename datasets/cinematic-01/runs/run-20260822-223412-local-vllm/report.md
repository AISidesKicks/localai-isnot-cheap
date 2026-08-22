# cinematic-01 smoke run: run-20260822-223412-local-vllm

- **model**: `local-vllm` — LFM2.5-2.6B W8A16 (vLLM)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, vLLM (W8A16, prefix cache))
- **cache mode**: `both` — all modes
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `154` rows (round-robin across studios)
- **mode**: `disabled` reasoning, `4` workers
- **run_at**: `2026-08-22T22:41:49+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **51/154** (33%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **134/154** (87%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.623** | 0.8 | **FAIL** |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 154 | 20 | 134 | 58536 | 2.09s |
| 2 | 154 | 6 | 148 | 51600 | 2.06s |
| 3 | 154 | 41 | 113 | 64118 | 1.75s |

## Cache demo — per-mode prefix/Redis reuse

| Mode | Call | Prompt | Regime | Latency | engine cached_tokens |
|------|------|--------|--------|---------|---------------------|
| 1level | base 1 | variant | `litellm-redis-miss` | 1.8817s | — |
| 1level | base 2 | variant | `litellm-redis-miss` | 1.8637s | — |
| 1level | base 3 | variant | `litellm-redis-miss` | 1.8668s | — |
| 2level | Q1 | base | `litellm-redis-miss` | 1.8880s | — |
| 2level | Q2 | base | `litellm-redis-hit` | 0.0068s | — |
| 2level | Q3 | variant | `litellm-redis-miss` | 1.8765s | — |
| no-cache | N1 | variant | `litellm-redis-miss` | 1.8807s | — |
| no-cache | N2 | variant | `litellm-redis-miss` | 1.8816s | — |
| no-cache | N3 | variant | `litellm-redis-miss` | 1.8885s | — |

| Mode | vLLM prefix-cache Δ hits | Δ queries |
|------|--------------------------|-----------|
| 1level | 32 | 72 |
| 2level | 16 | 47 |
| no-cache | 0 | 62 |

In 2level, call Q2 reuses the Q1 response from Redis — the engine does no work. In 1level (LiteLLM bypassed) and no-cache, the `engine cached_tokens` column shows how many prompt tokens the engine replayed from its prefix cache (vLLM) or recomputed.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. |
| Walt Disney Pictures | The Lion King | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Dark Knight Rises | Warner Bros. |
| Universal Pictures | Jurassic Park | Amblin Entertainment |
| Paramount Pictures | Star Wars: Episode IV – A New Hope | 20th Century Fox |
| Sony Pictures | Spider-Man: Into the Spider-Verse | Sony Pictures Animation |
| Columbia Pictures | Gone with the Wind | Metro-Goldwyn-Mayer |
| 20th Century Studios | Ratatouille | Pixar Animation Studios |
| Lionsgate Films | The Fast and the Furious | Lightstorm Entertainment |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| Focus Features | The Last Samurai | — |
| Searchlight Pictures | Sully | Paramount Pictures |
| Netflix | The Irishman | Universal Pictures |
| DC Studios | Batman v Superman: Dawn of Justice | Warner Bros. Pictures |
| Walt Disney Pictures | Frozen | Walt Disney Animation Studios |
| Warner Bros. Pictures | Harry Potter and the Sorcerer's Stone | Warner Bros. |
| Universal Pictures | The Godfather | Paramount Pictures |
| Paramount Pictures | The Sound of Music | Walt Disney Productions |
| Columbia Pictures | Home Alone | Universal Pictures |
| 20th Century Studios | Cars | Pixar Animation Studios |
| Lionsgate Films | The Fast & Furious 7 | Paramount Pictures |
| Legendary Entertainment | Furious 7 | Lightstorm Entertainment |
| Focus Features | The Mummy | Twentieth Century Fox |
| Searchlight Pictures | Dunkirk | — |
| DC Studios | Justice League | Warner Bros. |
| Walt Disney Pictures | The Little Mermaid | Walt Disney Feature Animation |
| Warner Bros. Pictures | The Lord of the Rings: The Fellowship of the Ring | New Line Cinema |
| Universal Pictures | Titanic | 20th Century Fox |
| Paramount Pictures | The Exorcist | American International Pictures |
| Sony Pictures | Gravity | Paramount Pictures |
| Columbia Pictures | The Last of the Mohicans | — |
| Lionsgate Films | Transformers | Paramount Pictures |
| Metro-Goldwyn-Mayer | Casablanca | Warner Bros. Pictures |
| Legendary Entertainment | The Suicide Squad | Warner Bros. Pictures |
| New Line Cinema | The Departed | Fox Searchlight Pictures |
| Focus Features | The Great Gatsby | Columbia Pictures |
| Searchlight Pictures | The Imitation Game | Open Road Films |
| Netflix | Bird Box | Blumhouse Productions |
| DC Studios | Wonder Woman | Warner Bros. Pictures |
| Walt Disney Pictures | Aladdin | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Two Towers | New Line Cinema |
| Universal Pictures | E.T. the Extra-Terrestrial | Paramount Pictures |
| Paramount Pictures | The Shining | Universal Pictures |
| Sony Pictures | The Lost City | Paramount Pictures |
| Lionsgate Films | Transformers: Dark of the Moon | Paramount Pictures |
| Metro-Goldwyn-Mayer | Mutiny on the Bounty | RKO Pictures |
| Legendary Entertainment | The Hobbit: The Desolation of Smaug | Warner Bros. Pictures |
| New Line Cinema | Pirates of the Caribbean: The Curse of the Black Pearl | Warner Bros. |
| Focus Features | The Martian | — |
| Searchlight Pictures | The Big Short | — |
| Netflix | The Gray Man | — |
| DC Studios | Aquaman | Warner Bros. Pictures |
| Walt Disney Pictures | Beauty and the Beast | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Return of the King | New Line Pictures |
| Universal Pictures | The Super Mario Bros. Movie | Illumination |
| Paramount Pictures | The Ten Commandments | 20th Century Fox |
| Sony Pictures | Creed | Columbia Pictures |
| Lionsgate Films | The Hunger Games | — |
| A24 | Tár | — |
| Metro-Goldwyn-Mayer | The Philadelphia Story | 20th Century Fox |
| Legendary Entertainment | The Avengers: Age of Ultron | Marvel Studios |
| New Line Cinema | Memento | The Film Company |
| Focus Features | The Incredible Burt Wonderstone | Paramount Pictures |
| Netflix | The Old Guard | Warner Bros. Pictures |
| DC Studios | Shazam! | Warner Bros. Pictures |
| Walt Disney Pictures | Mulan | Walt Disney Animation Studios |
| Warner Bros. Pictures | Batman Begins | Warner Bros. |
| Universal Pictures | Fast & Furious | New Line Cinema |
| Paramount Pictures | The Great Escape | Columbia Pictures |
| Sony Pictures | Alita: Battle Angel | Lightstorm Entertainment |
| Lionsgate Films | John Carter | Walt Disney Pictures |
| New Line Cinema | The Social Network | Columbia Pictures |
| Focus Features | The Adventures of Tintin | — |
| Netflix | Don't Look Up | — |
| DC Studios | The Flash | Warner Bros. Pictures |
| Walt Disney Pictures | Toy Story | Pixar Animation Studios |
| Universal Pictures | Back to the Future | Paramount Pictures |
| Sony Pictures | Venom | Marvel Studios |
| DreamWorks Animation | The Prince of Egypt | DreamWorks SKG |
| Lionsgate Films | The Expendables | 20th Century Fox |
| Focus Features | The Chronicles of Narnia: The Lion, the Witch and the Wardrobe | Walden Media |
| Netflix | The Power of the Dog | — |
| DC Studios | Zack Snyder's Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Princess and the Frog | Walt Disney Animation Studios |
| Universal Pictures | The Wizard of Oz | Metro-Goldwyn-Mayer |
| Sony Pictures | Joy | Universal Pictures |
| DreamWorks Animation | Chicken Run | Aardman Animations |
| Lionsgate Films | The Mummy (2001) | Colossal Entertainment |
| A24 | The Florida Project | — |
| Focus Features | The Hobbit: An Unexpected Journey | Warner Bros. Pictures |
| Netflix | The Fabelmans | — |
| DC Studios | The Batman | Warner Bros. Pictures |
| Walt Disney Pictures | Wreck-It Ralph | Walt Disney Animation Studios |
| Universal Pictures | Scooby-Doo | Warner Bros. |
| Sony Pictures | The Girl with the Dragon Tattoo | — |
| Lionsgate Films | The Mummy: Tomb of the Dragon Emperor | Twentieth Century Fox |
| A24 | The Night House | — |
| Focus Features | The Secret Life of Walter Mitty | — |
| DC Studios | Shazam! Fury of the Gods | — |
| Walt Disney Pictures | Moana | Walt Disney Animation Studios |
| Lionsgate Films | The Mummy (2017) | — |
| A24 | The Menu | — |
| Studio Ghibli | From Up on Poppy Hill | — |

## Re-run

```sh
pixi run cinematic-01-test -- --model local-vllm --cache-mode both
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260822-223412-local-vllm/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260822-223412-local-vllm/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260822-223412-local-vllm/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-22T22:43:07+0200.*
