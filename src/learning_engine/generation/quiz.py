"""Typed quiz generation and open-ended scoring.

Replaces app.generate_quiz and open_ended_processor. Because mixed-quiz
generation lives here (not in the Streamlit app), the old circular import
`from app import generate_quiz` (BUG-7) is gone.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from openai import OpenAI

from learning_engine.generation.prompts import (
    build_open_ended_prompt,
    build_quiz_prompt,
    build_scoring_prompt,
    build_summarize_prompt,
)
from learning_engine.llm.client import GenerationFailed
from learning_engine.llm.providers import ProviderConfig
from learning_engine.llm.structured import generate_structured
from learning_engine.models import (
    MCQQuiz,
    OpenEndedQuestion,
    OpenEndedQuiz,
    Quiz,
    ScoringResult,
)

GENERATION_TEMPERATURE = 0.7
GENERATION_MAX_TOKENS = 2000
SCORING_TEMPERATURE = 0.3
SCORING_MAX_TOKENS = 700
SUMMARY_TEMPERATURE = 0.5


def generate_quiz(
    client: OpenAI,
    cfg: ProviderConfig,
    text: str,
    quiz_type: str,
    num_questions: int = 5,
    difficulty: str = "Standard",
    *,
    mcq_count: int = 0,
    tf_count: int = 0,
) -> Quiz:
    """Generate a Multiple Choice / True or False / Mixed (MCQ + T/F) quiz."""
    prompt = build_quiz_prompt(text, quiz_type, num_questions, difficulty, mcq_count, tf_count)
    result = generate_structured(
        client, cfg.chat_model, prompt, MCQQuiz,
        temperature=GENERATION_TEMPERATURE, max_tokens=GENERATION_MAX_TOKENS,
    )
    return Quiz(questions=list(result.questions))


def generate_open_ended(
    client: OpenAI,
    cfg: ProviderConfig,
    text: str,
    num_questions: int = 3,
    difficulty: str = "Standard",
) -> Quiz:
    """Generate open-ended questions with marking schemes."""
    prompt = build_open_ended_prompt(text, num_questions, difficulty)
    result = generate_structured(
        client, cfg.chat_model, prompt, OpenEndedQuiz,
        temperature=GENERATION_TEMPERATURE, max_tokens=GENERATION_MAX_TOKENS,
    )
    return Quiz(questions=list(result.questions))


def generate_mixed(
    client: OpenAI,
    cfg: ProviderConfig,
    text: str,
    mcq_count: int = 3,
    tf_count: int = 2,
    open_count: int = 2,
    difficulty: str = "Standard",
) -> Quiz:
    """Generate a full mix of MCQ, T/F, and open-ended questions."""
    traditional = generate_quiz(
        client, cfg, text, "Mixed (MCQ + T/F)", mcq_count + tf_count, difficulty,
        mcq_count=mcq_count, tf_count=tf_count,
    )
    open_ended = generate_open_ended(client, cfg, text, open_count, difficulty)
    return Quiz(questions=list(traditional.questions) + list(open_ended.questions))


def score_open_ended(
    client: OpenAI,
    cfg: ProviderConfig,
    question: OpenEndedQuestion,
    user_answer: str,
) -> ScoringResult:
    """Score an open-ended answer, falling back to a labeled estimate on failure."""
    if not user_answer.strip():
        return ScoringResult(
            total_score=0,
            max_score=question.total_marks,
            percentage=0,
            overall_feedback="No answer provided.",
        )
    prompt = build_scoring_prompt(question, user_answer)
    try:
        result = generate_structured(
            client, cfg.scoring_model, prompt, ScoringResult,
            temperature=SCORING_TEMPERATURE, max_tokens=SCORING_MAX_TOKENS,
        )
    except GenerationFailed:
        return fallback_scoring(question, user_answer)

    if result.max_score <= 0:
        result.max_score = question.total_marks
    if result.max_score:
        result.percentage = round(result.total_score / result.max_score * 100, 1)
    return result


def fallback_scoring(question: OpenEndedQuestion, user_answer: str) -> ScoringResult:
    """Honest keyword-based estimate when AI scoring is unavailable (estimated=True)."""
    total_marks = question.total_marks or 0
    word_count = len(user_answer.split())
    base_score = min(1.0, word_count / 50)

    keyword_hits = 0
    total_keywords = 0
    for criterion in question.marking_scheme:
        total_keywords += len(criterion.keywords)
        keyword_hits += sum(
            1 for kw in criterion.keywords if kw.lower() in user_answer.lower()
        )
    keyword_ratio = keyword_hits / max(total_keywords, 1)
    final = (base_score * 0.3 + keyword_ratio * 0.7) * total_marks

    return ScoringResult(
        total_score=round(final, 1),
        max_score=total_marks,
        percentage=round((final / total_marks) * 100, 1) if total_marks else 0,
        overall_feedback="Estimated with keyword matching (AI scoring unavailable).",
        strengths=["Answer provided"] if word_count else [],
        improvements=["Add more specific detail"],
        estimated=True,
    )


def summarize(client: OpenAI, cfg: ProviderConfig, text: str) -> str:
    """Return a free-text (non-JSON) summary of `text`."""
    resp = client.chat.completions.create(
        model=cfg.chat_model,
        messages=[{"role": "user", "content": build_summarize_prompt(text)}],
        temperature=SUMMARY_TEMPERATURE,
    )
    return (resp.choices[0].message.content or "").strip()
