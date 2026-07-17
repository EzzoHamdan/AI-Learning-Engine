# 01 — Current State Audit

Reviewed: 2026-07-17. Every finding below cites the file and line as of commit `29ccc65`.

## 1. Inventory — what exists today

Flat, single-directory layout. 13 Python files, ~4,700 lines, no package, no tests, no CI.

| File | Lines | Role today |
|---|---|---|
| `app.py` | ~1,700 | Everything: Streamlit UI, text extraction, prompt building, LLM calls, JSON parsing, quiz runner, results, flashcard viewer, study-material rendering, welcome page |
| `learning_analytics.py` | ~990 | Analytics tracking **and** the entire analytics dashboard UI |
| `study_materials_generator.py` | ~680 | Prompts + LLM calls + JSON parsing for 6 material types |
| `session_manager.py` | ~375 | Session state, API-key storage, provider status UI, cloud detection |
| `open_ended_processor.py` | ~320 | Open-ended question generation + AI scoring |
| `local_ai_client.py` | ~315 | Hand-written OpenAI-compatible wrapper around Ollama's raw API |
| `ai_client_factory.py` | ~195 | Provider factory + a "MockClient" used as an error channel |
| `config.py` | ~215 | Dataclass configs (largely unused) + difficulty/scoring dictionaries |
| `google_ai_client.py` | ~105 | Hand-written OpenAI-compatible wrapper around `google-genai` |
| `setup_easy.py` | ~280 | Interactive terminal setup wizard |
| `auto_config.py` | ~150 | Creates `.env`, auto-installs pip packages, detects providers |
| `logger.py` | ~80 | Logging setup (fine) + an unused decorator |
| `requirements.txt` | 29 | Mixed runtime/dev/"optional" deps, no lockfile |

### Data flow (as-built)

```
upload file ──► extract text (app.py:68-83)
                    │  if len > 3000 chars
                    ▼
             summarize via LLM (app.py:85-115)   ◄── lossy, hardcoded threshold
                    │
                    ▼
     build prompt string with JSON template embedded (app.py:117-228)
                    │
                    ▼
     client.chat.completions.create(...)          ◄── "client" may be a real
                    │                                 OpenAI client, one of two
                    ▼                                 hand-rolled fakes, or an
     regex-extract JSON from free text                error-carrying MockClient
     (4-level fallback chain, app.py:252-293)
                    │
                    ▼
     dict passed around untyped ──► rendered by display_* functions
                    │
                    ▼
     analytics tracked in st.session_state only (lost on refresh)
```

---

## 2. Confirmed bugs (things that are wrong *today*)

These are not style issues — each one is a crash, incorrect behavior, or a dead feature, verified by reading the code paths.

### BUG-1 — Open-ended results screen crashes (nested expanders)
**Where:** `app.py:566` opens `st.expander(f"Question {i+1}…")`, and inside it `app.py:590` opens `st.expander("View Model Answer")`.
**Why it's wrong:** Streamlit raises `StreamlitAPIException` for an expander nested inside another expander. Any quiz containing an open-ended question dies when rendering results.
**Why it exists:** the model-answer block was added later without re-testing the open-ended flow end to end; there are no tests to catch it.
**Fix direction:** render the model answer with `st.toggle`/`st.popover` or plain markdown inside the outer expander.

### BUG-2 — Open-ended answers are re-scored (and re-billed) on every rerun; analytics double-count
**Where:** `display_results()` (`app.py:418`) calls `processor.score_open_ended_answer(...)` (`app.py:461-482`) and `analytics.track_quiz_completion(...)` (`app.py:523-527`) directly in the render path.
**Why it's wrong:** Streamlit reruns the whole script on *every* widget interaction. Once the results screen is up, expanding a question, clicking anything, or even the browser reconnecting triggers a full rerun → every open-ended answer is sent to the LLM again (cost + 10-30s wait), and `total_quizzes`, `performance_over_time`, etc. increment again. One completed quiz can be counted five times, which then corrupts every downstream metric (velocity, streaks, averages).
**Why it exists:** the mental model was "this function runs once when the quiz completes." That's true in a request/response framework, false in Streamlit's rerun model. This is the single most important Streamlit idiom the codebase misses.
**Fix direction:** compute scoring/tracking exactly once when transitioning to the completed state, store results in `st.session_state`, and have `display_results` only *read*.

