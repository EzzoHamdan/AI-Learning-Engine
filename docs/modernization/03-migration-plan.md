# 03 — Migration Plan (baby steps)

Nine phases. Each phase leaves the app **runnable** — you can stop after any phase and still be better off. Within each phase: **What / Why / How / Verify**. Do them in order; later phases assume earlier ones.

Conventions used below:
- Work on a branch per phase: `git checkout -b modernize/phase-N`.
- "Run the smoke test" means: `streamlit run app.py`, upload a small PDF, generate a 3-question MCQ quiz, finish it, open results; then generate flashcards and flip two cards.

---

## Phase 0 — Safety net (½ day)

**What:** Freeze a working baseline before touching anything.

**Why:** There are no tests, so your only regression detector right now is your own hands. Make the manual check cheap and the rollback trivial.

**How:**
1. `git tag pre-modernization` on current `main`.
2. Fix `.gitignore` (BUG-8): delete lines 169-173 (`demo_*.py`, `test_*.py`, `*_demo.py`, `*_test.py`, and keep `IMPLEMENTATION_SUMMARY.md` if you want). Tests must be committable before anything else, or every later phase flies blind.
3. Create `tests/manual-smoke.md` writing down the smoke test steps above, plus one open-ended quiz run and one analytics-page visit. This is your checklist until automated tests exist (Phase 8).
4. Run the smoke test once now and note what is *already broken* (per the audit: open-ended results crash — BUG-1 — and Google AI fails — BUG-9). Knowing the pre-existing breakage stops you blaming your own changes later.

**Verify:** `git status` clean, tag exists, you have a written record of current behavior.

---

## Phase 1 — Stop the bleeding: bug fixes in place, zero restructuring (1-2 days)

**What:** Fix the audit's confirmed bugs *inside the current file layout*. No files move in this phase.

**Why first:** These fixes are small, independently shippable, and every one of them reduces confusion during the restructure. Restructuring buggy code just relocates the bugs.

**How — one commit each:**

1. **Remove auto-pip-install (BUG-5).** In `auto_config.py`, delete `check_and_install_dependencies()` and its call inside `get_setup_status()` (`auto_config.py:96`). Missing deps should fail loudly with the normal `ImportError`.
2. **Fix the nested expander crash (BUG-1).** In `app.py:589-591`, replace the inner `st.expander("View Model Answer")` with `st.markdown("**Model answer:**")` + `st.info(question['model_answer'])`.
3. **Score once, then only read (BUG-2 — the big one).**
   - In `display_quiz()` where `quiz_completed` is set to `True` (`app.py:403-406`), immediately compute open-ended scores and store them: `st.session_state.open_ended_scores = …` and call `analytics.track_quiz_completion(...)` there, once.
   - Simplest structure: add a function `finalize_quiz(questions, user_answers)` that does the scoring loop currently at `app.py:461-482` plus the tracking call at `app.py:523-527`, and stores everything in session state.
   - `display_results()` becomes read-only: it renders from `st.session_state.open_ended_scores` and never calls the processor or `analytics.track_*`.
   - Guard with a flag: `if not st.session_state.get("quiz_finalized"): finalize_quiz(...); st.session_state.quiz_finalized = True`. Reset the flag wherever the quiz resets (`app.py:316-321`, `627-631`, `1488-1494`).
4. **Fix `next_card()` (BUG-3).** Pass the real list length in: `next_card(total_cards)` and use it instead of `st.session_state.get('flashcards', [])` (`app.py:888-895`).
5. **Fix the `st` NameError (BUG-6).** Add `import streamlit as st` at the top of `open_ended_processor.py`; remove the two inline imports (`open_ended_processor.py:113,229`). (This module still touches Streamlit for now — Phase 6 removes that properly.)
6. **Fix cloud detection (BUG-4).** Replace the `hasattr(st, 'secrets')` heuristic (`session_manager.py:19-30`) with an explicit signal: `return os.getenv("DEPLOYED", "").lower() == "true"` — and document `DEPLOYED=true` in the deployment section of the README. Decide the fate of `user_config.json`: recommended is to **delete the save-keys-to-JSON feature entirely** (it stores plaintext keys and has never actually run — see audit §2 BUG-4) and rely on `.env` / `st.secrets` / session input. That deletes `cleanup_cloud_config`, `save_user_config`, `_load_saved_api_keys`'s file branch, and the checkbox UI.
7. **Update dead model names (BUG-9).** `config.py:61-62` → `gemini-2.5-flash`; `study_materials_generator.py:49` → read from config instead of the hardcoded `gemini-2.0-flash-exp`; bump `google-genai` pin. Fix the stale "GPT-4" warning text (`app.py:1217,1226`).
8. **Reconcile config vs. hardcoded values (BUG-10).** Make `app.py:1421` use `quiz_config.SUMMARY_THRESHOLD`; make the sliders use `quiz_config.MIN/MAX/DEFAULT_QUESTIONS`; enforce an upload size limit at extraction time; fix the README `LOCAL_AI_MODELL` typo.
9. **Split `requirements.txt`.** Runtime deps stay; move `black/flake8/mypy/isort/pre-commit` to `requirements-dev.txt`; delete `streamlit-analytics` and `nltk` (unused). (Full pyproject conversion comes in Phase 2 — this step just stops installing dev tools on user machines.)
10. **Delete trivial dead code:** `get_model_info` (`app.py:65-66`), the no-op `local_ai_config.MODEL_NAME = selected_model` assignment (`app.py:1331`), `log_function_call` if unused.

