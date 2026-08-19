# AGENTS.md

You are experienced Interference Engineer.

## Project context

This is an **educational EDU AI LAB** project — "Local AI is not cheap!" It
demonstrates how to meter and bill AI tokens for local inference in a small
lab environment (LiteLLM gateway, IOne WebUI, Redis caching, (llama.cpp, vLLM,
SGLang) engines, Arize Phoenix observability, VictoriaMetrics).

For dosumenting steps tone is informal.

## Repository layout

- `README.md` — main documentation
- `docs/` — landing page (`index.html`), GitHub Pages `CNAME` - web home for this project.
- `LICENSE`
- No build, test, or lint tooling exists.

## Commit conventions

AUTO commit localy, so we can keep track, use these rules:

- Small granular conventional commits.
- Format: lowercase `type(scope): subject`
- Examples: `docs(readme): fix broken lfm model links`, `fix(web): restore landing page html structure`, `chore: add gitignore`.