### BUG-3 — Flashcard "next" after self-assessment always jumps to card 1
**Where:** `next_card()` at `app.py:888-895` reads `st.session_state.get('flashcards', [])`.
**Why it's wrong:** nothing ever writes `st.session_state['flashcards']` — the cards live in `materials_data`. So the length is always 0, `current_flashcard < -1` is always false, and the "loop back to beginning" branch always runs. Marking a card correct/incorrect/skip on any card jumps you back to card 1.
**Why it exists:** the navigation buttons (`app.py:860-879`) use the real list; `next_card()` was written against a key that was never introduced. Untyped, stringly-keyed session state made this invisible.

### BUG-4 — "Cloud deployment" detection is always true → "save API keys" is dead code, config deleted at startup
**Where:** `session_manager.py:19-30`.
```python
if hasattr(st, 'secrets'):
    _ = st.secrets
    return True
```
**Why it's wrong:** `st.secrets` exists as an attribute in every modern Streamlit install, local or cloud, and merely referencing the object doesn't raise. So `is_cloud_deployment` is `True` on your laptop, which means: `cleanup_cloud_config()` (`session_manager.py:60-86`) deletes `user_config.json` on every startup, and the entire "💾 Save API keys locally" UI (`session_manager.py:292-329`) never renders. The feature the README advertises cannot work.
**Why it exists:** the heuristic ("secrets are accessible ⇒ we're in the cloud") was probably true on some old Streamlit version or was never verified locally. Environment detection by attribute-sniffing is inherently fragile — an explicit env var is the standard approach.

### BUG-5 — `pip install` runs automatically when the app imports
**Where:** `app.py:12-15` → `auto_config.get_setup_status()` → `check_and_install_dependencies()` (`auto_config.py:40-61`) runs `subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])` if any import fails.
**Why it's wrong:** a web app must never mutate its own environment at import time. It makes startup non-deterministic, breaks in read-only/locked environments (Docker, Streamlit Cloud), can hang the first page load for minutes, and is a supply-chain hazard (whatever `requirements.txt` says at runtime gets installed, unpinned).
**Why it exists:** it was a kindness for non-technical classmates ("it just works"). The right home for that kindness is `setup_easy.py` — an explicit, user-invoked script — not the app's import path.

### BUG-6 — `NameError` masks real scoring errors for OpenAI users
**Where:** `open_ended_processor.py:259` — `st.error(f"Scoring failed: …")` inside the `except` block, but `streamlit` is only imported *inside* the `if self.use_local_ai:` branch (`open_ended_processor.py:229`).
**Why it's wrong:** when the provider is OpenAI/Google and the scoring call throws, the handler itself throws `NameError: name 'st' is not defined`, replacing the real error. (It's "rescued" only because the caller's own broad `except` catches the NameError — so the user sees a garbage message.)
**Why it exists:** conditional local imports scattered through methods instead of module-level imports; no linting (`flake8` is in requirements but evidently never run — it flags exactly this, F821).

### BUG-7 — Circular import: the library imports the app
**Where:** `open_ended_processor.py:304` — `from app import generate_quiz` inside `generate_mixed_quiz()`.
**Why it's wrong:** a lower-level module reaching up into the top-level Streamlit script inverts the dependency direction. Importing `app` executes all of `app.py`'s module-level side effects (client creation, `.env` writing, provider probing). It only avoids infinite recursion because the import is deferred and `app` is usually already in `sys.modules`. It makes `open_ended_processor` untestable in isolation.
**Why it exists:** `generate_quiz` (prompting + parsing logic) lives in the UI file, so the only way to reuse it was to import the UI. The real fix is moving generation logic out of `app.py` — see doc 02.

### BUG-8 — Tests are impossible to commit
**Where:** `.gitignore:169-173` ignores `demo_*.py`, `test_*.py`, `*_demo.py`, `*_test.py`.
**Why it's wrong:** any test file following the universal pytest naming convention is silently invisible to git. This guarantees the project stays untested.
**Why it exists:** presumably added to keep personal scratch scripts out of the repo; the pattern collided with the standard test naming.

