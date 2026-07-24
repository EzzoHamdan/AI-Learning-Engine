"""Render domain models to Markdown.

One renderer per model, dispatched by `material_to_markdown`. Everything is a
plain function of the model, so exports are testable without a browser and the
UI only has to attach a download button.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from learning_engine.models import (
    CheatSheet,
    FlashcardDeck,
    KeyTerms,
    MCQQuestion,
    OpenEndedQuestion,
    Outline,
    OutlineItem,
    Quiz,
    StudyGuide,
    Summary,
)


def _lines(*parts: str) -> str:
    """Join sections, collapsing the blank-line runs that empty sections leave."""
    text = "\n".join(part for part in parts if part is not None)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"


def _bullets(heading: str, items: list[str]) -> str:
    if not items:
        return ""
    body = "\n".join(f"- {item}" for item in items)
    return f"\n## {heading}\n\n{body}\n"


# --------------------------------------------------------------------------- #
# Study materials
# --------------------------------------------------------------------------- #


def summary_to_markdown(summary: Summary) -> str:
    kind = f" ({summary.summary_type})" if summary.summary_type else ""
    return _lines(
        f"# Summary{kind}\n",
        f"{summary.summary}\n" if summary.summary else "",
        _bullets("Key Points", summary.key_points),
        _bullets("Main Topics", summary.main_topics),
    )


def cheat_sheet_to_markdown(cheat: CheatSheet) -> str:
    sections = []
    for section in cheat.sections:
        body = section.content.strip()
        items = "\n".join(f"- {item}" for item in section.items)
        sections.append(
            f"\n## {section.heading}\n\n{body}\n\n{items}\n"
            if items
            else f"\n## {section.heading}\n\n{body}\n"
        )

    terms = ""
    if cheat.key_terms:
        rows = "\n".join(f"| {t.term} | {t.definition} |" for t in cheat.key_terms)
        terms = f"\n## Key Terms\n\n| Term | Definition |\n| --- | --- |\n{rows}\n"

    formulas = ""
    if cheat.formulas:
        blocks = "\n".join(
            f"**{f.name}**\n\n```\n{f.formula}\n```\n\n{f.explanation}\n" for f in cheat.formulas
        )
        formulas = f"\n## Formulas\n\n{blocks}"

    return _lines(
        f"# {cheat.title}\n",
        "".join(sections),
        terms,
        formulas,
        _bullets("Quick Tips", cheat.quick_tips),
    )


def flashcards_to_markdown(deck: FlashcardDeck) -> str:
    cards = []
    for index, card in enumerate(deck.flashcards, start=1):
        hint = f"\n> Hint: {card.hint}\n" if card.hint else ""
        meta = " · ".join(filter(None, [card.difficulty, card.category]))
        cards.append(f"\n### {index}. {card.front}\n{hint}\n{card.back}\n\n_{meta}_\n")

    return _lines(
        f"# Flashcards ({len(deck.flashcards)} cards)\n",
        "".join(cards),
        _bullets("Study Tips", deck.study_tips),
    )


def _outline_items(items: list[OutlineItem], depth: int = 0) -> str:
    out = []
    for item in items:
        marker = f"{item.marker} " if item.marker else ""
        out.append(f"{'  ' * depth}- {marker}{item.text}")
        if item.children:
            out.append(_outline_items(item.children, depth + 1))
    return "\n".join(out)


def outline_to_markdown(outline: Outline) -> str:
    depth = f" ({outline.outline_depth})" if outline.outline_depth else ""
    estimate = outline.time_estimates.total_study_time
    return _lines(
        f"# Study Outline{depth}\n",
        f"{_outline_items(outline.outline)}\n" if outline.outline else "",
        f"\n_Estimated study time: {estimate}_\n" if estimate and estimate != "Unknown" else "",
        _bullets("Study Sequence", outline.study_sequence),
    )


def key_terms_to_markdown(terms: KeyTerms) -> str:
    entries = []
    for term in terms.key_terms:
        related = f"\nRelated: {', '.join(term.related_terms)}" if term.related_terms else ""
        context = f"\n\n{term.context}" if term.context else ""
        entries.append(
            f"\n### {term.term}\n\n{term.definition}{context}"
            f"\n\n_Importance: {term.importance}_{related}\n"
        )

    categories = ""
    if terms.categories:
        rows = "\n".join(f"- **{c.category}**: {', '.join(c.terms)}" for c in terms.categories)
        categories = f"\n## Categories\n\n{rows}\n"

    return _lines(
        f"# Key Terms ({len(terms.key_terms)})\n",
        "".join(entries),
        categories,
        _bullets("Study Suggestions", terms.study_suggestions),
    )


def study_guide_to_markdown(guide: StudyGuide) -> str:
    parts = [f"# {guide.title}\n"]
    if guide.generated_at:
        parts.append(f"_Generated {guide.generated_at} · {guide.guide_type}_\n")

    if guide.study_plan.sessions:
        rows = "\n".join(
            f"| {s.session} | {s.focus} | {s.time} |" for s in guide.study_plan.sessions
        )
        parts.append(
            f"\n## Study Plan ({guide.study_plan.total_time})\n\n"
            f"| Session | Focus | Time |\n| --- | --- | --- |\n{rows}\n"
        )

    # Demote each component's H1 to H2 so the guide keeps one document outline.
    components = guide.components
    if components.summary is not None:
        parts.append("\n" + _demote_headings(summary_to_markdown(components.summary)))
    if components.cheat_sheet is not None:
        parts.append("\n" + _demote_headings(cheat_sheet_to_markdown(components.cheat_sheet)))
    if components.flashcards is not None:
        parts.append("\n" + _demote_headings(flashcards_to_markdown(components.flashcards)))
    if components.key_terms is not None:
        parts.append("\n" + _demote_headings(key_terms_to_markdown(components.key_terms)))

    if guide.errors:
        parts.append(_bullets("Generation Notes", guide.errors))

    return _lines(*parts)


def _demote_headings(markdown: str) -> str:
    return "\n".join(f"#{line}" if line.startswith("#") else line for line in markdown.splitlines())


# --------------------------------------------------------------------------- #
# Quizzes
# --------------------------------------------------------------------------- #


def quiz_to_markdown(quiz: Quiz, *, include_answers: bool = True) -> str:
    """Render a quiz as a worksheet, with an optional answer key at the end."""
    questions = []
    answers = []

    for index, question in enumerate(quiz.questions, start=1):
        if isinstance(question, OpenEndedQuestion):
            questions.append(
                f"\n**{index}.** {question.question} _({question.total_marks} marks)_\n"
            )
            if include_answers:
                scheme = "\n".join(
                    f"  - {c.criterion} ({c.marks} marks)" for c in question.marking_scheme
                )
                answers.append(
                    f"\n**{index}.** Model answer:\n\n{question.model_answer}\n\n{scheme}\n"
                )
        elif isinstance(question, MCQQuestion):
            options = "\n".join(f"- {option}" for option in question.options)
            questions.append(f"\n**{index}.** {question.question}\n\n{options}\n")
            if include_answers:
                explanation = f" — {question.explanation}" if question.explanation else ""
                answers.append(f"- **{index}.** {question.correct_answer}{explanation}")

    parts = [f"# Quiz ({len(quiz.questions)} questions)\n", "".join(questions)]
    if include_answers and answers:
        parts.append("\n---\n\n## Answer Key\n\n" + "\n".join(answers) + "\n")
    return _lines(*parts)


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def material_to_markdown(material: object) -> str:
    """Render any study-material model to Markdown.

    An isinstance chain rather than a type->callable table: each branch keeps
    its own argument type, so mypy checks the renderers here instead of at a
    single erased call site. Raises TypeError for anything unknown, so a new
    model type fails loudly rather than silently exporting an empty file.
    """
    if isinstance(material, StudyGuide):
        return study_guide_to_markdown(material)
    if isinstance(material, Summary):
        return summary_to_markdown(material)
    if isinstance(material, CheatSheet):
        return cheat_sheet_to_markdown(material)
    if isinstance(material, FlashcardDeck):
        return flashcards_to_markdown(material)
    if isinstance(material, Outline):
        return outline_to_markdown(material)
    if isinstance(material, KeyTerms):
        return key_terms_to_markdown(material)
    if isinstance(material, Quiz):
        return quiz_to_markdown(material)
    raise TypeError(f"No Markdown renderer for {type(material).__name__}")
