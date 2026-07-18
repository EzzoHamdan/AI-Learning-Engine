"""Typed session-state accessors and explicit state transitions.

The UI reads and writes st.session_state only through this module, so every
cross-module key name lives in exactly one place, and the reset logic that the
old app.py copied in four places has a single implementation here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

if TYPE_CHECKING:
    from learning_engine.models import Quiz
    from learning_engine.ui.tracking import AnalyticsTracker

# Defaults for every cross-module session key. Mutable values are copied on init.
_DEFAULTS: dict[str, Any] = {
    # document
    "current_file_id": None,
    "original_text": "",
    "summarized_text": "",
    "text_summarized": False,
    "summarization_in_progress": False,
    # quiz
    "quiz_generated": False,
    "quiz_data": None,
    "quiz_type": "",
    "quiz_difficulty": "Standard",
    "current_question": 0,
    "user_answers": {},
    "quiz_completed": False,
    "quiz_finalized": False,
    "quiz_results": {},
    # study materials
    "materials_generated": False,
    "materials_data": None,
    "material_type": "",
}


def init_state() -> None:
    """Ensure every cross-module session key exists (idempotent)."""
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, dict) else value


def tracker() -> AnalyticsTracker:
    """The per-session analytics tracker (constructed once, on first use)."""
    if "analytics_tracker" not in st.session_state:
        from learning_engine.ui.tracking import AnalyticsTracker

        st.session_state.analytics_tracker = AnalyticsTracker()
    return st.session_state.analytics_tracker


# --------------------------------------------------------------------------- #
# Document / extraction
# --------------------------------------------------------------------------- #


def current_file_id() -> str | None:
    return st.session_state.current_file_id


def original_text() -> str:
    return st.session_state.original_text


def set_original_text(text: str) -> None:
    st.session_state.original_text = text


def summarized_text() -> str:
    return st.session_state.summarized_text


def text_summarized() -> bool:
    return st.session_state.text_summarized


def summarization_in_progress() -> bool:
    return st.session_state.summarization_in_progress


def set_summarization_in_progress(value: bool) -> None:
    st.session_state.summarization_in_progress = value


def store_summary(summary: str) -> None:
    """Record the condensed document text and mark summarization finished."""
    st.session_state.summarized_text = summary
    st.session_state.text_summarized = True
    st.session_state.summarization_in_progress = False


# --------------------------------------------------------------------------- #
# Quiz
# --------------------------------------------------------------------------- #


def quiz_generated() -> bool:
    return st.session_state.quiz_generated


def quiz_data() -> Quiz | None:
    return st.session_state.quiz_data


def quiz_type() -> str:
    return st.session_state.quiz_type


def quiz_difficulty() -> str:
    return st.session_state.quiz_difficulty


def store_quiz(quiz: Quiz, kind: str, difficulty: str) -> None:
    """Record a freshly generated quiz and enter the quiz-running state."""
    st.session_state.quiz_generated = True
    st.session_state.quiz_data = quiz
    st.session_state.quiz_type = kind
    st.session_state.quiz_difficulty = difficulty


def begin_quiz(quiz: Quiz) -> None:
    """(Re)start progress tracking for `quiz` — question 1, no answers."""
    reset_quiz_progress()
    st.session_state.quiz_data = quiz


def current_question() -> int:
    return st.session_state.current_question


def set_current_question(index: int) -> None:
    st.session_state.current_question = index


def user_answers() -> dict[int, str]:
    return st.session_state.user_answers


def record_answer(index: int, answer: str) -> None:
    st.session_state.user_answers[index] = answer


def quiz_completed() -> bool:
    return st.session_state.quiz_completed


def set_quiz_completed() -> None:
    st.session_state.quiz_completed = True


def quiz_finalized() -> bool:
    return st.session_state.quiz_finalized


def set_quiz_finalized() -> None:
    st.session_state.quiz_finalized = True


def quiz_results() -> dict:
    return st.session_state.quiz_results


def set_quiz_results(results: dict) -> None:
    st.session_state.quiz_results = results


# --------------------------------------------------------------------------- #
# Study materials
# --------------------------------------------------------------------------- #


def materials_generated() -> bool:
    return st.session_state.materials_generated


def materials_data() -> Any:
    return st.session_state.materials_data


def material_type() -> str:
    return st.session_state.material_type


def store_materials(data: Any, kind: str) -> None:
    st.session_state.materials_generated = True
    st.session_state.materials_data = data
    st.session_state.material_type = kind


# --------------------------------------------------------------------------- #
# Flashcards
# --------------------------------------------------------------------------- #


def init_flashcards() -> None:
    if "current_flashcard" not in st.session_state:
        st.session_state.current_flashcard = 0
        st.session_state.flashcard_answer_visible = False
        st.session_state.flashcard_stats = {"correct": 0, "incorrect": 0, "skipped": 0}


def current_flashcard() -> int:
    return st.session_state.current_flashcard


def set_current_flashcard(index: int) -> None:
    st.session_state.current_flashcard = index


def flashcard_answer_visible() -> bool:
    return st.session_state.flashcard_answer_visible


def set_flashcard_answer_visible(value: bool) -> None:
    st.session_state.flashcard_answer_visible = value


def flashcard_stats() -> dict[str, int]:
    return st.session_state.flashcard_stats


# --------------------------------------------------------------------------- #
# State transitions / resets (single source; formerly four divergent copies)
# --------------------------------------------------------------------------- #


def reset_quiz_progress() -> None:
    """Back to question 1 with no answers or scores ("Take Quiz Again")."""
    st.session_state.current_question = 0
    st.session_state.user_answers = {}
    st.session_state.quiz_completed = False
    st.session_state.quiz_finalized = False
    st.session_state.quiz_results = {}


def reset_quiz() -> None:
    """Discard the generated quiz entirely ("Generate New Quiz")."""
    st.session_state.quiz_generated = False
    reset_quiz_progress()


def reset_materials() -> None:
    """Leave the materials view; keeps the summarized text to avoid rework."""
    st.session_state.materials_generated = False


def reset_document(file_id: str | None) -> None:
    """A new file was uploaded: clear extraction, summary, and quiz state."""
    st.session_state.current_file_id = file_id
    st.session_state.original_text = ""
    st.session_state.summarized_text = ""
    st.session_state.text_summarized = False
    st.session_state.summarization_in_progress = False
    reset_quiz()
