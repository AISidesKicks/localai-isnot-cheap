# cinematic-01 smoke run: run-20260822-211110-local-gguf

- **model**: `local-gguf` — LFM2.5-2.6B Q8_0 GGUF (LiquidAI/LFM2.5-2.6B-GGUF)
- **gateway**: `http://localhost:4000` (LiteLLM + Redis cache, llama.cpp engine)
- **dataset**: `/home/roro/Workspaces/localai-isnot-cheap/datasets/cinematic-01/dataset.csv`
- **sample**: `154` rows (round-robin across studios)
- **mode**: `disabled` reasoning, `2` workers
- **run_at**: `2026-08-22T21:21:00+0200`
- **test**: `smoketests/cinematic-01/test.py`

## Scenarios

| # | Scenario | Metric | Score | Threshold | Pass |
|---|----------|--------|-------|-----------|------|
| 1 | Studio recall | manual exact match | **49/154** (32%) | — | — |
| 2 | Year match (±2) | abs diff <= 2 | **126/154** (82%) | — | — |
| 3 | Year repeat | deepeval.ExactMatchMetric | **0.805** | 0.8 | PASS |

## Observations

| Scenario | Calls | Redis hits | Redis misses | Total tokens | Avg latency |
|----------|-------|------------|--------------|--------------|-------------|
| 1 | 154 | 0 | 154 | 39213 | 2.54s |
| 2 | 154 | 0 | 154 | 46985 | 2.93s |
| 3 | 154 | 0 | 154 | 37944 | 2.02s |

## Cache demo — identical prompt, three calls

| Call | Prompt | Regime | Latency | Cache header |
|------|--------|--------|---------|--------------|
| Q1 | base | `litellm-redis-miss` | 1.9717s | — |
| Q2 | base | `litellm-redis-hit` | 0.0094s | — |
| Q3 | base + suffix | `litellm-redis-miss` | 1.9750s | — |

Call Q2 reuses the Q1 response from Redis — the GPU never wakes up.

## Miss detail — studio recall

