"""Difficulty labels and score-band messages — display text, not configuration.

These used to live in `settings.py` as `DIFFICULTY_CONFIG` / `SCORING_CONFIG`,
where the difficulty entries also carried a fourth, drifted copy of the prompt
instructions. The real instructions now live in `generation/prompts.py`; what
remains here is purely what the UI shows, so it belongs to the UI layer and
settings keeps only numbers (rule R4).
"""

from __future__ import annotations

LEVELS = ("Standard", "Advanced", "Extreme")

# Level → (emoji, one-line description shown in the sidebar and on results).
DIFFICULTY_DISPLAY: dict[str, tuple[str, str]] = {
    "Standard": ("📚", "University-level questions testing comprehension and analysis"),
    "Advanced": ("🎓", "Graduate-level questions requiring critical analysis"),
    "Extreme": ("🔥", "Expert-level questions with tricky elements and edge cases"),
}

# Level → score bands, highest threshold first. Thresholds fall as difficulty
# rises: 70% on Extreme is a better performance than 70% on Standard.
SCORING_BANDS: dict[str, list[tuple[float, str, str]]] = {
    "Standard": [
        (90, "success", "🌟 Excellent! Outstanding performance!"),
        (80, "success", "👍 Great job! Well done!"),
        (70, "info", "👌 Good work! Room for improvement."),
        (60, "warning", "📚 Fair performance. Consider reviewing the material."),
        (0, "warning", "📖 Keep studying! You'll do better next time."),
    ],
    "Advanced": [
        (85, "success", "🏆 OUTSTANDING! Exceptional critical thinking!"),
        (75, "success", "🌟 EXCELLENT! Strong analytical skills!"),
        (65, "info", "👍 GOOD! Solid understanding of complex concepts!"),
        (50, "warning", "📚 DEVELOPING! These are challenging questions!"),
        (0, "warning", "💪 CHALLENGING! Advanced material takes time to master!"),
    ],
    "Extreme": [
        (80, "success", "🏆 LEGENDARY! You've mastered the most challenging content!"),
        (70, "success", "🌟 OUTSTANDING! Excellent performance on extreme difficulty!"),
        (60, "info", "🔥 IMPRESSIVE! Strong performance on very challenging material!"),
        (50, "warning", "👍 SOLID! Good grasp of complex concepts!"),
        (0, "warning", "💪 CHALLENGING! Extreme questions are meant to push your limits!"),
    ],
}


def emoji(difficulty: str) -> str:
    """The badge for `difficulty` (falls back to Standard's)."""
    return DIFFICULTY_DISPLAY.get(difficulty, DIFFICULTY_DISPLAY["Standard"])[0]


def selector_help() -> str:
    """The sidebar help text, built from the descriptions above."""
    return " | ".join(f"{level}: {DIFFICULTY_DISPLAY[level][1]}" for level in LEVELS)


def band(difficulty: str, percentage: float) -> tuple[str, str]:
    """Return (streamlit_callout_kind, message) for a score at this difficulty."""
    bands = SCORING_BANDS.get(difficulty, SCORING_BANDS["Standard"])
    for threshold, kind, message in bands:
        if percentage >= threshold:
            return kind, message
    return bands[-1][1], bands[-1][2]
