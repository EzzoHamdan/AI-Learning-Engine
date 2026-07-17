# 02 — Target Architecture

## Does it need rearchitecting?

**Yes — a restructure, not a rewrite.** The verdict in one paragraph:

The product design (upload → generate → interact → track) is sound and Streamlit remains the right framework for a single-user study tool. What must change is *where code lives* and *how the pieces talk*: today the UI file owns the business logic, three hand-written compatibility layers stand in for one API standard, output parsing is regex archaeology, and analytics have no storage. None of that requires new features — it requires moving existing behavior into a conventional Python package with one LLM client, typed data models, and a database file. Every screen the user sees can stay the same.

What you should **not** do: rewrite in a heavier stack (FastAPI + React, etc.). Nothing in the audit is caused by Streamlit; it's caused by structure. A rewrite would spend months to arrive at the same feature set.

## The traditional skeleton

```
AI-Learning-Engine/
├── pyproject.toml                  # metadata + deps + tool config (ruff, mypy, pytest) — replaces requirements.txt
├── uv.lock                         # lockfile → reproducible installs
├── .env.example                    # replaces .env.template (standard name)
├── .gitignore                      # fixed: no longer ignores test_*.py
├── README.md
├── app.py                          # ~10 lines: thin launcher that calls the package
│
├── src/
│   └── learning_engine/
│       ├── __init__.py
│       ├── settings.py             # ONE config module (pydantic-settings). Replaces config.py,
│       │                           #   auto_config.py env logic, and all scattered constants.
│       ├── models.py               # Pydantic domain models: Question, Quiz, MarkingCriterion,
│       │                           #   ScoringResult, Flashcard, StudyGuide, Summary, …
│       │
│       ├── extraction/
│       │   ├── __init__.py         # extract_text(file, kind) dispatcher + size/type validation
│       │   ├── pdf.py              # PyMuPDF
│       │   ├── docx.py
│       │   └── pptx.py
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py           # ONE client. Replaces google_ai_client.py, local_ai_client.py,
│       │   │                       #   and ai_client_factory.py (~600 lines → ~80).
│       │   ├── providers.py        # Provider enum + per-provider base_url/model/health-check
│       │   └── structured.py       # generate(schema=PydanticModel) with validation + 1 retry.
│       │                           #   Replaces every regex JSON-extraction chain.
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── prompts.py          # ALL prompt templates in one file, incl. difficulty
│       │   │                       #   instructions (single source; currently 3 divergent copies)
│       │   ├── quiz.py             # MCQ/TF/mixed/open-ended generation (pure: text in, Quiz out)
│       │   ├── materials.py        # summaries, cheat sheets, flashcards, outlines, key terms
│       │   ├── scoring.py          # open-ended scoring + honest fallback
│       │   └── summarize.py        # document condensation / chunking
│       │
│       ├── analytics/
│       │   ├── __init__.py
│       │   ├── store.py            # SQLite persistence (~/.learning_engine/analytics.db)
│       │   └── metrics.py          # pure functions: velocity, streaks, strengths/weaknesses
│       │                           #   (extracted from learning_analytics.py — finally testable)
│       │
│       └── ui/
│           ├── main.py             # st.navigation([study, analytics]) — real multipage
│           ├── state.py            # typed session-state accessors + state transitions
│           ├── sidebar.py          # provider picker, API keys, generation options
│           ├── pages/
│           │   ├── study.py        # upload → generate → run
│           │   └── analytics.py    # dashboard (rendering only; math lives in analytics/metrics)
│           └── components/
│               ├── quiz_runner.py  # question navigation + answer capture
│               ├── results.py      # results view (reads precomputed scores — fixes BUG-2)
│               ├── flashcards.py
│               └── materials.py    # study-material renderers
│
├── scripts/
│   └── setup_wizard.py             # setup_easy.py moved; the ONLY place that installs/writes .env
│
├── tests/
│   ├── conftest.py                 # FakeLLM fixture (canned JSON responses)
│   ├── test_extraction.py
│   ├── test_models.py              # schema round-trips on real captured LLM outputs
│   ├── test_generation.py          # prompt assembly + parsing against FakeLLM
│   ├── test_scoring.py             # incl. fallback scorer
│   └── test_metrics.py             # velocity/streaks — pure math, no mocks needed
│
└── docs/
    └── modernization/              # these documents
```

## Rules that make the skeleton work (the actual architecture)

### R1 — Dependencies point one way: `ui → generation/analytics → llm/extraction → settings/models`
Nothing below `ui/` may import Streamlit. This single rule fixes: the circular import (BUG-7), library modules calling `st.error` (BUG-6), analytics being un-importable without a Streamlit context, and untestability. `models.py` and `settings.py` import nothing from the project.

*Enforcement:* keep it honest with a 5-line test using `grep`/import-linter: `grep -rl "import streamlit" src/learning_engine --include="*.py" | grep -v "/ui/"` must return empty.

### R2 — One LLM client, because every provider speaks OpenAI now
All three targets expose OpenAI-compatible chat endpoints:

| Provider | base_url | api_key |
|---|---|---|
| OpenAI | (default) | user key |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | user key |
| Ollama | `http://127.0.0.1:11434/v1` | `"ollama"` (any string) |