**Verify:** smoke test, including: finish an open-ended quiz → results render, expanding/collapsing questions does **not** show the "Scoring…" spinner again, and Analytics shows `total_quizzes == 1` after exactly one quiz. Flashcard "Got it right" advances to the next card.

---

## Phase 2 — Traditional packaging skeleton (1 day)

**What:** Introduce `pyproject.toml` + `src/` layout and *move files without changing their contents* (except imports).

**Why:** Every later phase wants an importable package (`from learning_engine.generation import quiz`). Moving files is mechanical and safe *now* because Phase 1 already made behavior sane. Doing packaging before logic changes means later diffs show real changes, not renames.

**How:**
1. Install `uv` (`pipx install uv` or the installer). Create `pyproject.toml`:
   ```toml
   [project]
   name = "learning-engine"
   version = "1.0.0"
   requires-python = ">=3.11"
   dependencies = [
     "streamlit>=1.40", "python-dotenv>=1.0",
     "plotly>=5.24", "pandas>=2.2", "numpy>=1.26",
     "openai>=1.50", "requests>=2.32",
     "pymupdf>=1.24", "python-docx>=1.1", "python-pptx>=1.0",
     "pydantic>=2.8", "pydantic-settings>=2.4",
   ]
   [dependency-groups]
   dev = ["pytest>=8", "ruff>=0.6", "mypy>=1.11"]
   [tool.ruff]
   line-length = 100
   [tool.ruff.lint]
   select = ["E", "F", "I", "UP", "B"]
   ```
2. `uv lock && uv sync` → commit `uv.lock`. Delete `requirements*.txt` (README install becomes `uv sync`; keep a one-line `pip install -e .` alternative).
3. Create `src/learning_engine/` and **move** (git mv, keep names for now): `config.py → settings.py`, `logger.py`, `session_manager.py`, `ai_client_factory.py`, `google_ai_client.py`, `local_ai_client.py`, `open_ended_processor.py`, `study_materials_generator.py`, `learning_analytics.py` into the package. `setup_easy.py → scripts/setup_wizard.py`. `auto_config.py`: delete; move `ensure_env_file_exists` into the wizard.
4. `app.py` stays at the root as the Streamlit entrypoint but its imports change to `from learning_engine.session_manager import SessionManager`, etc.
5. Run `ruff check --fix .` and `ruff format .` once, commit separately ("mechanical format").
6. Rename `.env.template` → `.env.example`.

**Verify:** `uv run streamlit run app.py` passes the smoke test. `uv run python -c "import learning_engine"` works from anywhere.

---

## Phase 3 — One LLM client (2-3 days, biggest single win)

**What:** Replace `google_ai_client.py`, `local_ai_client.py`, and the mock layer in `ai_client_factory.py` with a single OpenAI-SDK-based client (`llm/client.py` + `llm/providers.py`), per target doc R2.

**Why:** ~600 lines of hand-written compatibility code exist to imitate an interface all three providers now speak natively. This layer is also where real bugs live (Gemini wrapper drops system messages and ignores temperature) and where the error-as-content anti-pattern originates.