| Studio | Film | Guessed |
|--------|------|---------|
| DC Studios | The Dark Knight | Warner Bros. Pictures |
| Warner Bros. Pictures | The Dark Knight Rises | Legendary Entertainment |
| Paramount Pictures | Star Wars: Episode IV – A New Hope | 20th Century Fox |
| Sony Pictures | Spider-Man: Into the Spider-Verse | Sony Pictures Animation |
| Columbia Pictures | Gone with the Wind | Metro-Goldwyn-Mayer |
| 20th Century Studios | Ratatouille | Pixar Animation Studios |
| Lionsgate Films | The Fast and the Furious | Universal Pictures |
| A24 | Get Out | Skydance Media |
| Metro-Goldwyn-Mayer | Singin' in the Rain | MGM |
| Legendary Entertainment | X-Men: Days of Future Past | 20th Century Fox |
| New Line Cinema | Fight Club | MGM |
| Focus Features | The Last Samurai | Paramount Pictures |
| Searchlight Pictures | Sully | Paramount Pictures |
| Netflix | The Irishman | A24 |
| DC Studios | Batman v Superman: Dawn of Justice | Warner Bros. Pictures |
| Walt Disney Pictures | Frozen | Walt Disney Animation Studios |
| Warner Bros. Pictures | Harry Potter and the Sorcerer's Stone | Warner Bros. |
| Universal Pictures | The Godfather | Paramount Pictures |
| Paramount Pictures | The Sound of Music | Walt Disney Productions |
| Columbia Pictures | Home Alone | Universal Pictures |
| 20th Century Studios | Cars | Pixar Animation Studios |
| Lionsgate Films | The Fast & Furious 7 | 20th Century Fox |
| Metro-Goldwyn-Mayer | Ben-Hur | 20th Century-Fox |
| New Line Cinema | The Big Lebowski | The Coen Brothers |
| Focus Features | The Mummy | Twentieth Century Fox |
| Searchlight Pictures | Dunkirk | Legendary Pictures |
| DC Studios | Justice League | Warner Bros. |
| Walt Disney Pictures | The Little Mermaid | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Fellowship of the Ring | New Line Pictures |
| Universal Pictures | Titanic | 20th Century Fox |
| Paramount Pictures | The Exorcist | Universal Pictures |
| Sony Pictures | Gravity | Paramount Pictures |
| Columbia Pictures | The Last of the Mohicans | Paramount Pictures |
| Lionsgate Films | Transformers | Paramount Pictures |
| Metro-Goldwyn-Mayer | Casablanca | RKO Pictures |
| Legendary Entertainment | The Suicide Squad | Warner Bros. Pictures |
| New Line Cinema | The Departed | Fox Searchlight Pictures |
| Focus Features | The Great Gatsby | 20th Century Fox |
| Searchlight Pictures | The Imitation Game | Universal Pictures |
| Netflix | Bird Box | New Line Cinema |
| DC Studios | Wonder Woman | Warner Bros. Pictures |
| Walt Disney Pictures | Aladdin | Walt Disney Animation Studios |
| Warner Bros. Pictures | The Lord of the Rings: The Two Towers | New Line Pictures |
| Universal Pictures | E.T. the Extra-Terrestrial | Walt Disney Pictures |
| Paramount Pictures | The Shining | Warner Bros. |
| Sony Pictures | The Lost City | 20th Century Studios |
| Columbia Pictures | The Shawshank Redemption | Warner Bros. |
| Lionsgate Films | Transformers: Dark of the Moon | Paramount Pictures |
| Metro-Goldwyn-Mayer | Mutiny on the Bounty | 20th Century Fox |
| Legendary Entertainment | The Hobbit: The Desolation of Smaug | Warner Bros. Pictures |
| New Line Cinema | Pirates of the Caribbean: The Curse of the Black Pearl | Walt Disney Pictures |
| Focus Features | The Martian | Warner Bros. |
| Searchlight Pictures | The Big Short | A24 |
| Netflix | The Gray Man | Paramount Pictures |
| DC Studios | Aquaman | Warner Bros. Pictures |
| Walt Disney Pictures | Beauty and the Beast | Walt Disney Feature Animation |
| Warner Bros. Pictures | The Lord of the Rings: The Return of the King | New Line Pictures |
| Universal Pictures | The Super Mario Bros. Movie | Illumination |
| Paramount Pictures | The Ten Commandments | 20th Century-Fox |
| Sony Pictures | Creed | Columbia Pictures |
| Lionsgate Films | The Hunger Games | New Line Cinema |
| Metro-Goldwyn-Mayer | The Philadelphia Story | MGM |
| Legendary Entertainment | The Avengers: Age of Ultron | Marvel Studios |
| New Line Cinema | Memento | Legendary Pictures |
| Focus Features | The Incredible Burt Wonderstone | Legendary Pictures |
| Netflix | The Old Guard | 20th Century Studios |
| DC Studios | Shazam! | Warner Bros. Pictures |
| Walt Disney Pictures | Mulan | Walt Disney Animation Studios |
| Pixar Animation Studios | Brave | Pixar |
| Warner Bros. Pictures | Batman Begins | Warner Bros. |
| Paramount Pictures | The Great Escape | 20th Century Fox |
| Sony Pictures | Alita: Battle Angel | Lightstorm Entertainment |
| Lionsgate Films | John Carter | 20th Century Fox |
| New Line Cinema | The Social Network | Columbia Pictures |
| Studio Ghibli | The Wind Rises | Studio Bones |
| Focus Features | The Adventures of Tintin | Legendary Entertainment |
| Netflix | Don't Look Up | Sony Pictures |
| DC Studios | The Flash | Warner Bros. Pictures |
| Walt Disney Pictures | Toy Story | Pixar Animation Studios |
| Warner Bros. Pictures | Man of Steel | Warner Bros. |
| Universal Pictures | Back to the Future | Lucasfilm |
| Sony Pictures | Venom | Marvel Studios |
| Lionsgate Films | The Expendables | 21Lap |
| Focus Features | The Chronicles of Narnia: The Lion, the Witch and the Wardrobe | Walden Media |
| Netflix | The Power of the Dog | A24 |
| DC Studios | Zack Snyder's Justice League | Warner Bros. Pictures |
| Walt Disney Pictures | The Princess and the Frog | Walt Disney Animation Studios |
| Universal Pictures | The Wizard of Oz | MGM |
| Sony Pictures | Joy | Focus Features |
| DreamWorks Animation | Chicken Run | Aardman Animations |
| Lionsgate Films | The Mummy (2001) | Universal Pictures |
| A24 | The Florida Project | The Florida Project |
| Studio Ghibli | The Secret World of Arrietty | Gumball |
| Focus Features | The Hobbit: An Unexpected Journey | New Line Cinema |
| Netflix | The Fabelmans | Paramount Pictures |
| DC Studios | The Batman | Warner Bros. Pictures |
| Walt Disney Pictures | Wreck-It Ralph | Walt Disney Animation Studios |
| Universal Pictures | Scooby-Doo | Warner Bros. |
| Sony Pictures | The Girl with the Dragon Tattoo | Fazer Film AB |
| Lionsgate Films | The Mummy: Tomb of the Dragon Emperor | Twisted Pictures |
| Focus Features | The Secret Life of Walter Mitty | 20th Century Fox |
| DC Studios | Shazam! Fury of the Gods | Warner Bros. Pictures |
| Walt Disney Pictures | Moana | Walt Disney Animation Studios |
| Lionsgate Films | The Mummy (2017) | Colossal Entertainment |
| Studio Ghibli | From Up on Poppy Hill | The Dome |

## Re-run

```sh
pixi run cinematic-01-test
pixi run cinematic-01-report
```

Artifacts for this report:

- `datasets/cinematic-01/runs/run-20260822-211110-local-gguf/results.json` — raw rows
- `datasets/cinematic-01/runs/run-20260822-211110-local-gguf/eval.json` — scored scenarios
- `datasets/cinematic-01/runs/run-20260822-211110-local-gguf/report.md` — this report
- latest copies: `datasets/cinematic-01/results.json`, `eval.json`

---

*Rendered by `smoketests/cinematic-01/report.py` at 2026-08-22T21:21:14+0200.*
