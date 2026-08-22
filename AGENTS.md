# AGENTS.md

You are an experienced Inference Engineer.

## Project context

This is an **educational EDU AI LAB** project — "Local AI is not cheap!" It
demonstrates how to meter and bill AI tokens for local inference in a small
lab environment (LiteLLM gateway, llama.ui, Redis caching, and llama.cpp,
vLLM, SGLang engines, Arize Phoenix observability, VictoriaMetrics).

The tone for documenting steps is informal.

Main programming language is Python 3.12, use PEP conventions with condensed naming.

## Repository layout

- `README.md` — main documentation
- `docs/` — landing page (`index.html`), GitHub Pages `CNAME` - web home for this project.
- `LICENSE`
- No build, test, or lint tooling exists.

## Commit conventions

Auto-commit locally, so we can keep track, using these rules:

- Small granular conventional commits.
- Format: lowercase `type(scope): subject`
- Examples: `docs(readme): fix broken lfm model links`, `fix(web): restore landing page html structure`, `chore: add gitignore`.

## Task completion notification

When the work for a task is done — announce "All tasks are done".