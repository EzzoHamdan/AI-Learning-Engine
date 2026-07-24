"""The study page: upload → (summarize) → generate → run quiz / view materials.

This is the orchestration formerly living in app.py's main(); the heavy
lifting happens in extraction/, generation/, and ui/components/.
"""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st
from pydantic import BaseModel
from streamlit.runtime.uploaded_file_manager import UploadedFile

from learning_engine.analytics import metrics
from learning_engine.extraction import ExtractionError, extract_text
from learning_engine.generation import materials as materials_gen
from learning_engine.generation import quiz as quiz_gen
from learning_engine.llm.client import GenerationFailed, ProviderUnavailable
from learning_engine.settings import AppSettings, QuizSettings, get_settings
from learning_engine.ui import sidebar, state
from learning_engine.ui.components.materials import display_study_materials
from learning_engine.ui.components.quiz_runner import display_quiz
from learning_engine.ui.providers import ActiveProvider, resolve_active_provider
from learning_engine.ui.session import SessionManager
from learning_engine.ui.sidebar import GenerationRequest


@st.cache_data(show_spinner=False)
def _extract_text_cached(data: bytes, file_type: str) -> str:
    """Extraction cached on file bytes, so reruns never re-parse the document."""
    return extract_text(data, file_type)


def render() -> None:
    """Render the study page (called by st.navigation on every rerun)."""
    state.init_state()
    settings = get_settings()
    app_config = settings.app
    quiz_config = settings.quiz

    session_manager = SessionManager()
    request = sidebar.render(session_manager)
    active = resolve_active_provider(session_manager)

    if app_config.debug:
        st.write("**Debug - Configuration Status:**")
        st.write(f"Selected Provider: {st.session_state.ai_provider}")
        st.write(f"Active Provider: {active.display_name}")
        st.write(f"Client Status: {'✅ Working' if active.ok else '❌ Error Mode'}")
        st.write(f"Provider Status: {st.session_state.provider_status}")

    if not active.ok:
        st.warning(f"⚠️ {active.display_name} unavailable: {active.error}")
        st.info(
            "💡 Configure a working AI provider in the sidebar to generate quizzes "
            "and study materials."
        )
    elif app_config.debug:
        st.success(f"✅ Successfully initialized: {active.display_name}")

    st.title(app_config.title)

    provider_emoji = {"Local AI (Ollama)": "🏠", "Google AI": "🆕"}.get(active.display_name, "⚡")
    st.info(
        f"{provider_emoji} **Powered by {active.display_name}** - Advanced AI for "
        "intelligent quiz generation and study materials creation"
    )

    if request.uploaded_file and not (state.quiz_generated() or state.materials_generated()):
        _handle_document_and_generation(
            request, request.uploaded_file, active, quiz_config, app_config
        )
    elif request.uploaded_file and state.quiz_generated():
        # Display the interactive quiz
        st.markdown("---")
        quiz = state.quiz_data()
        if quiz is not None:
            display_quiz(quiz, active)

        with st.sidebar:
            st.markdown("---")
            if st.button("🔄 Generate New Quiz"):
                # Keep the summarized text to avoid re-summarization
                state.reset_quiz()
                st.rerun()
    elif request.uploaded_file and state.materials_generated():
        # Display the study materials
        st.markdown("---")
        display_study_materials(state.materials_data(), state.material_type())

        with st.sidebar:
            st.markdown("---")
            if st.button("🔄 Generate New Materials"):
                # Keep the summarized text to avoid re-summarization
                state.reset_materials()
                st.rerun()
    else:
        _render_welcome(session_manager)


