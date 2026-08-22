# cinematic-01 smoke run: run-20260822-194728-local-gguf

- **model**: `local-gguf` — LFM2.5-2.6B Q8_0 GGUF (LiquidAI/LFM2.5-2.6B-GGUF)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, llama.cpp engine)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `154` rows (round-robin across studios)
- **mode**: `enabled` reasoning, `4` workers
- **run_at**: `2026-08-22T19:52:53+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **51/154** (33%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **131/154** (85%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.792** | 0.8 | **FAIL** |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 154 | 0 | 154 | 42384 | 2.79s |
| 2 | 154 | 0 | 154 | 50221 | 3.06s |
| 3 | 154 | 0 | 154 | 40751 | 2.36s |

## Cache demo — identical prompt, three calls

| Call | Prompt | Regime | Latency | Cache header |
|------|--------|--------|---------|--------------|
| Q1 | base | `litellm-redis-miss` | 1.9441s | — |
| Q2 | base | `litellm-redis-hit` | 0.0085s | — |
| Q3 | base + suffix | `litellm-redis-miss` | 1.9173s | — |

Call Q2 reuses the Q1 response from Redis — the GPU never wakes up.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. |
| Warner Bros. Pictures | The Dark Knight Rises | Legendary Entertainment |
| Paramount Pictures | Star Wars: Episode IV – A New Hope | 20th Century Fox |
| Sony Pictures | Spider-Man: Into the Spider-Verse | Sony Pictures Animation |
| Columbia Pictures | Gone with the Wind | Metro-Goldwyn-Mayer |
| 20th Century Studios | Ratatouille | Pixar Animation Studios |
| Lionsgate Films | The Fast and the Furious | Lightstorm Entertainment |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| New Line Cinema | Fight Club | Legendary Entertainment |
| Focus Features | The Last Samurai | Paramount Pictures |
| Searchlight Pictures | Sully | Paramount Pictures |
| Netflix | The Irishman | A24 |
| Marvel Studios | The Incredible Hulk | Paramount Pictures |
| DC Studios | Batman v Superman: Dawn of Justice | Warner Bros. Pictures |
| Walt Disney Pictures | Frozen | Walt Disney Animation Studios |
| Warner Bros. Pictures | Harry Potter and the Sorcerer's Stone | Warner Bros. |
| Universal Pictures | The Godfather | Paramount Pictures |
| Paramount Pictures | The Sound of Music | MGM |
| Columbia Pictures | Home Alone | Universal Pictures |
| 20th Century Studios | Cars | Pixar Animation Studios |
| Lionsgate Films | The Fast & Furious 7 | Universal Pictures |
| Metro-Goldwyn-Mayer | Ben-Hur | 20th Century Fox |
| New Line Cinema | The Big Lebowski | The Wachowski Company |
| Focus Features | The Mummy | 20th Century Fox |
| Searchlight Pictures | Dunkirk | BAFTA |
| DC Studios | Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Little Mermaid | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Fellowship of the Ring | New Line Pictures |
| Universal Pictures | Titanic | 20th Century Fox |
| Paramount Pictures | The Exorcist | Columbia Pictures |
| Sony Pictures | Gravity | Space Entertainment |
| Columbia Pictures | The Last of the Mohicans | Universal Pictures |
| Lionsgate Films | Transformers | Paramount Pictures |
| Metro-Goldwyn-Mayer | Casablanca | Warner Bros. |
| Legendary Entertainment | The Suicide Squad | Warner Bros. Pictures |
| New Line Cinema | The Departed | The Weinstein Company |
| Focus Features | The Great Gatsby | New Line Cinema |
| Searchlight Pictures | The Imitation Game | Open Road Films |
| Netflix | Bird Box | Focus Features |
| DC Studios | Wonder Woman | Warner Bros. |
| Walt Disney Pictures | Aladdin | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Two Towers | New Line Cinema |
| Universal Pictures | E.T. the Extra-Terrestrial | 20th Century Fox |
| Paramount Pictures | The Shining | Stanley Kubrick Productions |
| Sony Pictures | The Lost City | 20th Century Studios |
| Columbia Pictures | The Shawshank Redemption | Warner Bros. |
| Lionsgate Films | Transformers: Dark of the Moon | Paramount Pictures |
| A24 | Us | Universal Pictures |
| Metro-Goldwyn-Mayer | Mutiny on the Bounty | 20th Century Fox |
| Legendary Entertainment | The Hobbit: The Desolation of Smaug | New Line Cinema |
| New Line Cinema | Pirates of the Caribbean: The Curse of the Black Pearl | 20th Century Fox |
| Focus Features | The Martian | Columbia Pictures |
| Searchlight Pictures | The Big Short | A24 |
| Netflix | The Gray Man | Paramount Pictures |
| DC Studios | Aquaman | Warner Bros. Pictures |
| Walt Disney Pictures | Beauty and the Beast | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Return of the King | New Line Cinema |
| Universal Pictures | The Super Mario Bros. Movie | Illumination |
| Paramount Pictures | The Ten Commandments | MGM |
| Sony Pictures | Creed | Columbia Pictures |
| Lionsgate Films | The Hunger Games | New Line Cinema |
| Metro-Goldwyn-Mayer | The Philadelphia Story | MGM |
| Legendary Entertainment | The Avengers: Age of Ultron | Marvel Studios |
| New Line Cinema | Memento | Legendary Pictures |
| Focus Features | The Incredible Burt Wonderstone | Paramount Pictures |
| Netflix | The Old Guard | 20th Century Fox |
| DC Studios | Shazam! | Warner Bros. Pictures |
| Walt Disney Pictures | Mulan | Walt Disney Feature Animation |
| Warner Bros. Pictures | Batman Begins | Legendary Pictures |
| Paramount Pictures | The Great Escape | American International Pictures |
| Sony Pictures | Alita: Battle Angel | 20th Century Studios |
| Lionsgate Films | John Carter | 20th Century Fox |
| New Line Cinema | The Social Network | Columbia Pictures |
| Studio Ghibli | The Wind Rises | Studio Bones |
| Focus Features | The Adventures of Tintin | DreamWorks Animation |
| Netflix | Don't Look Up | Sony Pictures |
| DC Studios | The Flash | Warner Bros. Pictures |
| Walt Disney Pictures | Toy Story | Pixar Animation Studios |
| Warner Bros. Pictures | Man of Steel | New Line Cinema |
| Universal Pictures | Back to the Future | Lucasfilm |
| Sony Pictures | Venom | Marvel Studios |
| DreamWorks Animation | The Prince of Egypt | DreamWorks SKG |
| Lionsgate Films | The Expendables | 20th Century Fox |
| Focus Features | The Chronicles of Narnia: The Lion, the Witch and the Wardrobe | Walden Media |
| Netflix | The Power of the Dog | A24 |
| DC Studios | Zack Snyder's Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Princess and the Frog | Walt Disney Animation Studios |
| Universal Pictures | The Wizard of Oz | MGM |
| Sony Pictures | Joy | Columbia Pictures |
| DreamWorks Animation | Chicken Run | Aardman Animations |
| Lionsgate Films | The Mummy (2001) | Colossal Entertainment |
| Focus Features | The Hobbit: An Unexpected Journey | New Line Cinema |
| Netflix | The Fabelmans | Paramount Pictures |
| DC Studios | The Batman | Warner Bros. Pictures |
| Walt Disney Pictures | Wreck-It Ralph | Walt Disney Animation Studios |
| Universal Pictures | Scooby-Doo | Warner Bros. |
| Sony Pictures | The Girl with the Dragon Tattoo | Fox Searchlight Pictures |
| Lionsgate Films | The Mummy: Tomb of the Dragon Emperor | Twisted Pictures |
| Focus Features | The Secret Life of Walter Mitty | 20th Century Fox |
| DC Studios | Shazam! Fury of the Gods | Warner Bros. Pictures |
| Walt Disney Pictures | Moana | 20th Century Studios |
| Lionsgate Films | The Mummy (2017) | 20th Century Fox |
| Studio Ghibli | From Up on Poppy Hill | Aardman Animations |

## Re-run

```sh
pixi run cinematic-01-test
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260822-194728-local-gguf/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260822-194728-local-gguf/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260822-194728-local-gguf/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-22T20:51:30+0200.*
