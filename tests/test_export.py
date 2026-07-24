"""Tests for export/markdown.py.

Exports are rendered from the same captured real-provider fixtures the schema
tests use, so these check the renderers against output a model actually
produced rather than against tidy hand-written models.
"""

from __future__ import annotations

import pytest

from learning_engine.export import material_to_markdown, quiz_to_markdown
from learning_engine.export.markdown import (
    cheat_sheet_to_markdown,
    flashcards_to_markdown,
    key_terms_to_markdown,
    outline_to_markdown,
    study_guide_to_markdown,
    summary_to_markdown,
)
from learning_engine.llm.structured import _extract_json
from learning_engine.models import (
    CheatSheet,
    CheatSheetSection,
    Flashcard,
    FlashcardDeck,
    KeyTerm,
    KeyTerms,
    MarkingCriterion,
    MCQQuestion,
    OpenEndedQuestion,
    Outline,
    OutlineItem,
    Quiz,
    StudyGuide,
    StudyGuideComponents,
    StudyPlan,
    StudySession,
    Summary,
)

# --------------------------------------------------------------------------- #
# Rendering real captured material
# --------------------------------------------------------------------------- #


def test_captured_summary_renders(fixtures):
    summary = Summary.model_validate_json(_extract_json(fixtures.text("summary.txt")))
    markdown = summary_to_markdown(summary)
    assert markdown.startswith("# Summary")
    assert summary.summary[:40] in markdown


def test_captured_flashcards_render_every_card(fixtures):
    deck = FlashcardDeck.model_validate_json(_extract_json(fixtures.text("flashcards.txt")))
    markdown = flashcards_to_markdown(deck)
    for card in deck.flashcards:
        assert card.front in markdown
        assert card.back in markdown


def test_captured_key_terms_render_every_term(fixtures):
    terms = KeyTerms.model_validate_json(_extract_json(fixtures.text("key_terms.txt")))
    markdown = key_terms_to_markdown(terms)
    for term in terms.key_terms:
        assert term.term in markdown
        assert term.definition in markdown


# --------------------------------------------------------------------------- #
# Quiz worksheets
# --------------------------------------------------------------------------- #


@pytest.fixture
def mixed_quiz():
    return Quiz(
        questions=[
            MCQQuestion(
                question="Where do the light reactions occur?",
                options=["A) Stroma", "B) Thylakoid", "C) Nucleus", "D) Ribosome"],
                correct_answer="B",
                explanation="They occur in the thylakoid membrane.",
            ),
            OpenEndedQuestion(
                question="Explain the Calvin cycle.",
                total_marks=5,
                marking_scheme=[MarkingCriterion(criterion="Mentions stroma", marks=2)],
                model_answer="It fixes CO2 in the stroma.",
            ),
        ]
    )


def test_quiz_export_contains_the_questions_and_options(mixed_quiz):
    markdown = quiz_to_markdown(mixed_quiz)
    assert "Where do the light reactions occur?" in markdown
    assert "B) Thylakoid" in markdown
    assert "Explain the Calvin cycle." in markdown
    assert "(5.0 marks)" in markdown or "(5 marks)" in markdown


def test_quiz_export_has_an_answer_key_by_default(mixed_quiz):
    markdown = quiz_to_markdown(mixed_quiz)
    assert "## Answer Key" in markdown
    assert "They occur in the thylakoid membrane." in markdown
    assert "It fixes CO2 in the stroma." in markdown


def test_quiz_export_can_omit_the_answers(mixed_quiz):
    """A worksheet to hand out before the answers are wanted."""
    markdown = quiz_to_markdown(mixed_quiz, include_answers=False)
    assert "Where do the light reactions occur?" in markdown
    assert "Answer Key" not in markdown
    assert "They occur in the thylakoid membrane." not in markdown


def test_answer_key_comes_after_every_question(mixed_quiz):
    markdown = quiz_to_markdown(mixed_quiz)
    assert markdown.index("Explain the Calvin cycle.") < markdown.index("## Answer Key")


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #


def test_nested_outline_indents_by_depth():
    outline = Outline(
        outline=[
            OutlineItem(
                marker="I.",
                text="Photosynthesis",
                children=[OutlineItem(marker="A.", text="Light reactions")],
            )
        ]
    )
    markdown = outline_to_markdown(outline)
    assert "- I. Photosynthesis" in markdown
    assert "  - A. Light reactions" in markdown


def test_study_guide_demotes_component_headings_to_keep_one_outline():
    """Every component renders with an H1; inside a guide they must become H2."""
    guide = StudyGuide(
        title="Biology Guide",
        components=StudyGuideComponents(
            summary=Summary(summary="Plants make sugar."),
            key_terms=KeyTerms(key_terms=[KeyTerm(term="Stroma", definition="Fluid interior.")]),
        ),
        study_plan=StudyPlan(
            total_time="2 hours", sessions=[StudySession(session=1, focus="Read", time="30 min")]
        ),
    )
    markdown = study_guide_to_markdown(guide)

    assert markdown.count("\n# ") == 0, "only the title may be an H1"
    assert markdown.startswith("# Biology Guide")
    assert "## Summary" in markdown
    assert "## Key Terms" in markdown
    assert "| 1 | Read | 30 min |" in markdown


def test_cheat_sheet_terms_render_as_a_table():
    cheat = CheatSheet(
        title="Bio Cheat Sheet",
        sections=[CheatSheetSection(heading="Basics", content="Start here.", items=["One"])],
    )
    markdown = cheat_sheet_to_markdown(cheat)
    assert "# Bio Cheat Sheet" in markdown
    assert "## Basics" in markdown
    assert "- One" in markdown


def test_empty_sections_do_not_leave_stray_headings():
    markdown = summary_to_markdown(Summary(summary="Just prose."))
    assert "Key Points" not in markdown
    assert "Main Topics" not in markdown
    assert "\n\n\n" not in markdown


def test_export_of_an_empty_deck_still_produces_a_document():
    markdown = flashcards_to_markdown(FlashcardDeck())
    assert markdown.strip() == "# Flashcards (0 cards)"


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "material",
    [
        Summary(summary="s"),
        CheatSheet(),
        FlashcardDeck(flashcards=[Flashcard(front="f", back="b")]),
        Outline(),
        KeyTerms(),
        StudyGuide(),
        Quiz(),
    ],
    ids=lambda m: type(m).__name__,
)
def test_every_material_model_has_a_renderer(material):
    assert material_to_markdown(material).strip()


def test_an_unknown_type_fails_loudly_rather_than_exporting_nothing():
    with pytest.raises(TypeError, match="No Markdown renderer"):
        material_to_markdown({"not": "a model"})
