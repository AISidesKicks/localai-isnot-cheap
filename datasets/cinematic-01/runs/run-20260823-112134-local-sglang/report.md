# cinematic-01 smoke run: run-20260823-112134-local-sglang

- **model**: `local-sglang` — LFM2.5-2.6B W8A16 (SGLang)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, SGLang (W8A16))
- **cache mode**: `both` — all modes
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `154` rows (round-robin across studios)
- **mode**: `disabled` reasoning, `4` workers
- **run_at**: `2026-08-23T11:31:57+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **51/154** (33%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **134/154** (87%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.844** | 0.8 | PASS |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 154 | 0 | 154 | 56625 | 5.73s |
| 2 | 154 | 0 | 154 | 51980 | 3.62s |
| 3 | 154 | 0 | 154 | 59056 | 5.12s |

## Cache demo — per-mode prefix/Redis reuse

| Mode | Call | Prompt | Regime | Latency | engine cached_tokens |
|------|------|--------|--------|---------|---------------------|
| 1level | base 1 | variant | `litellm-redis-miss` | 2.4670s | — |
| 1level | base 2 | variant | `litellm-redis-miss` | 2.4050s | — |
| 1level | base 3 | variant | `litellm-redis-miss` | 2.4095s | — |
| 2level | Q1 | base | `litellm-redis-miss` | 2.3978s | — |
| 2level | Q2 | base | `litellm-redis-hit` | 0.0104s | — |
| 2level | Q3 | variant | `litellm-redis-miss` | 2.4269s | — |
| no-cache | N1 | variant | `litellm-redis-miss` | 2.4106s | — |
| no-cache | N2 | variant | `litellm-redis-miss` | 2.4174s | — |
| no-cache | N3 | variant | `litellm-redis-miss` | 2.4030s | — |

| Mode | SGLang cache-hit rate | KV-cache memory (GB) |
|------|-----------------------|----------------------|
| 1level | 0.000 | 0.000 |
| 2level | 0.000 | 0.000 |
| no-cache | 0.000 | 0.000 |

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
| Lionsgate Films | The Fast and the Furious | New Line Cinema |
| A24 | Get Out | 40 Acres & a Mule Film Collective |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| New Line Cinema | Fight Club | MGM |
| Focus Features | The Last Samurai | Paramount Pictures |
| Searchlight Pictures | Sully | Paramount Pictures |
| Netflix | The Irishman | Universal Pictures |
| DC Studios | Batman v Superman: Dawn of Justice | Warner Bros. |
| Walt Disney Pictures | Frozen | Walt Disney Animation Studios |
| Warner Bros. Pictures | Harry Potter and the Sorcerer's Stone | Warner Bros. |
| Universal Pictures | The Godfather | Paramount Pictures |
| Paramount Pictures | The Sound of Music | Walt Disney Productions |
| Sony Pictures | The Amazing Spider-Man | Sony Pictures Animation |
| Columbia Pictures | Home Alone | Universal Pictures |
| 20th Century Studios | Cars | Pixar Animation Studios |
| Lionsgate Films | The Fast & Furious 7 | Universal Pictures |
| Legendary Entertainment | Furious 7 | Lightstorm Entertainment |
| Focus Features | The Mummy | Twentieth Century Fox |
| Searchlight Pictures | Dunkirk | Legendary Pictures |
| DC Studios | Justice League | Warner Bros. |
| Walt Disney Pictures | The Little Mermaid | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Fellowship of the Ring | New Line Cinema |
| Universal Pictures | Titanic | 20th Century Fox |
| Paramount Pictures | The Exorcist | American International Pictures |
| Sony Pictures | Gravity | Paramount Pictures |
| Columbia Pictures | The Last of the Mohicans | Warner Bros. |
| Lionsgate Films | Transformers | Paramount Pictures |
| Metro-Goldwyn-Mayer | Casablanca | Warner Bros. |
| Legendary Entertainment | The Suicide Squad | Warner Bros. Pictures |
| New Line Cinema | The Departed | Warner Bros. |
| Focus Features | The Great Gatsby | Warner Bros. |
| Searchlight Pictures | The Imitation Game | Open Road Films |
| Netflix | Bird Box | 20th Century Fox |
| DC Studios | Wonder Woman | Warner Bros. Pictures |
| Walt Disney Pictures | Aladdin | Disney |
| Warner Bros. Pictures | The Lord of the Rings: The Two Towers | New Line Cinema |
| Universal Pictures | E.T. the Extra-Terrestrial | Paramount Pictures |
| Paramount Pictures | The Shining | Kubrick Productions |
| Sony Pictures | The Lost City | 20th Century Studios |
| Columbia Pictures | The Shawshank Redemption | Warner Bros. |
| DreamWorks Animation | Madagascar | 20th Century Fox |
| Lionsgate Films | Transformers: Dark of the Moon | Paramount Pictures |
| A24 | Us | Monic Pictures |
| Metro-Goldwyn-Mayer | Mutiny on the Bounty | Paramount Pictures |
| Legendary Entertainment | The Hobbit: The Desolation of Smaug | New Line Cinema |
| New Line Cinema | Pirates of the Caribbean: The Curse of the Black Pearl | Walt Disney Pictures |
| Focus Features | The Martian | RedBird Pictures |
| Searchlight Pictures | The Big Short | Appian Way Pictures |
| Netflix | The Gray Man | Paramount Pictures |
| DC Studios | Aquaman | Warner Bros. Pictures |
| Warner Bros. Pictures | The Lord of the Rings: The Return of the King | New Line Pictures |
| Universal Pictures | The Super Mario Bros. Movie | Illumination |
| Paramount Pictures | The Ten Commandments | MGM |
| Sony Pictures | Creed | Universal Pictures |
| Lionsgate Films | The Hunger Games | New Line Cinema |
| Legendary Entertainment | The Avengers: Age of Ultron | Marvel Studios |
| New Line Cinema | Memento | Warner Bros. |
| Focus Features | The Incredible Burt Wonderstone | Paramount Pictures |
| Netflix | The Old Guard | Legendary Pictures |
| DC Studios | Shazam! | Warner Bros. |
| Walt Disney Pictures | Mulan | Disney |
| Warner Bros. Pictures | Batman Begins | Warner Bros. |
| Universal Pictures | Fast & Furious | New Line Cinema |
| Paramount Pictures | The Great Escape | Columbia Pictures |
| Sony Pictures | Alita: Battle Angel | Lightstorm Entertainment |
| Lionsgate Films | John Carter | 20th Century Studios |
| New Line Cinema | The Social Network | Columbia Pictures |
| Focus Features | The Adventures of Tintin | Blue Sky Studios |
| Netflix | Don't Look Up | Sony Pictures Animation |
| DC Studios | The Flash | Warner Bros. Pictures |
| Walt Disney Pictures | Toy Story | Pixar Animation Studios |
| Pixar Animation Studios | Coco | Walt Disney Animation Studios |
| Warner Bros. Pictures | Man of Steel | Warner Bros. |
| Universal Pictures | Back to the Future | TriStar Pictures |
| Sony Pictures | Venom | Marvel Studios |
| Lionsgate Films | The Expendables | 20th Century Fox |
| Focus Features | The Chronicles of Narnia: The Lion, the Witch and the Wardrobe | Walden Media |
| Netflix | The Power of the Dog | A24 |
| DC Studios | Zack Snyder's Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Princess and the Frog | Walt Disney Animation Studios |
| Universal Pictures | The Wizard of Oz | Metro-Goldwyn-Mayer |
| DreamWorks Animation | Chicken Run | Aardman Animations |
| Lionsgate Films | The Mummy (2001) | Twentieth Century Fox |
| Focus Features | The Hobbit: An Unexpected Journey | Warner Bros. |
| Netflix | The Fabelmans | A24 |
| DC Studios | The Batman | Warner Bros. |
| Walt Disney Pictures | Wreck-It Ralph | Walt Disney Animation Studios |
| Universal Pictures | Scooby-Doo | Paramount Pictures |
| Sony Pictures | The Girl with the Dragon Tattoo | Skydance Media |
| Lionsgate Films | The Mummy: Tomb of the Dragon Emperor | 20th Century Fox |
| Focus Features | The Secret Life of Walter Mitty | Sony Pictures |
| DC Studios | Shazam! Fury of the Gods | Warner Bros. |
| Walt Disney Pictures | Moana | Walt Disney Animation Studios |
| Lionsgate Films | The Mummy (2017) | Universal Pictures |
| Studio Ghibli | From Up on Poppy Hill | MGM |

## Re-run

```sh
pixi run cinematic-01-test -- --model local-sglang --cache-mode both
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260823-112134-local-sglang/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260823-112134-local-sglang/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260823-112134-local-sglang/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-23T11:32:10+0200.*
