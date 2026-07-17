# Manual smoke test

Until automated tests exist (migration Phase 8), this checklist is the regression
detector for the AI Learning Engine. Run it after every phase of the modernization
(see [docs/modernization/03-migration-plan.md](../docs/modernization/03-migration-plan.md)).

Run the app:

```bash
streamlit run app.py          # or: uv run streamlit run app.py (Phase 2+)
```

## Core flow (MCQ)

1. Pick a working AI provider in the sidebar (Local AI/Ollama is easiest, but any
   configured provider works).
2. Upload a small PDF.
3. Choose **Interactive Quiz → Multiple Choice**, 3 questions, Standard difficulty.
4. Generate. Answer all 3 questions and **Submit Quiz**.
5. Results screen renders with a score and a per-question review.

## Open-ended flow (exercises BUG-1 and BUG-2)

1. Same document, choose **Interactive Quiz → Open-ended Questions**, 2 questions.
2. Generate, write a short answer to each, submit.
3. **Results must render without crashing** (BUG-1: nested-expander crash on the
   "View Model Answer" block).
4. Expand/collapse a question, or click anything on the results page:
   - The "🤖 Scoring open-ended questions…" spinner must **not** reappear (BUG-2:
     re-scoring on every rerun).
   - The score/feedback must not change between reruns.

## Flashcards (exercises BUG-3)

1. Same document, choose **Study Materials → Flashcards**, generate.
2. Show the answer on card 1, click **😊 Got it right!**
   - Must advance to **card 2**, not jump back to card 1 (BUG-3).
3. Flip two cards using **Previous/Next**.

## Analytics (exercises BUG-2 double-counting)

1. After completing exactly **one** quiz, switch to **📊 Learning Analytics**.
2. Total quizzes must read **1**, not 2+ (BUG-2 double-tracking).

## Known pre-existing breakage (baseline, before Phase 1)

Recorded so later changes aren't blamed for issues that already existed at the
`pre-modernization` tag:

- **Open-ended results crash** — nested expanders (BUG-1).
- **Google AI fails at generation** — retired model names (BUG-9).
- **Flashcard "Got it right" jumps to card 1** — `next_card()` reads an unset key (BUG-3).
- **"Save API keys locally" UI never appears** and `user_config.json` is deleted on
  startup — cloud detection always returns true (BUG-4).
- **`pip install` may run on first launch** — auto-install at import (BUG-5).