def _handle_document_and_generation(
    request: GenerationRequest,
    uploaded_file: UploadedFile,
    active: ActiveProvider,
    quiz_config: QuizSettings,
    app_config: AppSettings,
) -> None:
    """Extract text, summarize if needed, and offer the generate button."""

    # Enforce the upload size limit before doing any work with the file
    max_upload_bytes = quiz_config.max_upload_bytes
    if uploaded_file.size > max_upload_bytes:
        st.error(
            f"❌ File is {uploaded_file.size / (1024 * 1024):.1f}MB, which exceeds "
            f"the {quiz_config.max_upload_mb}MB limit. Please upload a smaller file."
        )
        return

    ext = uploaded_file.name.split(".")[-1]
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"

    if file_id != state.current_file_id():
        # New file: reset extraction/summary/quiz state and track the upload
        state.reset_document(file_id)
        tracker = state.tracker()
        tracker.track_feature_usage("document_upload")
        tracker.add_to_learning_history(
            "document_upload",
            {
                "filename": uploaded_file.name,
                "file_type": ext,
                "file_size": uploaded_file.size,
            },
        )

    # Extract text only if we don't have it already
    if not state.original_text():
        try:
            text = _extract_text_cached(uploaded_file.getvalue(), ext)
        except ExtractionError as e:
            st.error(f"❌ {e}")
            return

        if not text.strip():
            st.error("❌ No text found in the uploaded file")
            return

        state.set_original_text(text)
    else:
        text = state.original_text()

    # Show document preview
    with st.expander("📄 Document Preview"):
        preview_text = state.summarized_text() if state.text_summarized() else text
        st.text_area(
            "Extracted Text",
            preview_text[:1000] + "..." if len(preview_text) > 1000 else preview_text,
            height=200,
        )

    # Handle summarization logic
    needs_summarization = len(text) > quiz_config.summary_threshold and not state.text_summarized()

    if needs_summarization and not state.summarization_in_progress():
        # Start summarization automatically
        state.set_summarization_in_progress(True)
        st.info("📄 Large content detected. Summarizing automatically...")

        if not active.ok:
            st.warning("⚠️ No AI provider available for summarization. Using original text.")
            state.store_summary(text)
            st.rerun()
        else:
            with st.spinner("Summarizing content..."):
                state.store_summary(_summarize_text(active, text))
                st.success("✅ Content summarized successfully!")
                st.rerun()

    # Show summarization status
    if state.summarization_in_progress():
        st.info("🔄 Summarization in progress... Please wait.")
        st.stop()  # Prevent the rest of the UI from rendering
    elif state.text_summarized():
        st.success(
            f"✅ Content summarized (Original: {len(text):,} chars → "
            f"Summary: {len(state.summarized_text()):,} chars)"
        )

    # Determine which text to use for generation
    final_text = state.summarized_text() if state.text_summarized() else text

    # Generation button - only show if summarization is complete (if needed)
    if needs_summarization and not state.text_summarized():
        st.info("⏳ Please wait for summarization to complete before generating content.")
        return

    if request.generation_type == "Interactive Quiz":
        button_text = "🎯 Generate Interactive Quiz"
        button_help = "Create an interactive quiz from your document"
    else:
        button_text = f"📚 Generate {request.material_type}"
        button_help = f"Create {request.material_type.lower()} from your document"

    if st.button(button_text, type="primary", help=button_help):
        if not active.ok:
            st.error(
                "❌ No working AI provider available. Please configure an AI provider "
                "in the sidebar first."
            )
            st.info("💡 **Quick Setup Guide:**")
            st.info(
                "1. **Local AI**: Start Ollama server (`ollama serve`) and pull a model "
                f"(`ollama pull {get_settings().llm.ollama.chat_model}`)"
            )
            st.info("2. **Google AI**: Enter your Google AI API key in the sidebar")
            st.info("3. **OpenAI**: Enter your OpenAI API key in the sidebar")
            return

        if request.generation_type == "Interactive Quiz":
            _generate_quiz(final_text, request, active, app_config)
        else:
            _generate_materials(final_text, request, active, app_config)


def _summarize_text(active: ActiveProvider, text: str) -> str:
    """Return a condensed summary, or the original text if summarization fails."""
    try:
        client, cfg = active.require()
        return quiz_gen.summarize(client, cfg, text)
    except Exception as e:
        st.error(f"❌ Error during text summarization: {str(e)}")
        return text  # Fall back to the original text if summarization fails


