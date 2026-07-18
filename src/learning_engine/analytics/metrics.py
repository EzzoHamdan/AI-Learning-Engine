"""Pure analytics math: velocity, streaks, strengths/weaknesses.

Every function takes plain data (lists/dicts/dates) and returns plain data, so
this module is importable and testable without Streamlit or a session
(architecture rule R1). Session-state bookkeeping lives in ui/tracking.py;
rendering lives in ui/pages/analytics.py.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np


def average_score(performance_over_time: list[dict]) -> float:
    """Mean score percentage across quiz history (0 when empty)."""
    if not performance_over_time:
        return 0.0
    scores = [entry["score_percentage"] for entry in performance_over_time]
    return sum(scores) / len(scores)


def analyze_question_difficulty(question_text: str) -> str:
    """Classify a question as basic/medium/high difficulty from its wording."""
    text = question_text.lower()
    if any(word in text for word in ["analyze", "evaluate", "compare", "synthesize", "critique"]):
        return "high"
    if any(word in text for word in ["explain", "describe", "discuss", "apply"]):
        return "medium"
    return "basic"


def calculate_learning_velocity(performance_over_time: list[dict]) -> dict:
    """Trend/velocity/acceleration of quiz scores over time.

    Each entry needs a `timestamp` and a `score_percentage`.
    """
    if len(performance_over_time) < 2:
        return {"trend": "insufficient_data", "velocity": 0, "acceleration": 0}

    sorted_history = sorted(performance_over_time, key=lambda x: x["timestamp"])
    scores = [entry["score_percentage"] for entry in sorted_history]

    # Simple linear trend; the slope is the learning velocity.
    x = np.arange(len(scores))
    z = np.polyfit(x, scores, 1)
    velocity = z[0]

    if len(scores) >= 3:
        # Acceleration = change in velocity between the early and recent windows.
        recent_scores = scores[-3:]
        early_scores = scores[:3] if len(scores) >= 6 else scores[: len(scores) // 2]

        if len(early_scores) >= 2 and len(recent_scores) >= 2:
            early_trend = np.polyfit(range(len(early_scores)), early_scores, 1)[0]
            recent_trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
            acceleration = recent_trend - early_trend
        else:
            acceleration = 0
    else:
        acceleration = 0

    if velocity > 1:
        trend = "improving"
    elif velocity < -1:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "velocity": velocity,
        "acceleration": acceleration,
        "confidence": min(len(scores) / 5, 1.0),  # more data -> more confidence
    }


def strength_weakness_analysis(detailed_results: list[dict]) -> dict:
    """Strengths/weaknesses/recommendations from per-question quiz results."""
    if not detailed_results:
        return {"strengths": [], "weaknesses": [], "recommendations": []}

    type_performance: dict[str, dict[str, int]] = {}
    difficulty_performance: dict[str, dict[str, int]] = {}

    for result in detailed_results:
        for question in result["questions"]:
            q_type = question["question_type"]
            difficulty = question["difficulty_tag"]
            is_correct = question["correct"]

            type_performance.setdefault(q_type, {"correct": 0, "total": 0})
            type_performance[q_type]["total"] += 1
            if is_correct:
                type_performance[q_type]["correct"] += 1

            difficulty_performance.setdefault(difficulty, {"correct": 0, "total": 0})
            difficulty_performance[difficulty]["total"] += 1
            if is_correct:
                difficulty_performance[difficulty]["correct"] += 1

    type_percentages = {
        q_type: (stats["correct"] / stats["total"]) * 100 if stats["total"] else 0
        for q_type, stats in type_performance.items()
    }
    difficulty_percentages = {
        difficulty: (stats["correct"] / stats["total"]) * 100 if stats["total"] else 0
        for difficulty, stats in difficulty_performance.items()
    }

    strengths = []
    weaknesses = []
    recommendations = []

    for q_type, percentage in type_percentages.items():
        if percentage >= 80:
            strengths.append(f"Strong performance in {q_type} questions ({percentage:.1f}%)")
        elif percentage < 60:
            weaknesses.append(f"Needs improvement in {q_type} questions ({percentage:.1f}%)")
            recommendations.append(f"Practice more {q_type} questions to improve understanding")

    for difficulty, percentage in difficulty_percentages.items():
        if percentage >= 80:
            strengths.append(
                f"Excellent handling of {difficulty} difficulty questions ({percentage:.1f}%)"
            )
        elif percentage < 60:
            weaknesses.append(
                f"Struggles with {difficulty} difficulty questions ({percentage:.1f}%)"
            )
            recommendations.append(
                f"Focus on building foundational knowledge for {difficulty} concepts"
            )

    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "type_performance": type_percentages,
        "difficulty_performance": difficulty_percentages,
    }


def calculate_current_streak(active_days: set[date], today: date) -> int:
    """Consecutive active days ending today."""
    streak = 0
    for i, day in enumerate(sorted(active_days, reverse=True)):
        if day == today - timedelta(days=i):
            streak += 1
        else:
            break
    return streak


def calculate_longest_streak(active_days: set[date]) -> int:
    """Longest run of consecutive active days."""
    if not active_days:
        return 0

    sorted_dates = sorted(active_days, reverse=True)
    longest = 1
    current = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i - 1] - sorted_dates[i]).days == 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest
