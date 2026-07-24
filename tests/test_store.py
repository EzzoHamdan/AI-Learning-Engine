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
        {
            "question_type": "mcq",
            "correct": True,
            "difficulty_tag": "basic",
            "topic": "Calvin cycle",
        },
        {
            "question_type": "open_ended",
            "correct": False,
            "difficulty_tag": "high",
            "topic": "Light reactions",
        },
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
        "topic": "Calvin cycle",
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


# --------------------------------------------------------------------------- #
# Schema migration
# --------------------------------------------------------------------------- #


def test_topic_defaults_to_empty_when_the_caller_omits_it(store):
    """Older callers (and pre-topic quizzes) must still record."""
    store.record_quiz(
        difficulty="Standard",
        quiz_type="Multiple Choice",
        total_questions=1,
        correct=1,
        score_pct=100.0,
        questions=[{"question_type": "mcq", "correct": True, "difficulty_tag": "basic"}],
    )
    assert store.detailed_results()[0]["questions"][0]["topic"] == ""


def test_a_pre_topic_database_is_migrated_in_place(tmp_path):
    """A database created before `topic` existed must keep its rows and gain the column.

    CREATE TABLE IF NOT EXISTS silently leaves an old table alone, so without an
    explicit migration every read would fail on the missing column.
    """
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
            difficulty TEXT NOT NULL, quiz_type TEXT NOT NULL,
            total_questions INTEGER NOT NULL, correct INTEGER NOT NULL,
            score_pct REAL NOT NULL
        );
        CREATE TABLE question_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, quiz_id INTEGER NOT NULL,
            qtype TEXT NOT NULL, correct INTEGER NOT NULL, difficulty_tag TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO quiz_results (ts, difficulty, quiz_type, total_questions, correct, "
        "score_pct) VALUES ('2026-07-01T10:00:00+00:00', 'Standard', 'MCQ', 1, 1, 100.0)"
    )
    conn.execute(
        "INSERT INTO question_results (quiz_id, qtype, correct, difficulty_tag) "
        "VALUES (1, 'mcq', 1, 'basic')"
    )
    conn.commit()
    conn.close()

    migrated = AnalyticsStore(db)

    # The pre-existing quiz survived, and its untagged question reads as untagged.
    assert migrated.totals()["total_quizzes"] == 1
    assert migrated.detailed_results()[0]["questions"][0]["topic"] == ""

    # And new writes carry topics.
    migrated.record_quiz(
        difficulty="Advanced",
        quiz_type="MCQ",
        total_questions=1,
        correct=1,
        score_pct=100.0,
        questions=[
            {"question_type": "mcq", "correct": True, "difficulty_tag": "basic", "topic": "Osmosis"}
        ],
    )
    topics = {q["topic"] for r in migrated.detailed_results() for q in r["questions"]}
    assert topics == {"", "Osmosis"}


def test_migration_is_idempotent(tmp_path):
    """init() runs on every open, so a second pass must not fail or duplicate."""
    db = tmp_path / "repeat.db"
    AnalyticsStore(db)
    again = AnalyticsStore(db)
    again.init()
    assert again.totals()["total_quizzes"] == 0


# --------------------------------------------------------------------------- #
# Spaced repetition
# --------------------------------------------------------------------------- #


def test_review_state_round_trips(store):
    from datetime import date as _date

    from learning_engine.analytics.scheduling import ReviewState

    state = ReviewState(repetitions=3, interval_days=15, ease=2.36, due=_date(2026, 8, 8))
    store.save_review("card-abc", state)

    loaded = store.review_states(["card-abc"])["card-abc"]
    assert loaded == state


def test_saving_the_same_card_twice_updates_rather_than_duplicates(store):
    from datetime import date as _date

    from learning_engine.analytics.scheduling import ReviewState

    store.save_review("card-abc", ReviewState(repetitions=1, interval_days=1))
    store.save_review(
        "card-abc", ReviewState(repetitions=2, interval_days=6, due=_date(2026, 8, 1))
    )

    states = store.review_states()
    assert len(states) == 1
    assert states["card-abc"].repetitions == 2


def test_unreviewed_cards_are_simply_absent(store):
    """Callers treat a missing key as a new card, so no placeholder row is written."""
    assert store.review_states(["never-seen"]) == {}


def test_review_states_with_no_filter_returns_everything(store):
    from learning_engine.analytics.scheduling import ReviewState

    store.save_review("a", ReviewState(repetitions=1))
    store.save_review("b", ReviewState(repetitions=2))
    assert set(store.review_states()) == {"a", "b"}


def test_filtering_by_an_empty_deck_does_not_return_the_whole_table(store):
    from learning_engine.analytics.scheduling import ReviewState

    store.save_review("a", ReviewState(repetitions=1))
    assert store.review_states([]) == {}
