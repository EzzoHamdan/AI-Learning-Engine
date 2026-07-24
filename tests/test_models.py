"""Validate real captured provider output against the Pydantic schemas.

Everything in `tests/fixtures/` is a RAW response from a live model
(`gemma4:31b-cloud` via Ollama), saved exactly as it came back — before any
parsing. That makes these the highest-value regression tests in the suite: they
fail if a schema change stops accepting output that a real model really
produces, which hand-written JSON can never detect.

Regenerate them by re-running the capture script against a live provider; do not
hand-edit the .txt files, or they stop being evidence.
"""

from __future__ import annotations

import pytest

from learning_engine.llm.structured import _extract_json
from learning_engine.models import (
    FlashcardDeck,
    KeyTerms,
    MCQQuiz,
    OpenEndedQuestion,
    OpenEndedQuiz,
    ScoringResult,
    Summary,
)

# fixture file -> the schema it must satisfy
CORPUS = [
    ("mcq_quiz.txt", MCQQuiz),
    ("tf_quiz.txt", MCQQuiz),
    ("open_ended_quiz.txt", OpenEndedQuiz),
    ("scoring_result.txt", ScoringResult),
    ("summary.txt", Summary),
    ("flashcards.txt", FlashcardDeck),
    ("key_terms.txt", KeyTerms),
]


@pytest.mark.parametrize(("name", "schema"), CORPUS, ids=[n for n, _ in CORPUS])
def test_captured_response_validates(fixtures, name, schema):
    """Every captured response parses cleanly into its schema."""
    parsed = schema.model_validate_json(_extract_json(fixtures.text(name)))
    assert isinstance(parsed, schema)


# --------------------------------------------------------------------------- #
# Content invariants the UI relies on
# --------------------------------------------------------------------------- #


def test_captured_mcq_has_four_lettered_options_and_a_letter_answer(fixtures):
    quiz = MCQQuiz.model_validate_json(_extract_json(fixtures.text("mcq_quiz.txt")))
    assert quiz.questions
    for question in quiz.questions:
        assert question.type == "mcq"
        assert len(question.options) == 4
        assert question.correct_answer in {"A", "B", "C", "D"}
        # The renderer strips the "A) " prefix, so it must be there.
        assert all(opt[:2] in {"A)", "B)", "C)", "D)"} for opt in question.options)


def test_captured_true_false_uses_the_binary_option_pair(fixtures):
    quiz = MCQQuiz.model_validate_json(_extract_json(fixtures.text("tf_quiz.txt")))
    assert quiz.questions
    for question in quiz.questions:
        assert question.options == ["True", "False"]
        assert question.correct_answer in {"True", "False"}


def test_captured_open_ended_carries_a_usable_marking_scheme(fixtures):
    quiz = OpenEndedQuiz.model_validate_json(_extract_json(fixtures.text("open_ended_quiz.txt")))
    assert quiz.questions
    for question in quiz.questions:
        assert question.type == "open_ended"
        assert question.total_marks > 0
        assert question.marking_scheme, "scoring needs criteria to mark against"
        assert question.model_answer
        # Criterion marks should account for the stated total.
        assert sum(c.marks for c in question.marking_scheme) == pytest.approx(
            question.total_marks, rel=0.5
        )


def test_captured_scoring_result_is_within_bounds(fixtures):
    result = ScoringResult.model_validate_json(_extract_json(fixtures.text("scoring_result.txt")))
    assert 0 <= result.total_score <= result.max_score
    assert result.overall_feedback
    # Real AI scoring must not be labeled as the keyword estimate.
    assert result.estimated is False


def test_captured_flashcards_have_both_faces(fixtures):
    deck = FlashcardDeck.model_validate_json(_extract_json(fixtures.text("flashcards.txt")))
    assert deck.flashcards
    for card in deck.flashcards:
        assert card.front and card.back


def test_captured_key_terms_have_definitions(fixtures):
    terms = KeyTerms.model_validate_json(_extract_json(fixtures.text("key_terms.txt")))
    assert terms.key_terms
    for term in terms.key_terms:
        assert term.term and term.definition
        assert term.importance in {"high", "medium", "low"}


def test_captured_summary_has_prose(fixtures):
    summary = Summary.model_validate_json(_extract_json(fixtures.text("summary.txt")))
    assert summary.summary.strip()


# --------------------------------------------------------------------------- #
# Schema tolerance
# --------------------------------------------------------------------------- #


def test_optional_fields_default_so_the_ui_can_use_attribute_access():
    """Phase 4's promise: no defensive .get() in the render functions."""
    question = OpenEndedQuestion(question="Q?")
    assert question.marking_scheme == []
    assert question.model_answer == ""
    assert question.total_marks == 0


def test_a_question_missing_its_text_is_rejected():
    """`question` is the one field with no sensible default."""
    with pytest.raises(ValueError):
        OpenEndedQuestion()


def test_unknown_extra_keys_from_a_chatty_model_are_ignored():
    parsed = Summary.model_validate_json('{"summary": "s", "confidence": 0.9}')
    assert parsed.summary == "s"
    assert not hasattr(parsed, "confidence")