def _generate_quiz(
    final_text: str, request: GenerationRequest, active: ActiveProvider, app_config: AppSettings
) -> None:
    """Generate a quiz and store it (as a Quiz model) in session state."""
    with st.spinner(f"🤖 Generating quiz using {active.display_name}..."):
        try:
            client, cfg = active.require()
            if request.quiz_type == "Open-ended Questions":
                quiz = quiz_gen.generate_open_ended(
                    client,
                    cfg,
                    final_text,
                    request.num_questions,
                    request.difficulty,
                )
            elif request.quiz_type == "Complete Mix (All Types)":
                quiz = quiz_gen.generate_mixed(
                    client,
                    cfg,
                    final_text,
                    request.mcq_count,
                    request.tf_count,
                    request.open_count,
                    request.difficulty,
                )
            else:
                quiz = quiz_gen.generate_quiz(
                    client,
                    cfg,
                    final_text,
                    request.quiz_type,
                    request.num_questions,
                    request.difficulty,
                )

            tracker = state.tracker()
            tracker.track_feature_usage("quiz_generation")
            tracker.track_ai_provider_usage(st.session_state.ai_provider)

            state.store_quiz(quiz, request.quiz_type, request.difficulty)
            st.success("✅ Quiz generated successfully! Start answering below.")
            st.rerun()

        except ProviderUnavailable as e:
            st.error(f"❌ {active.display_name} is unavailable: {e}")
        except GenerationFailed as e:
            st.error(f"❌ Could not generate a valid quiz: {e}")
            st.info("Try again, or switch to a more capable model/provider in the sidebar.")
        except Exception as e:
            st.error(f"❌ Error during quiz generation: {str(e)}")
            st.write("**Debug Info:**")
            st.write(f"- AI Provider: {active.display_name}")
            st.write(f"- Quiz Type: {request.quiz_type}")
            st.write(f"- Text Length: {len(final_text)} characters")
            if app_config.debug:
                st.exception(e)