**How:**
1. Create `src/learning_engine/llm/providers.py`:
   ```python
   class Provider(str, Enum):
       OLLAMA = "ollama"; GOOGLE = "google"; OPENAI = "openai"

   @dataclass(frozen=True)
   class ProviderConfig:
       provider: Provider
       base_url: str | None      # None = OpenAI default
       api_key: str
       chat_model: str
       scoring_model: str
   ```
   plus `health_check(cfg) -> tuple[bool, str]` (the ONE copy of the Ollama `/api/tags` probe; key-presence check for cloud providers).
2. Create `llm/client.py` with `make_client(cfg) -> OpenAI` (three lines, see target doc) and typed exceptions `ProviderUnavailable`, `GenerationFailed`. Ollama uses `base_url="http://<host>:<port>/v1", api_key="ollama"`; Gemini uses the OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`.
3. Delete `MockClient`/`MockChatCompletions` from the factory. `get_working_client` becomes `resolve_provider(selected) -> ProviderConfig`, raising `ProviderUnavailable(reason)` instead of returning a fake. Callers (`app.py`) catch it and disable the Generate button with the reason — no silent provider switching; instead show "Local AI is down — switch to Google AI?" info.
4. Everywhere that did the provider-conditional model dance (`app.py:91-101`, `230-240`, `study_materials_generator._get_model_config`, `open_ended_processor` model selection) now takes a `ProviderConfig` and uses `cfg.chat_model` / `cfg.scoring_model`. Delete all `use_google_ai/use_local_ai` boolean pairs — pass the config object.
5. Delete `google_ai_client.py` and `local_ai_client.py` (keep `list_available_models` — rewrite as one small function in `providers.py` using `GET /api/tags`). Remove all six `.replace('/v1', '')` call sites by storing the base URL *without* `/v1` in settings and appending it only in `make_client`.
6. Cache the client in the UI: `@st.cache_resource def get_client(cfg): return make_client(cfg)` and stop re-probing providers on every rerun — probe on demand (button/expander) or at most once per session with a "refresh status" button.
7. Remove `google-genai` from dependencies.

**Verify:** smoke test against **each** provider you can reach (Ollama locally at minimum; Gemini with a key). Confirm: stopping Ollama mid-session produces a clear "provider unavailable" message, *not* a JSON parse error. Confirm sidebar interactions are visibly snappier (no per-click HTTP probes).

---

## Phase 4 — Structured output + domain models (2-3 days)

**What:** Add `models.py` (Pydantic) and `llm/structured.py`; delete all seven regex JSON-extraction chains.

**Why:** Untyped dicts + regex parsing are the source of the "Failed to parse quiz data" failure mode and make every render function defensive (`question.get('type')`, `term.get('definition', 'No definition available')`). Schema-validated output turns malformed model responses into a *retried, then clearly-reported* event.

**How:**
1. Write `models.py` from the JSON shapes already embedded in the prompts (they are your de-facto schema):
   ```python
   class MCQQuestion(BaseModel):
       question: str
       options: list[str]
       correct_answer: str          # "A"/"B"/"C"/"D" or "True"/"False"
       explanation: str
       type: Literal["mcq", "tf"] = "mcq"

   class MarkingCriterion(BaseModel):
       criterion: str; marks: float; keywords: list[str]

   class OpenEndedQuestion(BaseModel):
       question: str; total_marks: float
       marking_scheme: list[MarkingCriterion]; model_answer: str
       type: Literal["open_ended"] = "open_ended"

   class Quiz(BaseModel):
       questions: list[MCQQuestion | OpenEndedQuestion]
   ```
   …and equivalents for `ScoringResult`, `Summary`, `CheatSheet`, `FlashcardDeck`, `Outline`, `KeyTerms` (copy the field lists from `study_materials_generator.py` prompts).
2. Write `llm/structured.py::generate_structured(client, model, prompt, schema, temperature)`:
   - Try native structured output (`response_format={"type": "json_schema", ...}`); on providers/models where that errors, fall back to appending "Respond with ONLY a JSON object matching this schema: …" and a single lenient ```json-block extractor (the one surviving regex, living here and only here).
   - `schema.model_validate_json(...)`; on `ValidationError`, retry **once** with the error text appended; then raise `GenerationFailed(content=...)`.
