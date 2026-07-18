"""Pydantic domain models — the typed schema for all LLM output.

These mirror the JSON shapes previously embedded as f-strings in the prompts
(the de-facto schema). Optional fields carry defaults so the UI can use plain
attribute access (`quiz.questions[i].explanation`) without defensive `.get()`.

This module imports nothing from the rest of the project (architecture rule R1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Quiz questions
# --------------------------------------------------------------------------- #


class MCQQuestion(BaseModel):
    """A multiple-choice or true/false question."""

    question: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    type: Literal["mcq", "tf"] = "mcq"


class MarkingCriterion(BaseModel):
    criterion: str
    marks: float = 0
    keywords: list[str] = Field(default_factory=list)


class OpenEndedQuestion(BaseModel):
    """A written-answer question with a marking scheme."""

    question: str
    total_marks: float = 0
    marking_scheme: list[MarkingCriterion] = Field(default_factory=list)
    model_answer: str = ""
    type: Literal["open_ended"] = "open_ended"


# Generation schemas are homogeneous (one question type) so the JSON schema
# handed to the model stays simple; the mixed Quiz below is assembled in Python.
class MCQQuiz(BaseModel):
    questions: list[MCQQuestion] = Field(default_factory=list)


class OpenEndedQuiz(BaseModel):
    questions: list[OpenEndedQuestion] = Field(default_factory=list)


class Quiz(BaseModel):
    """Runtime container holding a (possibly mixed) list of questions."""

    questions: list[MCQQuestion | OpenEndedQuestion] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Open-ended scoring
# --------------------------------------------------------------------------- #


class CriterionScore(BaseModel):
    criterion: str = ""
    marks_awarded: float = 0
    max_marks: float = 0
    feedback: str = ""


class ScoringResult(BaseModel):
    total_score: float = 0
    max_score: float = 0
    percentage: float = 0
    overall_feedback: str = ""
    criterion_scores: list[CriterionScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    # True when produced by the keyword fallback rather than real AI scoring.
    estimated: bool = False


# --------------------------------------------------------------------------- #
# Study materials
# --------------------------------------------------------------------------- #


class Summary(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    main_topics: list[str] = Field(default_factory=list)
    word_count: int = 0
    summary_type: str = ""


class CheatSheetSection(BaseModel):
    heading: str = ""
    content: str = ""
    items: list[str] = Field(default_factory=list)


class CheatTerm(BaseModel):
    term: str = ""
    definition: str = ""


class Formula(BaseModel):
    name: str = ""
    formula: str = ""
    explanation: str = ""


class CheatSheet(BaseModel):
    title: str = "Cheat Sheet"
    sections: list[CheatSheetSection] = Field(default_factory=list)
    key_terms: list[CheatTerm] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    quick_tips: list[str] = Field(default_factory=list)
    format_type: str = ""


class Flashcard(BaseModel):
    id: int = 0
    front: str = ""
    back: str = ""
    hint: str = ""
    difficulty: str = "basic"
    category: str = "General"


class FlashcardDeck(BaseModel):
    flashcards: list[Flashcard] = Field(default_factory=list)
    total_cards: int = 0
    categories: list[str] = Field(default_factory=list)
    study_tips: list[str] = Field(default_factory=list)


class OutlineItem(BaseModel):
    level: int = 1
    marker: str = ""
    text: str = ""
    children: list[OutlineItem] = Field(default_factory=list)


class TimeEstimates(BaseModel):
    total_study_time: str = "Unknown"
    per_section: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    outline: list[OutlineItem] = Field(default_factory=list)
    total_sections: int = 0
    max_depth: int = 0
    study_sequence: list[str] = Field(default_factory=list)
    time_estimates: TimeEstimates = Field(default_factory=TimeEstimates)
    outline_depth: str = ""


class KeyTerm(BaseModel):
    term: str = ""
    definition: str = ""
    context: str = ""
    related_terms: list[str] = Field(default_factory=list)
    importance: Literal["high", "medium", "low"] = "medium"


class TermCategory(BaseModel):
    category: str = ""
    terms: list[str] = Field(default_factory=list)


class KeyTerms(BaseModel):
    key_terms: list[KeyTerm] = Field(default_factory=list)
    total_terms: int = 0
    categories: list[TermCategory] = Field(default_factory=list)
    study_suggestions: list[str] = Field(default_factory=list)


class StudySession(BaseModel):
    session: int = 0
    focus: str = ""
    time: str = ""


class StudyPlan(BaseModel):
    total_time: str = "Variable"
    sessions: list[StudySession] = Field(default_factory=list)


class StudyGuideComponents(BaseModel):
    summary: Summary | None = None
    cheat_sheet: CheatSheet | None = None
    flashcards: FlashcardDeck | None = None
    key_terms: KeyTerms | None = None


class StudyGuide(BaseModel):
    title: str = "Study Guide"
    generated_at: str = ""
    guide_type: str = ""
    components: StudyGuideComponents = Field(default_factory=StudyGuideComponents)
    study_plan: StudyPlan = Field(default_factory=StudyPlan)
    errors: list[str] = Field(default_factory=list)
