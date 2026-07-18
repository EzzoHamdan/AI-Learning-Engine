"""Pure-math tests for analytics/metrics.py (no Streamlit, no DB, no mocks).

These guard the streak/velocity logic that Phase 6's persistence finally makes
meaningful across days.
"""

from __future__ import annotations

from datetime import date, timedelta

from learning_engine.analytics import metrics

# --------------------------------------------------------------------------- #
# Streaks
# --------------------------------------------------------------------------- #


def test_current_streak_counts_consecutive_days_ending_today():
    today = date(2026, 7, 18)
    active = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert metrics.calculate_current_streak(active, today) == 3


def test_current_streak_is_zero_when_today_is_inactive():
    today = date(2026, 7, 18)
    active = {today - timedelta(days=1), today - timedelta(days=2)}
    assert metrics.calculate_current_streak(active, today) == 0


def test_current_streak_stops_at_a_gap():
    today = date(2026, 7, 18)
    active = {today, today - timedelta(days=1), today - timedelta(days=3)}
    assert metrics.calculate_current_streak(active, today) == 2


def test_longest_streak_finds_the_longest_run():
    days = {
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 3),  # run of 3
        date(2026, 7, 10),
        date(2026, 7, 11),  # run of 2
    }
    assert metrics.calculate_longest_streak(days) == 3


def test_longest_streak_empty_is_zero():
    assert metrics.calculate_longest_streak(set()) == 0


# --------------------------------------------------------------------------- #
# Velocity / averages
# --------------------------------------------------------------------------- #


def _series(scores):
    return [{"timestamp": i, "score_percentage": s} for i, s in enumerate(scores)]


def test_velocity_insufficient_data():
    result = metrics.calculate_learning_velocity(_series([80]))
    assert result["trend"] == "insufficient_data"


def test_velocity_improving():
    result = metrics.calculate_learning_velocity(_series([50, 60, 70, 80, 90]))
    assert result["trend"] == "improving"
    assert result["velocity"] > 1


def test_velocity_declining():
    result = metrics.calculate_learning_velocity(_series([90, 80, 70, 60, 50]))
    assert result["trend"] == "declining"
    assert result["velocity"] < -1


def test_average_score():
    assert metrics.average_score(_series([50, 100])) == 75.0
    assert metrics.average_score([]) == 0.0


# --------------------------------------------------------------------------- #
# Difficulty classification / strengths & weaknesses
# --------------------------------------------------------------------------- #


def test_analyze_question_difficulty():
    assert metrics.analyze_question_difficulty("Evaluate the trade-offs of X") == "high"
    assert metrics.analyze_question_difficulty("Explain how X works") == "medium"
    assert metrics.analyze_question_difficulty("What is X?") == "basic"


def test_strength_weakness_analysis_flags_strong_and_weak_types():
    detailed = [
        {
            "questions": [
                {"question_type": "mcq", "difficulty_tag": "basic", "correct": True},
                {"question_type": "mcq", "difficulty_tag": "basic", "correct": True},
                {"question_type": "open_ended", "difficulty_tag": "high", "correct": False},
                {"question_type": "open_ended", "difficulty_tag": "high", "correct": False},
            ]
        }
    ]
    analysis = metrics.strength_weakness_analysis(detailed)
    assert analysis["type_performance"]["mcq"] == 100.0
    assert analysis["type_performance"]["open_ended"] == 0.0
    assert any("mcq" in s for s in analysis["strengths"])
    assert any("open_ended" in w for w in analysis["weaknesses"])
    assert analysis["recommendations"]  # non-empty
