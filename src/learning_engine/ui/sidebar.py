"""Sidebar: provider picker, API keys, upload, and generation options.

render() returns a typed GenerationRequest instead of the old pattern of
passing `locals()` from the page function into the generators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from learning_engine.llm.providers import list_ollama_models
from learning_engine.settings import LocalAIConfig, QuizConfig
from learning_engine.ui.session import SessionManager

QUIZ_TYPES = [
    "Multiple Choice",
    "True or False",
    "Mixed (MCQ + T/F)",
    "Open-ended Questions",
    "Complete Mix (All Types)",
]
MATERIAL_TYPES = [
    "Complete Study Guide",
    "Summary Only",
    "Cheat Sheet",
    "Flashcards",
    "Study Outline",
    "Key Terms",
]


@dataclass
class GenerationRequest:
    """Everything the study page needs to know about what the user asked for."""

    uploaded_file: UploadedFile | None
    generation_type: str  # "Interactive Quiz" | "Study Materials"
    # Quiz options
    quiz_type: str = ""
    difficulty: str = "Standard"
    num_questions: int = 5
    mcq_count: int = 0
    tf_count: int = 0
    open_count: int = 0
    # Study-material options (only the keys relevant to material_type are set)
    material_type: str = ""
    material_options: dict[str, Any] = field(default_factory=dict)


def render(session_manager: SessionManager) -> GenerationRequest:
    """Render the sidebar and return the user's current generation request."""
    with st.sidebar:
        st.header("App Configuration")

        # AI Provider Selection with status (updates st.session_state.ai_provider)
        session_manager.render_provider_selector()

        # API Key Configuration
        session_manager.render_api_key_inputs()

        st.markdown("---")

        uploaded_file = st.file_uploader(
            "Upload PDF, Word, or PPTX file", type=["pdf", "docx", "pptx"]
        )

        generation_type = st.selectbox(
            "Choose Generation Type",
            ["Interactive Quiz", "Study Materials"],
            help="Select whether to generate a quiz or study materials",
        )

        request = GenerationRequest(uploaded_file=uploaded_file, generation_type=generation_type)
        if generation_type == "Interactive Quiz":
            _render_quiz_options(request)
        else:
            _render_material_options(request)

        if uploaded_file:
            st.success("✅ File uploaded successfully!")

        if st.session_state.ai_provider == "Local AI (Ollama)":
            _render_local_ai_status()

    return request


def _render_quiz_options(request: GenerationRequest) -> None:
    quiz_config = QuizConfig()

    request.quiz_type = st.selectbox("Choose Quiz Type", QUIZ_TYPES)
    request.difficulty = st.selectbox(
        "Choose Difficulty Level",
        ["Standard", "Advanced", "Extreme"],
        index=0,  # Default to Standard
        help=(
            "Standard: University-level | Advanced: Graduate-level | "
            "Extreme: Expert-level with tricky elements"
        ),
    )

    cloud_scoring = st.session_state.ai_provider not in ["Local AI (Ollama)", "Google AI"]

    if request.quiz_type == "Open-ended Questions":
        request.num_questions = st.slider("Number of Questions", min_value=2, max_value=5, value=3)
        if cloud_scoring:
            st.warning(
                "💡 Open-ended questions use gpt-4o-mini for scoring and may increase API "
                "costs. Each answer requires an additional AI evaluation."
            )
    elif request.quiz_type == "Complete Mix (All Types)":
        st.write("**Question Distribution:**")
        request.mcq_count = st.slider("Multiple Choice", min_value=1, max_value=5, value=2)
        request.tf_count = st.slider("True/False", min_value=1, max_value=5, value=2)
        request.open_count = st.slider("Open-ended", min_value=1, max_value=3, value=1)
        request.num_questions = request.mcq_count + request.tf_count + request.open_count
        st.info(f"Total questions: {request.num_questions}")
        if request.open_count > 0 and cloud_scoring:
            st.warning(
                f"⚠️ {request.open_count} open-ended question(s) will use gpt-4o-mini "
                "for scoring (higher cost)"
            )
    else:
        request.num_questions = st.slider(
            "Number of Questions",
            min_value=quiz_config.MIN_QUESTIONS,
            max_value=quiz_config.MAX_QUESTIONS,
            value=quiz_config.DEFAULT_QUESTIONS,
        )


