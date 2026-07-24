"""Tests for open-ended scoring, including the honest-failure fallback.

The audit's BUG-2 was that scoring re-ran on every Streamlit rerun; Phase 1 moved
it to a single finalize step. What remains worth testing is the scoring function
itself — above all that a keyword estimate is *labeled* as one (`estimated=True`)
rather than passed off as real AI marking, which is the Phase 4 honesty rule.
"""

from __future__ import annotations

import pytest

from learning_engine.generation.quiz import fallback_scoring, score_open_ended
from learning_engine.llm.providers import Provider, ProviderConfig
from learning_engine.models import MarkingCriterion, OpenEndedQuestion


@pytest.fixture
def cfg():
    return ProviderConfig(
        provider=Provider.OLLAMA,
        base_url="http://127.0.0.1:11434",
        api_key="ollama",
        chat_model="chat",
        scoring_model="scoring",
    )


@pytest.fixture
def question():
    return OpenEndedQuestion(
        question="Explain photosynthesis.",
        total_marks=6,
        marking_scheme=[
            MarkingCriterion(criterion="Location", marks=3, keywords=["chloroplast", "thylakoid"]),
            MarkingCriterion(criterion="Products", marks=3, keywords=["ATP", "NADPH"]),
        ],
        model_answer="Occurs in the chloroplast; produces ATP and NADPH.",
    )


# --------------------------------------------------------------------------- #
# No-answer short circuit
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_blank_answer_scores_zero_without_calling_the_model(fake_llm, cfg, question, blank):
    client = fake_llm({"total_score": 99, "max_score": 6})
    result = score_open_ended(client, cfg, question, blank)

    assert result.total_score == 0
    assert result.percentage == 0
    assert result.max_score == 6
    assert client.call_count == 0, "a blank answer must not cost an API call"


# --------------------------------------------------------------------------- #
# AI scoring
# --------------------------------------------------------------------------- #


def test_ai_score_is_returned_and_not_marked_estimated(fake_llm, cfg, question):
    client = fake_llm(
        {"total_score": 4.5, "max_score": 6, "overall_feedback": "Good, some detail missing."}
    )
    result = score_open_ended(client, cfg, question, "It happens in the chloroplast.")

    assert result.total_score == 4.5
    assert result.estimated is False
    assert result.percentage == 75.0  # recomputed from the scores


def test_missing_max_score_is_backfilled_from_the_question(fake_llm, cfg, question):
    """Models routinely omit max_score; the question already knows it."""
    client = fake_llm({"total_score": 3, "overall_feedback": "ok"})
    result = score_open_ended(client, cfg, question, "an answer")

    assert result.max_score == 6
    assert result.percentage == 50.0


def test_percentage_is_recomputed_rather_than_trusted(fake_llm, cfg, question):
    client = fake_llm(
        {"total_score": 3, "max_score": 6, "percentage": 100, "overall_feedback": "x"}
    )
    assert score_open_ended(client, cfg, question, "an answer").percentage == 50.0


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #


def test_generation_failure_falls_back_to_a_labeled_estimate(fake_llm, cfg, question):
    """The user must be able to see this score was not real AI marking."""
    client = fake_llm("not json", "still not json")  # exhausts the one retry
    result = score_open_ended(client, cfg, question, "chloroplast and ATP are involved")

    assert result.estimated is True
    assert "keyword" in result.overall_feedback.lower()
    assert result.max_score == 6


def test_transport_failure_also_falls_back(fake_llm, cfg, question):
    client = fake_llm(ConnectionError("ollama is down"))
    assert score_open_ended(client, cfg, question, "chloroplast").estimated is True


def test_fallback_rewards_matching_keywords(question):
    hits = fallback_scoring(question, "The chloroplast thylakoid makes ATP and NADPH.")
    misses = fallback_scoring(question, "Something completely unrelated to the topic.")
    assert hits.total_score > misses.total_score


def test_fallback_is_case_insensitive_on_keywords(question):
    upper = fallback_scoring(question, "CHLOROPLAST THYLAKOID ATP NADPH")
    lower = fallback_scoring(question, "chloroplast thylakoid atp nadph")
    assert upper.total_score == lower.total_score


def test_fallback_never_exceeds_the_available_marks(question):
    perfect = "chloroplast thylakoid ATP NADPH " * 50  # every keyword, very long
    result = fallback_scoring(question, perfect)
    assert result.total_score <= question.total_marks
    assert result.percentage <= 100


def test_fallback_on_an_unmarked_question_does_not_divide_by_zero():
    """total_marks=0 is legal in the schema, so the math must survive it."""
    result = fallback_scoring(OpenEndedQuestion(question="Q?"), "some answer")
    assert result.total_score == 0
    assert result.percentage == 0
    assert result.estimated is True