3. Convert call sites one generator at a time (each is one commit): `generate_quiz` in `app.py` → returns `Quiz`; `open_ended_processor` generation + scoring → `Quiz`/`ScoringResult`; each `study_materials_generator` method → its model. Delete each hand-rolled fallback dict (e.g., the fake single flashcard at `study_materials_generator.py:360-377`) — a validated failure now surfaces as an honest error message.
4. Update the display functions to attribute access (`q.question`, `card.front`). Mark the keyword fallback scorer's output as `estimated=True` in `ScoringResult` and badge it in the UI.
5. Fix `generate_mixed_quiz`'s circular import (BUG-7) as a by-product: quiz generation now lives in `generation/quiz.py` (create it in this phase — move `generate_quiz`, `summarize_text` prompt logic out of `app.py`; move prompt strings into `generation/prompts.py`, collapsing the three divergent difficulty-instruction copies into one).

**Verify:** smoke test all quiz types + all six material types with a local model (weakest JSON producer — best stress test). Deliberately break it: set the Ollama model to a tiny one and confirm a parse failure shows "generation failed after retry" instead of a stack trace or fake content.

---

## Phase 5 — Dismantle `app.py` (2-3 days)

**What:** Split the remaining 1,700-line `app.py` into `ui/` per the target skeleton; remove all import-time side effects.

**Why:** After Phases 3-4, `app.py`'s remaining bulk is pure UI plus orchestration glue plus module-level boot code. Splitting *now* is low-risk because the logic it used to own already moved out.

**How (mechanical order):**
1. Create `src/learning_engine/ui/state.py`: typed getters/setters for every session key currently accessed as strings (`quiz_generated`, `current_question`, `user_answers`, `original_text`, …) and `reset_quiz()`, `reset_materials()`, `reset_document()` functions replacing the four scattered copies of reset logic.
2. Move extraction functions (`extract_text_from_*`, `app.py:68-83`) to `extraction/` with the dispatcher + size check; wrap in `@st.cache_data` **at the UI call site**, not in the library.
3. Move display functions into `ui/components/`: `quiz_runner.py` (`display_quiz`), `results.py` (`display_results` + `finalize_quiz` from Phase 1), `flashcards.py`, `materials.py` (the six `display_*` material functions). Move sidebar construction (`app.py:1174-1362`) into `ui/sidebar.py`, returning a small `GenerationRequest` dataclass instead of the `locals()` hack (`app.py:1478`).
4. Create `ui/pages/study.py` (the current main flow) and `ui/pages/analytics.py`; `ui/main.py` uses `st.navigation([st.Page(study), st.Page(analytics)])` — replacing the mode selectbox (`app.py:1132-1141`).
5. Root `app.py` becomes:
   ```python
   from learning_engine.ui.main import run
   run()
   ```
   All the former module-level code (env writing, provider probing, client creation, debug prints at `app.py:11-63`) either dies or moves inside `run()` behind caching.
6. Sweep `learning_analytics.py`: split into `analytics/metrics.py` (pure: `calculate_learning_velocity`, `_calculate_longest_streak`, strength/weakness math — take data as arguments, return dicts) and `ui/pages/analytics.py` (rendering). Kill the import-time singleton (`learning_analytics.py:986-990`); construct the tracker in `state.py`. Replace deprecated `use_container_width=True` while you're in there.

**Verify:** full manual checklist (`tests/manual-smoke.md`), both pages, browser refresh mid-quiz (state should reset gracefully, not crash). `grep -rl "import streamlit" src/learning_engine | grep -v "/ui/"` → empty (rule R1 now holds).

---

## Phase 6 — Persistent analytics (1-2 days)

**What:** SQLite store so analytics survive refresh; make streaks real.

**Why:** The current analytics erase themselves on every refresh, so the headline features (streaks, improvement-over-time) are fictional. This is the highest-value *user-facing* modernization.

**How:**
1. `analytics/store.py`: `sqlite3` connection to `~/.learning_engine/analytics.db` (path in settings); tables `quiz_results(ts, difficulty, quiz_type, total_questions, correct, score_pct)`, `question_results(quiz_id, qtype, correct, difficulty_tag)`, `material_events(ts, mtype, seconds, success)`, `flashcard_events(ts, action)`. Timezone-aware timestamps (`datetime.now(timezone.utc)`).
2. `finalize_quiz` and the material/flashcard trackers write to the store (keep the in-session copies for the "this session" views).
3. `metrics.py` functions take rows from the store → streaks can now span days; velocity uses all history. Dashboard gains a "This session / All time" toggle.
4. Keep JSON export (dump tables); add "Reset my data" button (delete the DB file — with confirmation).

**Verify:** complete a quiz, refresh the browser → analytics still show it. Manually insert a row dated yesterday (`sqlite3` CLI) → streak shows 2 days.

---

## Phase 7 — Settings unification (1 day)

