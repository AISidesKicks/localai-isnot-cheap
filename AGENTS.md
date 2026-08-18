# AGENTS.md

## Project context

This is an **educational EDU AI LAB** project — "Local AI is not cheap!" It
demonstrates how to meter and bill AI tokens for local inference in a small
lab environment (LiteLLM gateway, Redis caching, llama.cpp / vLLM / SGLang
engines, Lago billing).

Tone is informal. The README contains pre-existing typos and informal wording
that are intentionally left alone — do not "fix" them.

## Repository layout

- `README.md` — main documentation
- `docs/` — landing page (`index.html`), GitHub Pages `CNAME`, `overview.jpeg`
- `LICENSE`
- No build, test, or lint tooling exists.

## Commit conventions

- Small granular conventional commits.
- Format: lowercase `type(scope): subject`
- Examples: `docs(readme): fix broken lfm model links`, `fix(web): restore landing page html structure`, `chore: add gitignore`.
