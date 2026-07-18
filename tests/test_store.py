"""Persistence round-trip tests for the SQLite analytics store.

These lock in Phase 6's headline claim: analytics survive across sessions and
streaks span days. The store is pure stdlib, so no Streamlit/LLM is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from learning_engine.analytics import metrics
from learning_engine.analytics.store import AnalyticsStore


@pytest.fixture
def store(tmp_path):
    """A fresh file-backed store in a temp directory (per-test isolation)."""
    return AnalyticsStore(tmp_path / "analytics.db")


def _questions():
    return [
        {"question_type": "mcq", "correct": True, "difficulty_tag": "basic"},
        {"question_type": "open_ended", "correct": False, "difficulty_tag": "high"},
    ]


def test_quiz_round_trip(store):
    quiz_id = store.record_quiz(
        difficulty="Advanced",
        quiz_type="Mixed",
        total_questions=2,
        correct=1,
        score_pct=75.0,
        questions=_questions(),
    )
    assert quiz_id == 1

    perf = store.performance_over_time()
    assert len(perf) == 1
    assert perf[0]["score_percentage"] == 75.0
    assert perf[0]["difficulty"] == "Advanced"
    assert perf[0]["quiz_type"] == "Mixed"

    assert store.totals() == {"total_quizzes": 1, "total_questions": 2, "total_correct": 1}
    assert store.difficulty_breakdown() == {"Advanced": 1}
    assert store.type_breakdown() == {"Mixed": 1}

    detailed = store.detailed_results()
    assert len(detailed) == 1
    assert len(detailed[0]["questions"]) == 2
    assert detailed[0]["questions"][0] == {
        "question_type": "mcq",
        "correct": True,
        "difficulty_tag": "basic",
    }


def test_material_and_flashcard_round_trip(store):
    store.record_material_event("flashcards", 3.2, success=True)
    store.record_material_event("summary", 1.0, success=False)
    store.record_flashcard_event("viewed")
    store.record_flashcard_event("correct")
    store.record_flashcard_event("correct")

    mats = store.material_stats()
    assert mats["total_materials"] == 1  # only the successful one counts
    assert mats["material_types"] == {"flashcards": 1}
    assert len(mats["generation_times"]) == 2

    cards = store.flashcard_totals()
    assert cards == {
        "cards_viewed": 1,
        "correct_responses": 2,
        "incorrect_responses": 0,
        "skipped_responses": 0,
    }


def test_persistence_survives_new_instance(tmp_path):
    """A brand-new store object on the same file sees prior data (the whole point)."""
    path = tmp_path / "analytics.db"
    AnalyticsStore(path).record_quiz(
        difficulty="Standard",
        quiz_type="Multiple Choice",
        total_questions=3,
        correct=3,
        score_pct=100.0,
        questions=[{"question_type": "mcq", "correct": True, "difficulty_tag": "basic"}],
    )

    reopened = AnalyticsStore(path)  # simulates a browser refresh / new session
    assert reopened.totals()["total_quizzes"] == 1


def test_streak_spans_days(store):
    """Two quizzes on consecutive days → a real 2-day streak (was impossible in-session)."""
    now = datetime.now(UTC)
    store.record_quiz(
        difficulty="Standard",
        quiz_type="Mixed",
        total_questions=1,
        correct=1,
        score_pct=100.0,
        questions=[{"question_type": "mcq", "correct": True, "difficulty_tag": "basic"}],
        ts=now - timedelta(days=1),
    )
    store.record_quiz(
        difficulty="Standard",
        quiz_type="Mixed",
        total_questions=1,
        correct=1,
        score_pct=100.0,
        questions=[{"question_type": "mcq", "correct": True, "difficulty_tag": "basic"}],
        ts=now,
    )

    active = store.active_days()
    assert len(active) == 2
    today = now.astimezone().date()
    assert metrics.calculate_current_streak(active, today) == 2
    assert metrics.calculate_longest_streak(active) == 2


def test_export_and_reset(store):
    store.record_quiz(
        difficulty="Standard",
        quiz_type="Mixed",
        total_questions=1,
        correct=1,
        score_pct=100.0,
        questions=[{"question_type": "mcq", "correct": True, "difficulty_tag": "basic"}],
    )
    store.record_material_event("summary", 2.0, success=True)
    store.record_flashcard_event("viewed")

    export = store.export()
    assert len(export["quiz_results"]) == 1
    assert len(export["question_results"]) == 1
    assert len(export["material_events"]) == 1
    assert len(export["flashcard_events"]) == 1

    store.reset()
    assert store.totals()["total_quizzes"] == 0
    assert store.material_stats()["total_materials"] == 0
    assert store.flashcard_totals()["cards_viewed"] == 0
    assert store.active_days() == set()