### BUG-9 — The Google AI path is dead (retired models)
**Where:** `config.py:61-62` (`gemini-1.5-flash`), `study_materials_generator.py:49` (`gemini-2.0-flash-exp`), `requirements.txt:14` (`google-genai>=0.8.0`).
**Why it's wrong:** `gemini-1.5-flash` was retired in September 2025 and `gemini-2.0-flash-exp` was an experimental alias that no longer resolves — the API returns errors for both, so choosing Google AI fails at generation time. The pinned SDK floor (`0.8.0`) predates the stable 1.x API.
**Why it exists:** cloud model names are perishable; the code hardcodes them in three different files, so nothing short of a grep sweep keeps them consistent (they had *already* drifted from each other: config says 1.5-flash, materials generator says 2.0-flash-exp).

### BUG-10 — Config exists but the app doesn't use it (silent drift)
Several settings look authoritative but are dead or contradicted:
- `QuizConfig.SUMMARY_THRESHOLD = 5000` (`config.py:20`) — `app.py:1421` hardcodes `len(text) > 3000`. The comment "Increased from 3000 to reduce API calls" describes a change that never took effect.
- `QuizConfig.MAX_TEXT_LENGTH = 10000` (`config.py:19`) — never referenced anywhere.
- `QuizConfig.MIN/MAX/DEFAULT_QUESTIONS` (`config.py:15-17`) — the sliders hardcode their own ranges (`app.py:1215`, `1220-1222`, `1228`).
- `DIFFICULTY_CONFIG[...]["instructions"]` (`config.py:159-188`) — duplicated *and already divergent* copies in `app.py:124-149` and `open_ended_processor.py:47-63`. The app never reads the config copy.
- The README's 50MB upload limit is not enforced anywhere.
- `USE_OPENAI` is written by both setup scripts but read by nothing.
- The default `.env` written by `auto_config.py:30` sets `LOCAL_AI_MODELL` in the README (`README.md:221`) — a typo'd variable name that matches nothing.
**Why it exists:** config was added aspirationally after the code worked; without a single source of truth, every new feature re-declared its own constants.

### BUG-11 — Errors travel as fake successful responses
**Where:** `ai_client_factory.py:18-46` (`MockClient` returns a normal-shaped response whose `content` is `"Error: <message>"`).
**Why it's wrong:** downstream code can't distinguish "the model answered" from "there is no model." The error string flows into the JSON-extraction chain, fails to parse, and surfaces as *"Failed to parse quiz data. Response content: Error: Ollama server not running…"* — a misleading parse error for a connectivity problem. Exceptions exist for exactly this.
**Why it exists:** an attempt at "graceful degradation" without an error-handling strategy; returning *something* shaped like success was the path of least resistance.

### BUG-12 — Model-selection state mutates a throwaway object
**Where:** `app.py:1331` — `local_ai_config.MODEL_NAME = selected_model`.
**Why it's wrong:** `local_ai_config` is a fresh `LocalAIConfig()` instance created at module import on *this* rerun; assigning to it persists nothing (next rerun re-instantiates). It happens to work only because the code also writes `st.session_state.selected_local_model`, which is what's actually read elsewhere. The assignment is a no-op that misleads readers about where truth lives.

---

## 3. Outdated / deprecated things

