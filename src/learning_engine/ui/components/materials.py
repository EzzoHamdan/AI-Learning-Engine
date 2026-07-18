"""Renderers for generated study materials (typed models in, widgets out)."""

from __future__ import annotations

import streamlit as st

from learning_engine.models import (
    CheatSheet,
    KeyTerm,
    KeyTerms,
    Outline,
    OutlineItem,
    StudyGuide,
    Summary,
)
from learning_engine.ui.components.flashcards import display_flashcards


def display_study_materials(materials_data, material_type: str) -> None:
    """Dispatch to the right renderer for a generated study-material model."""
    st.success(f"✅ {material_type} generated successfully!")
    if material_type == "Complete Study Guide":
        display_complete_study_guide(materials_data)
    elif material_type == "Summary Only":
        display_summary(materials_data)
    elif material_type == "Cheat Sheet":
        display_cheat_sheet(materials_data)
    elif material_type == "Flashcards":
        display_flashcards(materials_data)
    elif material_type == "Study Outline":
        display_outline(materials_data)
    elif material_type == "Key Terms":
        display_key_terms(materials_data)


def display_complete_study_guide(guide: StudyGuide) -> None:
    """Display a complete study guide (StudyGuide model)."""
    st.subheader(f"📚 {guide.title}")
    st.caption(
        f"Generated: {guide.generated_at or 'Unknown time'} | Type: {guide.guide_type.title()}"
    )

    with st.expander("🗓️ Suggested Study Plan", expanded=True):
        st.info(f"**Total Study Time:** {guide.study_plan.total_time}")
        for session in guide.study_plan.sessions:
            st.write(f"**Session {session.session}** ({session.time}): {session.focus}")

    components = guide.components
    if components.summary:
        with st.expander("📖 Summary", expanded=True):
            display_summary(components.summary)
    if components.key_terms:
        with st.expander("📚 Key Terms & Definitions"):
            display_key_terms(components.key_terms)
    if components.cheat_sheet:
        with st.expander("📄 Quick Reference Cheat Sheet"):
            display_cheat_sheet(components.cheat_sheet)
    if components.flashcards:
        with st.expander("🔄 Interactive Flashcards"):
            display_flashcards(components.flashcards)

    if guide.errors:
        with st.expander("⚠️ Generation Notes"):
            for error in guide.errors:
                st.warning(error)


def display_summary(summary: Summary) -> None:
    """Display a Summary model."""
    st.write(summary.summary or "No summary available")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Word Count", summary.word_count)
    with col2:
        if summary.summary_type:
            st.metric("Type", summary.summary_type.title())

    if summary.key_points:
        st.subheader("🎯 Key Points")
        for point in summary.key_points:
            st.write(f"• {point}")

    if summary.main_topics:
        st.subheader("📋 Main Topics")
        topic_cols = st.columns(3)
        for i, topic in enumerate(summary.main_topics):
            with topic_cols[i % 3]:
                st.write(f"📌 {topic}")


def display_cheat_sheet(cheat: CheatSheet) -> None:
    """Display a CheatSheet model."""
    st.subheader(f"📋 {cheat.title}")

    for section in cheat.sections:
        st.subheader(f"📌 {section.heading or 'Section'}")
        if section.content:
            st.write(section.content)
        for item in section.items:
            st.write(f"• {item}")

    if cheat.key_terms:
        st.subheader("📚 Key Terms")
        for term in cheat.key_terms:
            st.write(f"**{term.term}**: {term.definition}")

    if cheat.formulas:
        st.subheader("🔢 Formulas")
        for formula in cheat.formulas:
            st.write(f"**{formula.name}**: `{formula.formula}`")
            if formula.explanation:
                st.caption(formula.explanation)

    if cheat.quick_tips:
        st.subheader("💡 Quick Tips")
        for tip in cheat.quick_tips:
            st.info(tip)


def display_outline(outline: Outline) -> None:
    """Display a structured study outline (Outline model)."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sections", outline.total_sections)
    with col2:
        st.metric("Max Depth", outline.max_depth)
    with col3:
        st.metric("Study Time", outline.time_estimates.total_study_time)

    render_outline_recursive(outline.outline, 0)

    if outline.study_sequence:
        st.subheader("📅 Recommended Study Sequence")
        per_section = outline.time_estimates.per_section
        for i, section in enumerate(outline.study_sequence, 1):
            time_for_section = per_section[i - 1] if i - 1 < len(per_section) else "30 min"
            st.write(f"{i}. **{section}** ({time_for_section})")


def render_outline_recursive(outline_items: list[OutlineItem], depth: int) -> None:
    """Recursively render OutlineItem models."""
    for item in outline_items:
        indent = "  " * (item.level - 1)
        if item.level == 1:
            st.subheader(f"{item.marker}. {item.text}")
        elif item.level == 2:
            st.write(f"**{indent}{item.marker}. {item.text}**")
        else:
            st.write(f"{indent}{item.marker}. {item.text}")
        if item.children:
            render_outline_recursive(item.children, depth + 1)


def display_key_terms(terms: KeyTerms) -> None:
    """Display key terms and definitions (KeyTerms model)."""
    st.metric("Total Terms", terms.total_terms or len(terms.key_terms))

    if terms.categories:
        st.subheader("📂 Categories")
        for category in terms.categories:
            st.write(f"**{category.category}**: {len(category.terms)} terms")

    if terms.key_terms:
        st.subheader("📚 Terms & Definitions")
        priorities = (
            ("high", "### 🔴 High Priority Terms"),
            ("medium", "### 🟡 Medium Priority Terms"),
            ("low", "### 🟢 Low Priority Terms"),
        )
        for importance, header in priorities:
            group = [t for t in terms.key_terms if t.importance == importance]
            if group:
                st.markdown(header)
                for term in group:
                    display_term(term)

    if terms.study_suggestions:
        st.subheader("💡 Study Suggestions")
        for suggestion in terms.study_suggestions:
            st.info(suggestion)


def display_term(term: KeyTerm) -> None:
    """Display a single KeyTerm model with its definition and context."""
    with st.expander(f"📖 {term.term or 'Term'}"):
        st.write(f"**Definition**: {term.definition or 'No definition available'}")
        if term.context:
            st.write(f"**Context**: {term.context}")
        if term.related_terms:
            st.write(f"**Related Terms**: {', '.join(term.related_terms)}")