So `llm/client.py` is essentially:

```python
def make_client(p: ProviderConfig) -> OpenAI:
    return OpenAI(base_url=p.base_url, api_key=p.api_key, timeout=p.timeout)
```

This deletes `google_ai_client.py`, `local_ai_client.py`, and the mock hierarchy in `ai_client_factory.py` outright, and fixes the wrapper bugs (dropped system messages, ignored temperature) as a side effect. Errors **raise typed exceptions** (`ProviderUnavailable`, `GenerationFailed`) — the UI layer decides how to show them. No more error-strings-as-content (BUG-11).

*Alternative considered:* LiteLLM. Fine too, but it's a large dependency to do what three `base_url` values do; revisit only if you add many providers.

### R3 — Structured output instead of regex parsing
Every generation call goes through one function:

```python
def generate_structured(client, model, prompt, schema: type[BaseModel]) -> BaseModel:
    # 1. request JSON output (response_format json_schema when supported; else
    #    format=json / "return only JSON" instruction for local models)
    # 2. pydantic-validate; on failure, ONE retry that feeds the validation
    #    error back to the model; then raise GenerationFailed
```

Pydantic models replace the untyped dicts (`quiz_data["questions"][i]["correct_answer"]` → `quiz.questions[i].correct_answer`). This kills all 7 regex chains, makes malformed local-model output a *handled* case, and gives the UI compile-time-ish safety. Keep one lenient `json`-block extractor inside `structured.py` as the compat path for small local models — but it lives in exactly one place.

### R4 — Config has one home and everything reads it
`settings.py` (pydantic-settings) loads `.env` / environment / `st.secrets` and exposes typed settings: provider configs (model names in ONE place — fixes BUG-9/10), quiz limits (sliders read `settings.quiz.max_questions`), the summarization threshold, the upload size limit (now actually enforced in `extraction/__init__.py`). Difficulty instructions and scoring thresholds move to `generation/prompts.py` as the single copy. Delete `auto_config.py`; its .env-bootstrapping moves to the setup wizard, and its auto-pip-install (BUG-5) is removed, period.

### R5 — Session state is typed and transitions are explicit
`ui/state.py` wraps `st.session_state` with typed accessors and a tiny state machine (`IDLE → EXTRACTED → SUMMARIZED → GENERATED → RUNNING → COMPLETED`). Scoring and analytics-tracking run **inside the transition to COMPLETED**, exactly once, storing `ScoringResult`s in state; `components/results.py` only reads (fixes BUG-2, BUG-3-class errors, and the double-tracking). Clients are `@st.cache_resource`; extraction and summaries are `@st.cache_data` keyed on file bytes (kills the re-probing latency of §4.1).

### R6 — Analytics get a real store
`analytics/store.py` writes events to SQLite (stdlib, zero infra): `quiz_completed`, `material_generated`, `flashcard_reviewed` tables keyed by timezone-aware timestamps. `metrics.py` computes velocity/streaks/strengths as pure functions over query results. This is the change that makes "study streaks" and "improvement over time" *true* instead of advertised. Session-state remains only a per-run cache. Export keeps working (dump tables to JSON/CSV).

### R7 — Honest failure modes
- No AI provider → the generate button is disabled with a reason, not a mock client.
- Summarization fails → generation is blocked with a message, not silently fed oversized text.
- Fallback keyword scoring → clearly labeled "estimate (AI scoring unavailable)" in the UI, never mixed silently into analytics.
- API keys: env / `st.secrets` / session only. The plaintext `user_config.json` feature is dropped (it never worked — BUG-4 — so nothing is lost) and the false "encrypted" README claim is corrected.

## Dependency changes

| Remove | Why |
|---|---|
| `black`, `flake8`, `isort`, `mypy`, `pre-commit` from runtime deps | become dev-deps in `pyproject.toml`; ruff replaces the first three |
| `streamlit-analytics`, `nltk` | unused in code |
| `google-genai` | replaced by the OpenAI-compatible endpoint (one less SDK) |
| **Add** | |
| `pydantic` + `pydantic-settings` | models + config |
| `uv` (tooling, not a dep) | lockfile + fast installs |
| `pytest` (dev) | tests |

Model-name defaults to ship (July 2026, all replaceable in `settings.py`): OpenAI `gpt-4o-mini` (scoring can stay the same model), Google `gemini-2.5-flash`, Ollama default suggestion `llama3.2`/`gemma3` family — and the README's model-specific advice becomes generic ("pick any instruct model your RAM allows").

## Size expectation

Rough line-count movement (same features):

| Today | Target |
|---|---|
| `app.py` 1,700 | `ui/` ≈ 900 across 8 focused files |
| 3 provider wrappers + factory ≈ 620 | `llm/` ≈ 150 |
| 7 JSON-parse chains ≈ 250 | `structured.py` ≈ 60 |
| `learning_analytics.py` 990 | `analytics/` ≈ 450 + `ui/pages/analytics.py` ≈ 350 |
| duplicated prompts/constants | `prompts.py` ≈ 250, single copy |

Net: roughly the same total, but each file has one job, and ~1,000 lines of duplication/mocks disappear.