def _render_material_options(request: GenerationRequest) -> None:
    request.material_type = st.selectbox(
        "Choose Study Material Type",
        MATERIAL_TYPES,
        help="Select the type of study material to generate",
    )
    options = request.material_options

    if request.material_type == "Complete Study Guide":
        options["guide_type"] = st.selectbox(
            "Study Guide Type",
            ["comprehensive", "exam_prep", "quick_review"],
            format_func=lambda x: {
                "comprehensive": "📚 Comprehensive Guide (4-6 hours study time)",
                "exam_prep": "🎯 Exam Preparation (6-8 hours study time)",
                "quick_review": "⚡ Quick Review (2-3 hours study time)",
            }[x],
        )
    elif request.material_type == "Summary Only":
        options["summary_type"] = st.selectbox(
            "Summary Type",
            ["detailed", "concise", "bullet_points"],
            format_func=lambda x: {
                "detailed": "📖 Detailed Summary (300-500 words)",
                "concise": "📝 Concise Summary (150-250 words)",
                "bullet_points": "• Bullet Points Summary",
            }[x],
        )
    elif request.material_type == "Cheat Sheet":
        options["cheat_format"] = st.selectbox(
            "Cheat Sheet Format",
            ["comprehensive", "formulas", "definitions", "quick_ref"],
            format_func=lambda x: {
                "comprehensive": "📋 Comprehensive Reference",
                "formulas": "🔢 Formulas & Equations",
                "definitions": "📚 Definitions & Terms",
                "quick_ref": "⚡ Quick Reference",
            }[x],
        )
    elif request.material_type == "Flashcards":
        options["card_count"] = st.slider(
            "Number of Flashcards", min_value=5, max_value=30, value=15
        )
        options["flashcard_difficulty"] = st.selectbox(
            "Flashcard Difficulty",
            ["basic", "intermediate", "advanced", "mixed"],
            index=3,  # Default to mixed
            format_func=lambda x: {
                "basic": "📚 Basic (Definitions & Facts)",
                "intermediate": "🎓 Intermediate (Concepts & Applications)",
                "advanced": "🏆 Advanced (Analysis & Synthesis)",
                "mixed": "🎯 Mixed Difficulty",
            }[x],
        )
    elif request.material_type == "Study Outline":
        options["outline_depth"] = st.selectbox(
            "Outline Depth",
            ["overview", "detailed", "comprehensive"],
            index=1,  # Default to detailed
            format_func=lambda x: {
                "overview": "📝 Overview (1-2 levels)",
                "detailed": "📋 Detailed (3-4 levels)",
                "comprehensive": "📚 Comprehensive (4-5 levels)",
            }[x],
        )
    elif request.material_type == "Key Terms":
        options["term_count"] = st.slider(
            "Number of Key Terms", min_value=5, max_value=30, value=15
        )


def _render_local_ai_status() -> None:
    """Ollama server status + model picker (only shown for the local provider)."""
    local_ai_config = LocalAIConfig()

    st.markdown("---")
    st.subheader("🏠 Local AI Status")
    ollama_base_url = f"http://{local_ai_config.HOST}:{local_ai_config.PORT}"
    available_models = list_ollama_models(ollama_base_url)
    if not available_models:
        st.error("❌ Ollama server not running, or no models installed")
        st.code("ollama serve\nollama pull gemma2:2b")
        return

    st.success("✅ Ollama server running")
    if "selected_local_model" not in st.session_state:
        # Default to config model if available, otherwise first available
        default_model = (
            local_ai_config.MODEL_NAME
            if local_ai_config.MODEL_NAME in available_models
            else available_models[0]
        )
        st.session_state.selected_local_model = default_model

    selected_model = st.selectbox(
        "🤖 Select Model:",
        available_models,
        index=available_models.index(st.session_state.selected_local_model)
        if st.session_state.selected_local_model in available_models
        else 0,
        key="model_selector",
        help="Choose which model to use for generation. Larger models are more capable but slower.",
    )

    if selected_model != st.session_state.selected_local_model:
        st.session_state.selected_local_model = selected_model
        st.success(f"🔄 Switched to model: {selected_model}")

        # Show performance hint for selected model
        if ":2b" in selected_model:
            st.info("⚡ **Fast & Efficient** - Good for quick quiz generation")
        elif ":9b" in selected_model:
            st.info("⚖️ **Balanced** - Good mix of speed and quality")
        elif ":27b" in selected_model:
            st.info("🎯 **High Quality** - Better responses, requires more time")
        elif ":70b" in selected_model:
            st.info("🏆 **Premium Quality** - Best results, much slower")

        st.rerun()

    st.info(f"🎯 **Active Model:** {st.session_state.selected_local_model}")

    with st.expander(f"📦 All Available Models ({len(available_models)})"):
        for model in available_models:
            is_current = model == st.session_state.selected_local_model
            marker = "🔹 **" if is_current else "• "
            end_marker = "** (Active)" if is_current else ""
            st.write(f"{marker}{model}{end_marker}")