def _generate_materials(
    final_text: str, request: GenerationRequest, active: ActiveProvider, app_config: AppSettings
) -> None:
    """Generate a study-material model and store it in session state."""
    material_type = request.material_type
    options = request.material_options
    generation_start_time = time.time()

    # Each branch returns a different model; the union is what store_materials holds.
    materials_data: BaseModel

    with st.spinner(f"📚 Generating {material_type.lower()} using {active.display_name}..."):
        try:
            client, cfg = active.require()
            if material_type == "Complete Study Guide":
                materials_data = materials_gen.generate_study_guide(
                    client,
                    cfg,
                    final_text,
                    options.get("guide_type", "comprehensive"),
                    generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            elif material_type == "Summary Only":
                materials_data = materials_gen.generate_summary(
                    client,
                    cfg,
                    final_text,
                    options.get("summary_type", "detailed"),
                )
            elif material_type == "Cheat Sheet":
                materials_data = materials_gen.generate_cheat_sheet(
                    client,
                    cfg,
                    final_text,
                    options.get("cheat_format", "comprehensive"),
                )
            elif material_type == "Flashcards":
                materials_data = materials_gen.generate_flashcards(
                    client,
                    cfg,
                    final_text,
                    options.get("card_count", 15),
                    options.get("flashcard_difficulty", "mixed"),
                )
            elif material_type == "Study Outline":
                materials_data = materials_gen.generate_outline(
                    client,
                    cfg,
                    final_text,
                    options.get("outline_depth", "detailed"),
                )
            elif material_type == "Key Terms":
                materials_data = materials_gen.generate_key_terms(
                    client, cfg, final_text, options.get("term_count", 15)
                )
            else:
                st.error(f"❌ Unknown material type: {material_type}")
                return

            generation_time = time.time() - generation_start_time
            tracker = state.tracker()
            tracker.track_materials_generation(material_type, generation_time, True)
            tracker.track_feature_usage("study_materials")
            tracker.track_ai_provider_usage(st.session_state.ai_provider)

            state.store_materials(materials_data, material_type)
            st.success(f"✅ {material_type} generated successfully!")
            st.rerun()

        except GenerationFailed as e:
            state.tracker().track_materials_generation(
                material_type, time.time() - generation_start_time, False
            )
            st.error(f"❌ Could not generate valid {material_type.lower()}: {e}")
            st.info("Try again, or switch to a more capable model/provider in the sidebar.")
        except Exception as e:
            state.tracker().track_materials_generation(
                material_type, time.time() - generation_start_time, False
            )
            st.error(f"❌ Error during {material_type.lower()} generation: {str(e)}")
            st.write("**Debug Info:**")
            st.write(f"- AI Provider: {active.display_name}")
            st.write(f"- Material Type: {material_type}")
            st.write(f"- Text Length: {len(final_text)} characters")
            if app_config.debug:
                st.exception(e)


def _render_welcome(session_manager: SessionManager) -> None:
    """Welcome screen with quick analytics, guides, and provider status."""
    tracker = state.tracker()

    # Quick Analytics Preview
    if (
        tracker.quiz_analytics["total_quizzes"] > 0
        or tracker.materials_analytics["total_materials"] > 0
    ):
        st.subheader("📊 Quick Analytics Overview")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Quizzes Completed", tracker.quiz_analytics["total_quizzes"])

        with col2:
            performance = tracker.quiz_analytics["performance_over_time"]
            if performance:
                st.metric("Average Score", f"{metrics.average_score(performance):.1f}%")
            else:
                st.metric("Average Score", "N/A")

        with col3:
            st.metric("Materials Generated", tracker.materials_analytics["total_materials"])

        with col4:
            session_duration = datetime.now() - tracker.session_start_time
            hours, remainder = divmod(session_duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            st.metric("Session Time", f"{int(hours):02d}:{int(minutes):02d}")

        # Quick recommendation
        if tracker.quiz_analytics["total_quizzes"] >= 2:
            analysis = metrics.strength_weakness_analysis(
                tracker.quiz_analytics["detailed_results"]
            )
            if analysis["recommendations"]:
                st.info(f"💡 **Quick Tip**: {analysis['recommendations'][0]}")

        st.info("📊 **View detailed analytics by switching to Analytics mode in the sidebar!**")
        st.markdown("---")

    st.markdown("""
    ## Welcome to the AI Interactive Quiz Generator & Study Materials Creator! 🎓

    This application creates personalized, interactive quizzes and comprehensive study
    materials from your documents with **advanced AI scoring**, **graceful error
    handling**, and **comprehensive learning analytics**.

    ### 🆕 **New Features:**
    - **📊 Learning Analytics**: Track your progress, performance trends, and learning patterns
    - **📝 Study Materials Generation**: Create summaries, cheat sheets, flashcards, and more!
    - **🔧 Graceful Error Handling**: App now works even if AI providers have issues
    - **⚡ Dynamic Provider Switching**: Change AI providers instantly without restarting
    - **🔐 Runtime API Key Management**: Enter API keys directly in the app for the current session
    - **🌱 Environment Config**: Or set keys in your .env / Streamlit secrets to persist them

    ### How it works:
    1. 📁 **Upload** a PDF, Word, or PowerPoint file
    2. ⚙️ **Configure** your AI provider and API keys in the sidebar
    3. 🎯 **Choose Generation Type**: Interactive Quiz or Study Materials
    4. 📝 **Generate & Use** your personalized content
    5. 📊 **Review** results with detailed AI-powered feedback

    ### AI Provider Options:
    - 🏠 **Local AI (Ollama)**: Run Gemma models locally - completely free and private!
    - 🆕 **Google AI**: Use Google's Gemma models via API
    - ⚡ **OpenAI**: Traditional GPT models for reference

    ### 📚 **Study Materials Available:**
    - **📖 Complete Study Guide**: Comprehensive package with summary, cheat sheet,
      flashcards, key terms + study plan
    - **📝 Summaries**: Detailed, concise, or bullet-point summaries
    - **📋 Cheat Sheets**: Quick reference sheets with key concepts
    - **🔄 Interactive Flashcards**: Self-paced flashcards with difficulty levels
    - **📊 Study Outlines**: Structured hierarchical outlines (available separately)
    - **🔖 Key Terms**: Important terminology with definitions

    ### Question Types Available:
    - 🔘 **Multiple Choice**: Traditional 4-option questions
    - ✅ **True/False**: Binary choice questions
    - 📝 **Open-ended**: Write detailed answers scored by AI
    - 🎯 **Complete Mix**: Combination of all question types

    ### 🔐 **API Key Management:**
    - Enter API keys directly in the sidebar (used for the current session)
    - Or set them in your .env file / Streamlit secrets to persist across sessions
    - Secure password input fields

    **Get started by:**
    1. **Configure AI Provider** in the sidebar →
    2. **Enter API keys** (if needed)
    3. **Upload a document** to begin!
    4. **Check Analytics** to track your learning progress

    ### 📊 **Learning Analytics Features:**
    - **📈 Performance Tracking**: Monitor quiz scores and improvement trends
    - **🎯 Strength/Weakness Analysis**: Identify areas for focused study
    - **🚀 Learning Velocity**: Track your rate of improvement over time
    - **📋 Detailed Insights**: Question-by-question performance analysis
    - **🔥 Study Streaks**: Monitor daily learning consistency
    - **💡 Personalized Recommendations**: Get AI-powered study suggestions
    - **📊 Comprehensive Reports**: Export detailed analytics data

    *Switch to Analytics mode using the sidebar navigation!*
    """)

    # Provider status overview
    with st.expander("🔍 Current Provider Status"):
        session_manager.update_provider_status()
        for provider, status in st.session_state.provider_status.items():
            if status.get("available", False):
                st.success(f"✅ **{provider}**: {status.get('message', 'Ready')}")
            else:
                st.warning(f"⚠️ **{provider}**: {status.get('message', 'Not available')}")

    # Study Materials Preview
    with st.expander("📚 Study Materials Preview"):
        st.markdown("""
        **Example Study Materials from a Biology Document:**

        **📖 Summary**: "Cell membrane is a selectively permeable barrier that controls
        substance transport..."

        **📋 Cheat Sheet**:
        - Cell Membrane: Phospholipid bilayer with embedded proteins
        - Functions: Transport, signaling, protection
        - Types: Passive (diffusion) vs Active (ATP-required)

        **🔄 Flashcard Example**:
        - Front: "What is the primary function of mitochondria?"
        - Back: "Energy production through cellular respiration (ATP synthesis)"

        **📊 Study Outline**:
        - I. Cell Structure
          - A. Cell Membrane
            - 1. Composition
            - 2. Functions

        **🔖 Key Terms**:
        - **Osmosis**: Movement of water across semipermeable membrane
        - **Endocytosis**: Cell engulfs external material
        """)

    # Local AI Setup Guide
    with st.expander("🏠 Local AI Setup Guide"):
        ollama = get_settings().llm.ollama
        st.markdown(f"""
        **Why use Local AI?**
        - ✅ **Completely Free** - No API costs ever
        - 🔐 **Private** - Your data never leaves your computer
        - 🚀 **Fast** - No internet required after setup
        - 🎯 **Always Available** - No rate limits or downtime

        **Quick Setup:**
        ```bash
        # 1. Install Ollama (visit ollama.ai for download)

        # 2. Start Ollama server
        ollama serve

        # 3. Download the configured model
        ollama pull {ollama.chat_model}

        # 4. Or download larger models for better quality
        ollama pull gemma2:9b
        ollama pull gemma2:27b
        Or any other model you prefer
        ```

        **Hardware Requirements:** Examples
        - **2B Model**: 2GB RAM, runs on most computers
        - **9B Model**: 6GB RAM, better quality
        - **27B Model**: 16GB RAM, best quality

        **Troubleshooting:**
        - Ensure Ollama is running: `ollama list`
        - Check server status: `curl {ollama.base_url}/api/tags`
        - View logs: Check terminal where `ollama serve` is running
        """)

    # Add example of open-ended scoring
    with st.expander("🔍 See Open-ended Question Example"):
        st.markdown("""
        **Example Question:** *Explain the chemical composition and importance of water
        (4 marks)*

        **Sample Answer:**
        "Water is a liquid encompassed with two hydrogens and one oxygen. It is a crucial
        composition that its existence guarantees life."

        **AI Scoring Breakdown:**
        - ✅ Chemical composition (H2O) - 2/2 marks
        - ⚠️ Physical properties mentioned - 1/1 mark
        - ✅ Biological importance stated - 1/1 mark

        **Result:** 4/4 marks (100%) with specific feedback on scientific accuracy!
        """)

    st.info(
        "💡 **Pro Tip:** The app now works gracefully even with provider errors. "
        "Configure your preferred AI provider in the sidebar and start generating "
        "quizzes or study materials!"
    )
