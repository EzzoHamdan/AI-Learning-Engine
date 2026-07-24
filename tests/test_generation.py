"""Tests for generation/prompts.py and generation/quiz.py.

Two things matter here. The difficulty instructions used to exist in three
divergent copies (app.py, settings.DIFFICULTY_CONFIG, open_ended_processor);
Phase 4 collapsed them into prompts.py and Phase 7 deleted the last stray copy,
so "appears exactly once" is a regression test for that whole effort. And the
generation knobs became settings in Phase 7, so the wiring from env to API call
is worth asserting end to end.
"""

from __future__ import annotations

import pytest

from learning_engine.generation import materials as materials_gen
from learning_engine.generation import quiz as quiz_gen
from learning_engine.generation.prompts import (
    OPEN_ENDED_DIFFICULTY_INSTRUCTIONS,
    QUIZ_DIFFICULTY_INSTRUCTIONS,
    build_open_ended_prompt,
    build_quiz_prompt,
    build_scoring_prompt,
)
from learning_engine.llm.providers import Provider, ProviderConfig
from learning_engine.models import MarkingCriterion, OpenEndedQuestion
from learning_engine.settings import reload_settings

TEXT = "Mitochondria are the powerhouse of the cell."


@pytest.fixture
def cfg():
    return ProviderConfig(
        provider=Provider.OLLAMA,
        base_url="http://127.0.0.1:11434",
        api_key="ollama",
        chat_model="test-chat",
        scoring_model="test-scoring",
    )


# --------------------------------------------------------------------------- #
# Prompt assembly
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("difficulty", ["Standard", "Advanced", "Extreme"])
def test_difficulty_instructions_appear_exactly_once(difficulty):
    prompt = build_quiz_prompt(TEXT, "Multiple Choice", 3, difficulty)
    instructions = QUIZ_DIFFICULTY_INSTRUCTIONS[difficulty].strip()
    assert prompt.count(instructions) == 1


@pytest.mark.parametrize("difficulty", ["Standard", "Advanced", "Extreme"])
def test_open_ended_difficulty_instructions_appear_exactly_once(difficulty):
    prompt = build_open_ended_prompt(TEXT, 2, difficulty)
    instructions = OPEN_ENDED_DIFFICULTY_INSTRUCTIONS[difficulty].strip()
    assert prompt.count(instructions) == 1


def test_unknown_difficulty_falls_back_to_standard():
    prompt = build_quiz_prompt(TEXT, "Multiple Choice", 3, "Nightmare")
    assert QUIZ_DIFFICULTY_INSTRUCTIONS["Standard"].strip() in prompt


def test_quiz_prompt_carries_the_content_and_the_count():
    prompt = build_quiz_prompt(TEXT, "Multiple Choice", 7, "Standard")
    assert TEXT in prompt
    assert "exactly 7" in prompt


def test_mixed_prompt_states_the_per_type_split():
    prompt = build_quiz_prompt(TEXT, "Mixed (MCQ + T/F)", 5, "Standard", mcq_count=3, tf_count=2)
    assert "3 multiple-choice" in prompt
    assert "2 true/false" in prompt


def test_true_false_prompt_does_not_ask_for_four_options():
    prompt = build_quiz_prompt(TEXT, "True or False", 3, "Standard")
    assert '["True", "False"]' in prompt
    assert "exactly 4 options" not in prompt


def test_scoring_prompt_includes_the_scheme_the_model_must_mark_against():
    question = OpenEndedQuestion(
        question="Explain photosynthesis.",
        total_marks=5,
        marking_scheme=[
            MarkingCriterion(criterion="Mentions chloroplast", marks=2, keywords=["chloroplast"])
        ],
        model_answer="It happens in the chloroplast.",
    )
    prompt = build_scoring_prompt(question, "It happens in the chloroplast.")
    assert "Explain photosynthesis." in prompt
    assert "Mentions chloroplast" in prompt
    assert "chloroplast" in prompt  # the keyword list
    assert "TOTAL MARKS: 5" in prompt


# --------------------------------------------------------------------------- #
# Settings wiring (Phase 7)
# --------------------------------------------------------------------------- #


def test_quiz_generation_uses_the_configured_temperature_and_tokens(fake_llm, cfg, monkeypatch):
    monkeypatch.setenv("LLM__GENERATION_TEMPERATURE", "0.11")
    monkeypatch.setenv("LLM__GENERATION_MAX_TOKENS", "1234")
    reload_settings()

    client = fake_llm({"questions": [{"question": "Q?", "type": "mcq"}]})
    quiz_gen.generate_quiz(client, cfg, TEXT, "Multiple Choice", 1)

    call = client.calls[0]
    assert call.temperature == 0.11
    assert call.max_tokens == 1234
    assert call.model == "test-chat"


def test_scoring_uses_the_scoring_model_not_the_chat_model(fake_llm, cfg, monkeypatch):
    monkeypatch.setenv("LLM__SCORING_TEMPERATURE", "0.02")
    reload_settings()

    question = OpenEndedQuestion(question="Q?", total_marks=4)
    client = fake_llm({"total_score": 3, "max_score": 4, "overall_feedback": "ok"})
    quiz_gen.score_open_ended(client, cfg, question, "an answer")

    assert client.calls[0].model == "test-scoring"
    assert client.calls[0].temperature == 0.02


def test_materials_use_their_own_temperature(fake_llm, cfg, monkeypatch):
    monkeypatch.setenv("LLM__MATERIALS_TEMPERATURE", "0.42")
    reload_settings()

    client = fake_llm({"summary": "s"})
    materials_gen.generate_summary(client, cfg, TEXT, "concise")
    assert client.calls[0].temperature == 0.42


# --------------------------------------------------------------------------- #
# Quiz composition
# --------------------------------------------------------------------------- #


def test_generate_mixed_combines_both_generations_in_order(fake_llm, cfg):
    """Covers the path that used to need `from app import generate_quiz` (BUG-7)."""
    client = fake_llm(
        {"questions": [{"question": "MCQ?", "type": "mcq"}, {"question": "TF?", "type": "tf"}]},
        {"questions": [{"question": "Open?", "type": "open_ended", "total_marks": 5}]},
    )
    quiz = quiz_gen.generate_mixed(client, cfg, TEXT, mcq_count=1, tf_count=1, open_count=1)

    assert [q.type for q in quiz.questions] == ["mcq", "tf", "open_ended"]
    assert client.call_count == 2


def test_generate_mixed_has_no_circular_import():
    """BUG-7 regression: quiz generation must not reach back into the UI."""
    import learning_engine.generation.quiz as module

    source = module.__file__
    assert "learning_engine" in source
    assert not hasattr(module, "app")