**What:** Finish `settings.py` as the single config source (target rule R4).

**Why:** Phases 3-6 each consumed parts of the old config; this phase deletes the leftovers so drift can't restart.

**How:**
1. `pydantic-settings` classes: `LLMSettings` (per-provider model names, host/port, temperatures, timeouts), `QuizSettings` (min/max questions, summary threshold, max upload MB, open-ended word bounds), `AppSettings` (title, debug, deployed flag, db path). Env prefixes (`LLM__`, `QUIZ__`) documented in `.env.example`.
2. Grep for every remaining literal that should be a setting (`3000`, `gemma2:2b`, `11434`, temperature values) and route through settings. Difficulty/scoring text lives in `generation/prompts.py`; numbers live in settings.
3. Delete the old `config.py` remnants. Update `scripts/setup_wizard.py` to write the new env names and current model suggestions.

**Verify:** `LLM__OLLAMA__CHAT_MODEL=llama3.2 uv run streamlit run app.py` actually changes the model used (check the sidebar/status line).

---

## Phase 8 — Tests + CI + types (2 days, then ongoing)

**What:** Automated safety net so the manual checklist retires.

**Why last (not first):** before Phase 5 the code physically couldn't be tested (Streamlit-coupled, circular imports, gitignored test files). Now the pure layers exist.

**How:**
1. `tests/conftest.py`: `FakeLLM` that returns canned JSON per schema (capture a few *real* provider responses as fixtures — best regression data you can get).
2. Highest-value tests, in order: `test_metrics.py` (streaks/velocity — pure math, catches off-by-one date bugs), `test_models.py` (validate captured provider outputs against schemas), `test_scoring.py` (fallback scorer + `estimated` flag), `test_generation.py` (prompt assembly contains difficulty text exactly once; structured retry path), `test_extraction.py` (tiny fixture PDF/DOCX/PPTX; size-limit rejection), plus the architecture test from R1 (no streamlit below `ui/`).
3. `.github/workflows/ci.yml`: `uv sync` → `ruff check` → `ruff format --check` → `mypy src/` → `pytest`. Add `pre-commit` with ruff if you like.
4. `mypy` strictness: start with `check_untyped_defs = true`, tighten per-module.

**Verify:** CI green on the PR; deliberately break a metric function → CI fails.

---

## Phase 9 — Optional upgrades (backlog, post-modernization)

Only after the above; each is now a small PR instead of surgery:
- **Drop the lossy auto-summarization** for large-context models (all current defaults handle far more than 3,000 chars) — summarize only past a much larger threshold, or chunk + map-reduce.
- Streaming generation (`stream=True`) with `st.write_stream` for perceived speed.
- Export study materials to Markdown/PDF download buttons.
- Question-topic tagging at generation time so strengths/weaknesses report *topics*, not just question types.
- Spaced-repetition scheduling for flashcards using the persistent store (you now have the data).
- Publish to PyPI / `uvx learning-engine` one-command run, replacing the setup wizard for technical users.

---

## Sequencing rationale (why this order)

1. **Bugs before structure** — moving broken code spreads the breakage across new files and pollutes every diff.
2. **Packaging before logic changes** — after Phase 2, every subsequent diff is a real change, reviewable in isolation.
3. **LLM client before structured output** — structured output needs one client to hang the schema logic on; doing it against three wrappers means doing it three times.
4. **Structured output before UI split** — display components are much simpler to extract when they receive typed models instead of defensive dict-groping.
5. **UI split before persistence** — the store needs one write path (`finalize_quiz`), which only exists cleanly after the state machine.
6. **Tests last-but-not-least** — not a philosophy statement; simply the first moment the code is testable. The manual checklist covers the gap until then.

## Effort summary

| Phase | Effort | Risk | Ship independently? |
|---|---|---|---|
| 0 Safety net | 0.5d | none | yes |
| 1 Bug fixes | 1-2d | low | yes — users benefit immediately |
| 2 Packaging | 1d | low (mechanical) | yes |
| 3 One LLM client | 2-3d | medium (touches every generation path) | yes |
| 4 Structured output | 2-3d | medium | yes |
| 5 UI split | 2-3d | medium (large mechanical diff) | yes |
| 6 Persistence | 1-2d | low | yes |
| 7 Settings | 1d | low | yes |
| 8 Tests/CI | 2d | none | yes |

Total: roughly **13-18 focused days**, spreadable over weeks since every phase lands green.
