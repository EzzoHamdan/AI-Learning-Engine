"""Typed study-material generation.

Replaces study_materials_generator.py. Each function returns a validated
Pydantic model via generate_structured (no regex parsing, no fallback dicts);
failures raise GenerationFailed for the UI to report honestly.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from openai import OpenAI

from learning_engine.llm.providers import ProviderConfig
from learning_engine.llm.structured import generate_structured
from learning_engine.models import (
    CheatSheet,
    FlashcardDeck,
    KeyTerms,
    Outline,
    StudyGuide,
    StudyGuideComponents,
    StudyPlan,
    Summary,
)

TEMPERATURE = 0.3  # lower for more consistent study materials

_SUMMARY_INSTRUCTIONS = {
    "detailed": "Comprehensive, detailed summary covering all major topics with examples; 300-500 words.",
    "concise": "Concise summary of the essential points in clear language; 150-250 words.",
    "bullet_points": "Well-organized hierarchical bullet-point summary grouping related concepts.",
}
_CHEAT_INSTRUCTIONS = {
    "comprehensive": "Key concepts, definitions, important formulas/principles, procedures, and memory aids.",
    "formulas": "Focus on formulas and equations with variable definitions and example calculations.",
    "definitions": "Focus on key terms and definitions, acronyms, classifications, and related concepts.",
    "quick_ref": "Ultra-concise quick reference: essential facts only, short phrases, easy to scan.",
}
_FLASHCARD_INSTRUCTIONS = {
    "basic": "Simple definitions, facts, and straightforward question-answer pairs.",
    "intermediate": "Concept explanations, applications, comparisons, and problem-solving.",
    "advanced": "Complex analysis, synthesis, and multi-step problem solving.",
    "mixed": "A mix: ~30% basic, ~40% intermediate, ~30% advanced.",
}
_OUTLINE_INSTRUCTIONS = {
    "overview": "High-level overview: main topics only, 1-2 levels deep.",
    "detailed": "Detailed outline: topics and subtopics, 3-4 levels, with key examples.",
    "comprehensive": "Full hierarchical structure, 4-5 levels, with examples and cross-references.",
}
_STUDY_PLANS: dict[str, StudyPlan] = {
    "comprehensive": StudyPlan(
        total_time="4-6 hours",
        sessions=[
            {"session": 1, "focus": "Read summary and outline", "time": "45-60 min"},
            {"session": 2, "focus": "Review cheat sheet and key terms", "time": "30-45 min"},
            {"session": 3, "focus": "Practice with flashcards", "time": "45-60 min"},
            {"session": 4, "focus": "Review and self-test", "time": "60-90 min"},
            {"session": 5, "focus": "Final review before exam", "time": "30-45 min"},
        ],
    ),
    "exam_prep": StudyPlan(
        total_time="6-8 hours",
        sessions=[
            {"session": 1, "focus": "Study outline thoroughly", "time": "90-120 min"},
            {"session": 2, "focus": "Memorize key terms", "time": "45-60 min"},
            {"session": 3, "focus": "Intensive flashcard practice", "time": "60-90 min"},
            {"session": 4, "focus": "Timed self-testing", "time": "60-90 min"},
        ],
    ),
    "quick_review": StudyPlan(
        total_time="2-3 hours",
        sessions=[
            {"session": 1, "focus": "Skim summary and cheat sheet", "time": "30-45 min"},
            {"session": 2, "focus": "Run through flashcards", "time": "30-45 min"},
            {"session": 3, "focus": "Review key terms", "time": "30 min"},
        ],
    ),
}


def _instr(mapping: dict[str, str], key: str, default: str) -> str:
    return mapping.get(key, mapping[default])


def generate_summary(client: OpenAI, cfg: ProviderConfig, text: str, summary_type: str = "detailed") -> Summary:
    prompt = (
        f"Create a {summary_type} summary of the content.\n"
        f"{_instr(_SUMMARY_INSTRUCTIONS, summary_type, 'detailed')}\n"
        f"Set summary_type to {summary_type!r}.\n\nContent:\n{text}"
    )
    return generate_structured(client, cfg.chat_model, prompt, Summary, temperature=TEMPERATURE)


def generate_cheat_sheet(client: OpenAI, cfg: ProviderConfig, text: str, format_type: str = "comprehensive") -> CheatSheet:
    prompt = (
        f"Create a study cheat sheet from the content.\n"
        f"{_instr(_CHEAT_INSTRUCTIONS, format_type, 'comprehensive')}\n"
        "Use clear sections with headings and bullet items; include key terms, any formulas, "
        f"and quick tips. Set format_type to {format_type!r}.\n\nContent:\n{text}"
    )
    return generate_structured(client, cfg.chat_model, prompt, CheatSheet, temperature=TEMPERATURE)


def generate_flashcards(client: OpenAI, cfg: ProviderConfig, text: str, card_count: int = 10, difficulty: str = "mixed") -> FlashcardDeck:
    prompt = (
        f"Create exactly {card_count} study flashcards from the content.\n"
        f"{_instr(_FLASHCARD_INSTRUCTIONS, difficulty, 'mixed')}\n"
        "Each card has a focused question (front), a comprehensive answer (back), an optional "
        "hint, a difficulty (basic/intermediate/advanced), and a category.\n\nContent:\n{}"
    ).format(text)
    return generate_structured(client, cfg.chat_model, prompt, FlashcardDeck, temperature=TEMPERATURE)


def generate_outline(client: OpenAI, cfg: ProviderConfig, text: str, outline_depth: str = "detailed") -> Outline:
    prompt = (
        f"Create a structured study outline from the content.\n"
        f"{_instr(_OUTLINE_INSTRUCTIONS, outline_depth, 'detailed')}\n"
        "Use Roman numerals for main topics (level 1), capital letters for subtopics (level 2), "
        "numbers for details (level 3); nest via each item's children. Provide total_sections, "
        f"max_depth, study_sequence, and time_estimates. Set outline_depth to {outline_depth!r}.\n\n"
        f"Content:\n{text}"
    )
    return generate_structured(client, cfg.chat_model, prompt, Outline, temperature=TEMPERATURE)


def generate_key_terms(client: OpenAI, cfg: ProviderConfig, text: str, term_count: int = 15) -> KeyTerms:
    prompt = (
        f"Extract the {term_count} most important key terms from the content. For each term give a "
        "clear definition, the context it's used in, related terms, and an importance of "
        "high/medium/low. Also provide category groupings and study_suggestions.\n\n"
        f"Content:\n{text}"
    )
    return generate_structured(client, cfg.chat_model, prompt, KeyTerms, temperature=TEMPERATURE)


# guide_type -> (summary_type, cheat_format, card_count, flashcard_difficulty, term_count)
_GUIDE_RECIPES = {
    "comprehensive": ("detailed", "comprehensive", 15, "mixed", 20),
    "exam_prep": ("concise", "quick_ref", 20, "mixed", 25),
    "quick_review": ("bullet_points", "definitions", 10, "basic", 10),
}


def generate_study_guide(
    client: OpenAI, cfg: ProviderConfig, text: str, guide_type: str = "comprehensive", *, generated_at: str = ""
) -> StudyGuide:
    """Compose a full study guide. Component failures are recorded, not fatal."""
    summary_type, cheat_format, card_count, fc_difficulty, term_count = _GUIDE_RECIPES.get(
        guide_type, _GUIDE_RECIPES["comprehensive"]
    )
    components = StudyGuideComponents()
    errors: list[str] = []

    for name, thunk in (
        ("summary", lambda: generate_summary(client, cfg, text, summary_type)),
        ("cheat_sheet", lambda: generate_cheat_sheet(client, cfg, text, cheat_format)),
        ("flashcards", lambda: generate_flashcards(client, cfg, text, card_count, fc_difficulty)),
        ("key_terms", lambda: generate_key_terms(client, cfg, text, term_count)),
    ):
        try:
            setattr(components, name, thunk())
        except Exception as exc:  # keep building the rest of the guide
            errors.append(f"{name}: {exc}")

    return StudyGuide(
        title=f"Study Guide - {guide_type.title()}",
        generated_at=generated_at,
        guide_type=guide_type,
        components=components,
        study_plan=_STUDY_PLANS.get(guide_type, _STUDY_PLANS["comprehensive"]),
        errors=errors,
    )
