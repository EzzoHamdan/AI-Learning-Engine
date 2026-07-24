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


# --------------------------------------------------------------------------- #
# Topic analysis
# --------------------------------------------------------------------------- #


def _question(topic: str, correct: bool, qtype: str = "mcq", tag: str = "basic") -> dict:
    return {
        "question_type": qtype,
        "correct": correct,
        "difficulty_tag": tag,
        "topic": topic,
    }


def test_weak_topic_is_reported_by_name():
    """The Phase 9 payoff: weaknesses name a concept, not a question format."""
    results = [
        {
            "questions": [
                _question("Calvin cycle", False),
                _question("Calvin cycle", False),
                _question("Light reactions", True),
                _question("Light reactions", True),
            ]
        }
    ]
    analysis = metrics.strength_weakness_analysis(results)

    assert any("Calvin cycle" in w for w in analysis["weaknesses"])
    assert any("Light reactions" in s for s in analysis["strengths"])
    assert analysis["topic_performance"]["Calvin cycle"] == 0
    assert analysis["topic_performance"]["Light reactions"] == 100


def test_weakest_topic_is_recommended_first():
    results = [
        {
            "questions": [
                _question("Osmosis", False),
                _question("Osmosis", False),
                _question("Mitosis", False),
                _question("Mitosis", True),
            ]
        }
    ]
    recommendations = metrics.strength_weakness_analysis(results)["recommendations"]
    assert "Osmosis" in recommendations[0]


def test_a_single_attempt_is_not_enough_to_call_a_topic_weak():
    """One missed question is noise; a pattern needs repetition."""
    results = [{"questions": [_question("Osmosis", False), _question("Mitosis", True)]}]
    analysis = metrics.strength_weakness_analysis(results)
    assert not any("Osmosis" in w for w in analysis["weaknesses"])


def test_untagged_questions_are_skipped_rather_than_bucketed():
    """Pre-topic quizzes must not show up as a topic literally called ''."""
    results = [{"questions": [_question("", False), _question("", False)]}]
    analysis = metrics.strength_weakness_analysis(results)
    assert analysis["topic_performance"] == {}
    assert not any("needs review" in w for w in analysis["weaknesses"])


def test_topics_accumulate_across_quizzes():
    results = [
        {"questions": [_question("Osmosis", True)]},
        {"questions": [_question("Osmosis", False)]},
    ]
    assert metrics.strength_weakness_analysis(results)["topic_performance"]["Osmosis"] == 50


def test_empty_history_still_returns_the_topic_key():
    """Callers index topic_performance directly; it must always exist."""
    assert metrics.strength_weakness_analysis([])["topic_performance"] == {}


def test_strengths_lead_with_the_strongest_topic():
    """Mirror of the weakness ordering — the two lists rank in opposite directions."""
    results = [
        {
            "questions": [
                _question("Osmosis", True),
                _question("Osmosis", True),
                _question("Osmosis", True),
                _question("Osmosis", True),
                _question("Mitosis", True),
                _question("Mitosis", True),
                _question("Mitosis", True),
                _question("Mitosis", False),
            ]
        }
    ]
    strengths = metrics.strength_weakness_analysis(results)["strengths"]
    assert "Osmosis" in strengths[0]  # 100% before Mitosis's 75%
