# Modernization Documentation

This folder is the complete plan for modernizing the AI Learning Engine (written ~2025, reviewed 2026-07-17).

| Doc | What it answers |
|---|---|
| [01-current-state-audit.md](01-current-state-audit.md) | What exists today, what is broken, what is outdated, what is badly designed — with file/line evidence and an explanation of *why* each problem exists. |
| [02-target-architecture.md](02-target-architecture.md) | Does it need rearchitecting? (Yes — restructure, not rewrite.) The target "traditional" project skeleton and the key design decisions. |
| [03-migration-plan.md](03-migration-plan.md) | The baby-step plan: 9 phases, each with *what to do*, *how to do it*, *why*, and *how to verify* before moving on. |

## TL;DR

The app works as a prototype but has three classes of problems:

1. **Actual bugs** — some features crash or silently misbehave today (nested-expander crash on open-ended results, AI re-scoring + analytics double-counting on every rerun, the "save API keys" feature is dead code because cloud detection always returns true, `pip install` runs automatically at app import, tests are impossible to commit because `.gitignore` ignores `test_*.py`).
2. **Dead external dependencies** — the Google AI path targets `gemini-1.5-flash` / `gemini-2.0-flash-exp`, both retired. OpenAI defaults to `gpt-3.5-turbo` (legacy). The provider-compatibility layer (~500 lines of hand-written mock classes) is unnecessary because every provider now exposes an OpenAI-compatible endpoint.
3. **Architecture debt** — a 1,700-line `app.py` God module, config that exists but is never used, prompt text duplicated in 3 places (already drifted), 7 copies of a regex-based JSON parsing fallback chain, analytics that lose all data on page refresh despite advertising "streaks", no packaging, no tests, no CI.

**Verdict:** keep Streamlit and the feature set; restructure into a `src/` package with a single LLM client, structured (schema-validated) model output, a small persistence layer for analytics, and a test suite. Estimated effort: the plan is sequenced so the app keeps working after every phase.