| Item | Where | Status in 2026 |
|---|---|---|
| `gemini-1.5-flash`, `gemini-2.0-flash-exp` | `config.py:61`, `study_materials_generator.py:49` | Retired. Current equivalent: `gemini-2.5-flash` (or `-lite`). |
| `gpt-3.5-turbo` default, `gpt-4` mapping | `config.py:37`, `app.py:100,239`, `google_ai_client.py:30-31` | Legacy tier; `gpt-4o-mini`/newer small models are cheaper and better. The UI still warns "uses GPT-4 for scoring" (`app.py:1217`) while config uses `gpt-4o-mini` — stale copy. |
| `gemma2:2b` as the recommended local model | everywhere | Superseded (Gemma 3, Llama 3.x, Qwen 3 lines); should not be hardcoded in 8 places. |
| Hand-rolled OpenAI-compat wrappers for Ollama | `local_ai_client.py` (all 315 lines) | Obsolete: Ollama has shipped a native OpenAI-compatible `/v1/chat/completions` endpoint for years. `OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")` replaces the entire file. Ironically `config.py:94` already builds the `/v1` URL and every consumer then strips it back off (`.replace('/v1', '')` appears 6 times). |
| Hand-rolled OpenAI-compat wrapper for Gemini | `google_ai_client.py` (all 105 lines) | Obsolete: Google offers an OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`), and the native SDK supports structured output directly. The wrapper also *drops system messages and every message after the first user message* (`google_ai_client.py:19-26`) and silently ignores `temperature`/`max_tokens` (`google_ai_client.py:39-42`). |
| Regex JSON extraction | `app.py:252-293` + 6 more copies | Obsolete: all three providers support structured output (OpenAI `response_format=json_schema`, Gemini `response_schema`, Ollama `format=json`). |
| `black` + `flake8` + `isort` as separate tools | `requirements.txt:21-25` | Modern consolidation: Ruff does all three, faster. (They were also never wired up — no config, no CI, and BUG-6 proves flake8 never ran.) |
| `requirements.txt` as the only dependency spec | root | Modern packaging is `pyproject.toml` + a lockfile (`uv`). Dev tools currently install into user machines as "runtime" deps, under a heading that says "Document Processing". The "## Optional Dependencies" section is *not* optional — pip installs those lines unconditionally. |
| Streamlit idioms | throughout | `use_container_width=True` is deprecated (→ `width="stretch"`); mode-switching via a sidebar selectbox (`app.py:1132`) predates `st.navigation`/`st.Page` multipage apps; no `st.cache_resource` for clients, no `st.cache_data` for extraction/summaries; `st.rerun()` used 15+ times where callbacks or state transitions would do. |
| Naive `datetime.now()` everywhere | `learning_analytics.py`, `app.py`, `study_materials_generator.py` | Timezone-naive timestamps; fine for one laptop, wrong the moment data persists. |
| `devcontainer.json` launch flags | `.devcontainer/devcontainer.json:22` | `--server.enableCORS false --server.enableXsrfProtection false` disables protections globally as a convenience. |

---

## 4. Structural problems (the "rigged" parts)

### 4.1 `app.py` is a God module with import-time side effects
Lines 1-63 run at import: writing `.env` to disk, possibly running pip, probing Ollama over HTTP, creating an LLM client, and emitting Streamlit warnings. Then `main()` declares `global client, ai_provider, client_successful` (`app.py:1128`) and mutates them. Consequences:
- Nothing in this file can be imported without booting the whole app (this is why BUG-7 exists).
- Every rerun re-executes the provider probe: `render_provider_selector` → `update_provider_status` (`session_manager.py:331-376`, `247-255`) makes up to 3 network checks *per rerun*, plus `get_working_client` at `app.py:47` re-creates the client from scratch — including `LocalAIClient.__init__`'s two HTTP calls (`local_ai_client.py:60-64`). The UI pays multi-hundred-ms latency on every click.
- `generate_study_materials_content(final_text, material_type, locals())` (`app.py:1478`) passes the caller's *entire local scope* as a parameter — the function signature is a lie, and refactoring the caller silently breaks the callee.

### 4.2 Three parallel fake-OpenAI object hierarchies
`MockResponse/MockChoice/MockMessage` exist in `google_ai_client.py:67-85`, again as dataclasses in `local_ai_client.py:16-42`, and again inside `MockChatCompletions` in `ai_client_factory.py:33-46`. ~500 lines exist only to imitate the OpenAI response shape — which every target API can now speak natively (see §3). This layer is also where bugs hide (dropped system prompts, ignored parameters).

### 4.3 Provider identity is stringly-typed and checked everywhere
`"Local AI (Ollama)" / "Google AI" / "OpenAI"` literals appear ~40 times across 6 files, including emoji-prefixed variants that get string-split back apart (`session_manager.py:365`). Both `StudyMaterialsGenerator` and `OpenEndedQuestionProcessor` take `use_google_ai`/`use_local_ai` boolean pairs (`study_materials_generator.py:29`, `open_ended_processor.py:16`) — a 2-bit enum encoded as two bools, with the invalid state (both true) unguarded, and each class re-deriving model/temperature its own way (`_get_model_config` hardcodes models, ignoring `config.py` entirely).

### 4.4 Analytics: session-scoped storage sold as longitudinal tracking
`learning_analytics.py` keeps everything in `st.session_state`, which dies on refresh. Therefore "Study Streaks" (`learning_analytics.py:775-809`) can mathematically never exceed 1 day, "learning velocity" resets every session, and the README's "track improvement trends over time" is unfulfillable. The class also mixes concerns: ~250 lines of tracking/metrics (pure logic, easily testable) welded to ~700 lines of Plotly/Streamlit dashboard code, plus a module-level singleton created at import via session state (`learning_analytics.py:986-990`) — importing the module requires a running Streamlit context.

### 4.5 Prompt templates are string literals inside functions
Every prompt embeds its expected JSON shape as an f-string (`app.py:159-228`, `open_ended_processor.py:65-107`, six methods in `study_materials_generator.py`). Because raw document text is interpolated straight in (`Content: {text}`), a document containing curly-brace examples or "ignore previous instructions" text can break or steer generation. There is no place to see/compare/version all prompts, which is how three divergent copies of the difficulty instructions happened.

### 4.6 Silent fallbacks that lie to the user
- `summarize_text` failure returns the original text with only a transient error (`app.py:113-115`) — generation then proceeds on unsummarized text that may exceed the model's context.
- `_fallback_scoring` (`open_ended_processor.py:262-291`) grades by keyword-counting and word count, then reports it as a score with fabricated "strengths".
- `get_working_client` silently switches your selected provider (`ai_client_factory.py:183-192`).
- README claims "API keys encrypted locally" (`README.md:262`); `save_user_config` writes them as plaintext JSON (`session_manager.py:176-192`).

### 4.7 Duplication census (why changes are risky today)
- JSON-extraction fallback chain: **7 copies** (`app.py`, `open_ended_processor.py` ×2, `study_materials_generator.py` ×5, minus variations).
- Difficulty instructions: **3 divergent copies**.
- Ollama health check (`GET /api/tags`): **6 copies** (`config.py:114`, `local_ai_client.py:69,79,278,310`, `auto_config.py:74`, `setup_easy.py:72,80`, `session_manager.py:236`).
- `.replace('/v1', '')` URL surgery: **6 copies**.
- Provider→model/temperature selection: **4 copies** (`app.py:91-101`, `app.py:230-240`, `study_materials_generator.py:42-55`, `open_ended_processor.py:110-121`).
- MCQ answer-letter extraction (`user_answer[0] in ['A','B','C','D']`): **3 copies** (`app.py:444-451`, `app.py:597-604`, `learning_analytics.py:141-146`).
- `.env` file writers: **2 competing copies** (`auto_config.py:13-37`, `setup_easy.py:173-197`) with different contents.

### 4.8 Missing engineering scaffolding
- No `pyproject.toml`, no package name, no `src/` layout — nothing is importable outside the repo directory, and `import app` *runs the app*.
- No tests (and BUG-8 forbids adding them), no CI, no type-checking run (mypy is in requirements, unconfigured), no pinned/locked dependencies, no versioning/changelog.
- Bare `except:` in 8 places (`config.py:117`, `session_manager.py:69,325`, `local_ai_client.py:312`, `auto_config.py:77`, `setup_easy.py:74,84`, `google_ai_client.py:61`) — these swallow `KeyboardInterrupt`/`SystemExit` too.
- `print()` used for debugging in library code (`google_ai_client.py:36-54`).
- Dead code: `get_model_info` returns its argument (`app.py:65-66`), `log_function_call` decorator never used (`logger.py:56-81`), `AppConfig.available_providers` never called, `MockLocalOpenAIClient.model_name` never read.

---

## 5. What is actually *good* (keep these)

- The **feature set and UX flow** are coherent and genuinely useful; the README is enthusiastic and mostly accurate about intent.
- **Marking-scheme-based open-ended scoring** (criteria + keywords + model answer, `open_ended_processor.py:65-107`) is a solid rubric design — better than "grade this 1-10".
- The **intent** behind `SessionManager` (runtime keys, provider status) and `AIClientFactory` (fallback) is right; only the mechanisms are wrong.
- `logger.py` is fine. `setup_easy.py`'s guided wizard is a nice touch worth keeping as an explicit script.
- Difficulty tiers, scoring thresholds, and study-plan presets in `config.py` are good *content* — they just need to become the single source of truth.
