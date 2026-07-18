import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import custom modules
from learning_engine.ai_client_factory import get_client, resolve_provider
from learning_engine.extraction import ExtractionError, extract_text
from learning_engine.learning_analytics import analytics
from learning_engine.generation import materials as materials_gen
from learning_engine.generation import quiz as quiz_gen
from learning_engine.llm.client import GenerationFailed, ProviderUnavailable
from learning_engine.llm.providers import list_ollama_models
from learning_engine.logger import setup_logging
from learning_engine.session_manager import SessionManager
from learning_engine.settings import (
    DIFFICULTY_CONFIG,
    SCORING_CONFIG,
    AppConfig,
    LocalAIConfig,
    QuizConfig,
)

# Temperatures kept per call type (Phase 7 moves these into settings).
QUIZ_TEMPERATURE = 0.7
SUMMARY_TEMPERATURE = 0.5

# Setup logging
logger = setup_logging()

# Initialize configuration
app_config = AppConfig()
quiz_config = QuizConfig()
local_ai_config = LocalAIConfig()

# Initialize session manager
session_manager = SessionManager()


def resolve_active_client():
    """Resolve the selected provider to (client, cfg, display_name, ok, error).

    On failure returns a disabled state with the reason instead of a mock
    client, and never switches providers silently.
    """
    try:
        cfg = resolve_provider(session_manager)
        return get_client(cfg), cfg, cfg.display_name, True, None
    except ProviderUnavailable as exc:
        return None, None, st.session_state.ai_provider, False, str(exc)


# Get AI client with graceful error handling
client, provider_cfg, ai_provider, client_successful, provider_error = resolve_active_client()

# Debug: Print configuration values
if app_config.DEBUG_MODE:
    st.write("**Debug - Configuration Status:**")
    st.write(f"Selected Provider: {st.session_state.ai_provider}")
    st.write(f"Active Provider: {ai_provider}")
    st.write(f"Client Status: {'✅ Working' if client_successful else '❌ Error Mode'}")
    st.write(f"Provider Status: {st.session_state.provider_status}")

# Show provider status
if client_successful:
    if app_config.DEBUG_MODE:
        st.success(f"✅ Successfully initialized: {ai_provider}")
else:
    st.warning(f"⚠️ {ai_provider} unavailable: {provider_error}")
    st.info(
        "💡 Configure a working AI provider in the sidebar to generate quizzes and study materials."
    )


def _mcq_letter(user_answer):
    """Extract the chosen A/B/C/D letter from a selected option string."""
    if user_answer and user_answer[0] in ("A", "B", "C", "D"):
        return user_answer[0]
    return ""


def summarize_text(text):
    """Return a condensed summary, or the original text if AI is unavailable."""
    if not client_successful:
        st.error("❌ No working AI provider available for text summarization.")
        return text
    try:
        return quiz_gen.summarize(client, provider_cfg, text)
    except Exception as e:
        st.error(f"❌ Error during text summarization: {str(e)}")
        return text  # Fall back to the original text if summarization fails


def display_quiz(quiz):
    """Display the interactive quiz (a Quiz model) and capture user answers."""
    questions = quiz.questions
    if not questions:
        st.error("No questions found in the quiz data.")
        return

    # Initialize / reset progress whenever a new quiz object is loaded
    if "current_question" not in st.session_state or st.session_state.get("quiz_data") is not quiz:
        st.session_state.current_question = 0
        st.session_state.user_answers = {}
        st.session_state.quiz_completed = False
        st.session_state.quiz_finalized = False
        st.session_state.quiz_results = {}
        st.session_state.quiz_data = quiz

    total_questions = len(questions)

    if not st.session_state.quiz_completed:
        current_q = st.session_state.current_question
        question = questions[current_q]

        st.progress(current_q / total_questions)
        st.write(f"Question {current_q + 1} of {total_questions}")
        st.subheader(f"Q{current_q + 1}: {question.question}")

        is_open_ended = question.type == "open_ended"
        if is_open_ended:
            st.info(f"📝 **Open-ended Question** | Total Marks: {question.total_marks}")
            st.caption("💡 Write a comprehensive answer. Quality matters more than quantity!")
            current_answer = st.session_state.user_answers.get(current_q, "")
            user_answer = st.text_area(
                "Your Answer:",
                value=current_answer,
                height=150,
                key=f"open_q_{current_q}",
                placeholder="Write your detailed answer here...",
            )
            if user_answer:
                st.caption(f"Word count: {len(user_answer.split())}")
        else:
            user_answer = st.radio(
                "Select your answer:", question.options, key=f"q_{current_q}", index=None
            )

        col1, _col2, col3 = st.columns([1, 1, 1])
        with col1:
            if current_q > 0 and st.button("Previous"):
                st.session_state.current_question -= 1
                st.rerun()
        with col3:
            if is_open_ended:
                has_answer = bool(
                    user_answer and user_answer.strip() and len(user_answer.split()) >= 5
                )
            else:
                has_answer = user_answer is not None

            if has_answer:
                if current_q < total_questions - 1:
                    if st.button("Next"):
                        st.session_state.user_answers[current_q] = user_answer
                        st.session_state.current_question += 1
                        st.rerun()
                elif st.button("Submit Quiz"):
                    st.session_state.user_answers[current_q] = user_answer
                    st.session_state.quiz_completed = True
                    st.rerun()
            elif is_open_ended:
                st.caption("⚠️ Please write at least 5 words to proceed")
            else:
                st.caption("⚠️ Please select an answer to proceed")
    else:
        # Score + record analytics exactly once on entry to the completed state,
        # then render read-only (BUG-2).
        if not st.session_state.get("quiz_finalized"):
            finalize_quiz(questions, st.session_state.user_answers)
            st.session_state.quiz_finalized = True
        display_results(questions, st.session_state.user_answers)


def finalize_quiz(questions, user_answers):
    """Score the quiz and record analytics exactly once, on completion (BUG-2).

    `questions` are Pydantic models. Scoring (an LLM call) and analytics tracking
    run only here, on the transition into the completed state; display_results()
    only reads st.session_state.quiz_results.
    """
    traditional = [(i, q) for i, q in enumerate(questions) if q.type != "open_ended"]
    open_ended = [(i, q) for i, q in enumerate(questions) if q.type == "open_ended"]

    # Score traditional questions
    traditional_correct = 0
    for i, q in traditional:
        answer = user_answers.get(i, "")
        user_letter = _mcq_letter(answer) if len(q.options) > 2 else answer
        if user_letter == q.correct_answer:
            traditional_correct += 1
    total_traditional = len(traditional)

    # Score open-ended questions with AI (runs once, not on every rerun)
    open_ended_scores = []  # list of (index, OpenEndedQuestion, ScoringResult)
    total_open_ended_marks = 0.0
    earned_open_ended_marks = 0.0
    if open_ended and client_successful:
        st.info("🤖 Scoring open-ended questions with AI... This may take a moment.")
        progress_bar = st.progress(0)
        for idx, (i, q) in enumerate(open_ended):
            result = quiz_gen.score_open_ended(client, provider_cfg, q, user_answers.get(i, ""))
            open_ended_scores.append((i, q, result))
            total_open_ended_marks += result.max_score
            earned_open_ended_marks += result.total_score
            progress_bar.progress((idx + 1) / len(open_ended))
        progress_bar.empty()

    # Overall percentage
    if total_traditional and total_open_ended_marks:
        overall = (
            (traditional_correct / total_traditional) * 100
            + (earned_open_ended_marks / total_open_ended_marks) * 100
        ) / 2
    elif total_open_ended_marks:
        overall = (earned_open_ended_marks / total_open_ended_marks) * 100
    elif total_traditional:
        overall = (traditional_correct / total_traditional) * 100
    else:
        overall = 0

    st.session_state.quiz_results = {
        "traditional_correct": traditional_correct,
        "total_traditional": total_traditional,
        "open_ended_scores": open_ended_scores,
        "total_open_ended_marks": total_open_ended_marks,
        "earned_open_ended_marks": earned_open_ended_marks,
        "overall_percentage": overall,
    }

    # Analytics consumes plain dicts (kept untouched until the Phase 5/6 rewrite).
    analytics.track_quiz_completion(
        quiz_data=st.session_state.quiz_data.model_dump(),
        user_answers=user_answers,
        performance_stats={
            "traditional_correct": traditional_correct,
            "total_traditional": total_traditional,
            "open_ended_scores": [
                (i, q.model_dump(), r.model_dump()) for i, q, r in open_ended_scores
            ],
            "total_open_ended_marks": total_open_ended_marks,
            "earned_open_ended_marks": earned_open_ended_marks,
            "overall_percentage": overall,
        },
    )


def display_results(questions, user_answers):
    """Render quiz results (read-only; scoring/tracking happened in finalize_quiz)."""
    st.success("🎉 Quiz Completed!")
    difficulty = getattr(st.session_state, "quiz_difficulty", "Standard")

    results = st.session_state.get("quiz_results", {})
    traditional_correct = results.get("traditional_correct", 0)
    total_traditional = results.get("total_traditional", 0)
    open_ended_scores = results.get("open_ended_scores", [])
    total_open_ended_marks = results.get("total_open_ended_marks", 0)
    earned_open_ended_marks = results.get("earned_open_ended_marks", 0)
    overall_percentage = results.get("overall_percentage", 0)
    emoji = DIFFICULTY_CONFIG[difficulty]["emoji"]

    if total_traditional and total_open_ended_marks:
        trad_pct = (traditional_correct / total_traditional) * 100
        oe_pct = (earned_open_ended_marks / total_open_ended_marks) * 100
        st.subheader(f"📊 Overall Score: {overall_percentage:.1f}% {emoji} {difficulty} Level")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Traditional Questions",
                f"{traditional_correct}/{total_traditional} ({trad_pct:.1f}%)",
            )
        with col2:
            st.metric(
                "Open-ended Questions",
                f"{earned_open_ended_marks:.1f}/{total_open_ended_marks} ({oe_pct:.1f}%)",
            )
    elif total_open_ended_marks:
        st.subheader(
            f"📊 Overall Score: {earned_open_ended_marks:.1f}/{total_open_ended_marks} "
            f"({overall_percentage:.1f}%) {emoji} {difficulty} Level"
        )
    else:
        st.subheader(
            f"📊 Overall Score: {traditional_correct}/{total_traditional} "
            f"({overall_percentage:.1f}%) {emoji} {difficulty} Level"
        )

    # Score interpretation
    scoring_config = SCORING_CONFIG.get(difficulty, SCORING_CONFIG["Standard"])
    for level, (threshold, message) in scoring_config.items():
        if level == "default":
            continue
        if overall_percentage >= threshold:
            if level in ("excellent", "good"):
                st.success(message)
            elif level == "fair":
                st.info(message)
            else:
                st.warning(message)
            break
    else:
        st.warning(scoring_config["default"][1])

    # Detailed review
    st.subheader("📝 Detailed Review")
    scores_by_index = {i: r for i, _q, r in open_ended_scores}

    for i, question in enumerate(questions):
        user_answer = user_answers.get(i, "No answer")

        if question.type == "open_ended":
            result = scores_by_index.get(i)
            if not result:
                continue
            score_text = f"{result.total_score:.1f}/{result.max_score:.0f}"
            badge = " · estimated" if result.estimated else ""
            with st.expander(
                f"Question {i + 1}: 📝 {score_text} ({result.percentage:.1f}%){badge}"
            ):
                st.write(f"**Question:** {question.question}")
                st.write(f"**Your Answer:** {user_answer}")
                st.write(f"**Score:** {score_text} marks ({result.percentage:.1f}%)")
                if result.estimated:
                    st.warning(
                        "⚠️ Estimated score (AI scoring unavailable) — keyword-based, not graded."
                    )
                if result.overall_feedback:
                    st.write(f"**Overall Feedback:** {result.overall_feedback}")
                if result.criterion_scores:
                    st.write("**Detailed Breakdown:**")
                    for c in result.criterion_scores:
                        st.write(f"- {c.criterion}: {c.marks_awarded}/{c.max_marks}")
                        if c.feedback:
                            st.write(f"  *{c.feedback}*")
                if result.strengths:
                    st.success("**Strengths:** " + ", ".join(result.strengths))
                if result.improvements:
                    st.info("**Areas for Improvement:** " + ", ".join(result.improvements))
                st.markdown("**Model answer:**")
                st.info(question.model_answer)
        else:
            user_letter = _mcq_letter(user_answer) if len(question.options) > 2 else user_answer
            is_correct = user_letter == question.correct_answer
            with st.expander(f"Question {i + 1}: {'✅' if is_correct else '❌'}"):
                st.write(f"**Question:** {question.question}")
                st.write(f"**Your Answer:** {user_answer}")
                if len(question.options) > 2:
                    correct_option = next(
                        (opt for opt in question.options if opt[:1] == question.correct_answer),
                        question.correct_answer,
                    )
                else:
                    correct_option = question.correct_answer
                st.write(f"**Correct Answer:** {correct_option}")
                st.write(f"**Explanation:** {question.explanation}")
                if is_correct:
                    st.success("Correct! 🎉")
                else:
                    st.error("Incorrect 😔")

    if st.button("Take Quiz Again"):
        st.session_state.current_question = 0
        st.session_state.user_answers = {}
        st.session_state.quiz_completed = False
        st.session_state.quiz_finalized = False
        st.session_state.quiz_results = {}
        st.rerun()


def display_study_materials(materials_data, material_type):
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


def display_complete_study_guide(guide):
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


def display_summary(summary):
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


def display_cheat_sheet(cheat):
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


def display_flashcards(deck):
    """Display interactive flashcards (FlashcardDeck model)."""
    flashcards = deck.flashcards
    if not flashcards:
        st.warning("No flashcards generated.")
        return

    if "current_flashcard" not in st.session_state:
        st.session_state.current_flashcard = 0
        st.session_state.flashcard_answer_visible = False
        st.session_state.flashcard_stats = {"correct": 0, "incorrect": 0, "skipped": 0}

    total_cards = len(flashcards)
    # Guard against an index left over from a previously longer deck.
    if st.session_state.current_flashcard >= total_cards:
        st.session_state.current_flashcard = 0
    current_card = flashcards[st.session_state.current_flashcard]

    # Progress and stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Progress", f"{st.session_state.current_flashcard + 1}/{total_cards}")
    with col2:
        st.metric("Correct", st.session_state.flashcard_stats["correct"])
    with col3:
        st.metric("Difficulty", current_card.difficulty.title())

    with st.container():
        st.subheader(f"🔄 Card {st.session_state.current_flashcard + 1}")
        st.caption(
            f"Category: {current_card.category} | Difficulty: {current_card.difficulty.title()}"
        )
        st.markdown("### 📝 Question:")
        st.write(current_card.front or "No question available")

        if current_card.hint and not st.session_state.flashcard_answer_visible:
            with st.expander("💡 Hint"):
                st.write(current_card.hint)

        if st.session_state.flashcard_answer_visible:
            st.markdown("### ✅ Answer:")
            st.success(current_card.back or "No answer available")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("😊 Got it right!", key="correct"):
                    st.session_state.flashcard_stats["correct"] += 1
                    analytics.track_flashcard_interaction("correct")
                    next_card(total_cards)
            with col2:
                if st.button("😔 Got it wrong", key="incorrect"):
                    st.session_state.flashcard_stats["incorrect"] += 1
                    analytics.track_flashcard_interaction("incorrect")
                    next_card(total_cards)
            with col3:
                if st.button("⏭️ Skip", key="skip"):
                    st.session_state.flashcard_stats["skipped"] += 1
                    analytics.track_flashcard_interaction("skipped")
                    next_card(total_cards)
            with col4:
                if st.button("🔄 Flip Back", key="flip_back"):
                    st.session_state.flashcard_answer_visible = False
                    st.rerun()
        else:
            if st.button("🔄 Show Answer", key="show_answer", type="primary"):
                st.session_state.flashcard_answer_visible = True
                analytics.track_flashcard_interaction("viewed")
                st.rerun()

    # Navigation
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous") and st.session_state.current_flashcard > 0:
            st.session_state.current_flashcard -= 1
            st.session_state.flashcard_answer_visible = False
            st.rerun()
    with col2:
        if st.button("🔄 Shuffle Cards"):
            import random

            random.shuffle(deck.flashcards)
            st.session_state.current_flashcard = 0
            st.session_state.flashcard_answer_visible = False
            st.success("Cards shuffled!")
            st.rerun()
    with col3:
        if st.button("➡️ Next") and st.session_state.current_flashcard < total_cards - 1:
            st.session_state.current_flashcard += 1
            st.session_state.flashcard_answer_visible = False
            st.rerun()

    if deck.study_tips:
        with st.expander("💡 Study Tips"):
            for tip in deck.study_tips:
                st.write(f"• {tip}")


def next_card(total_cards):
    """Advance to the next flashcard, looping back to the first after the last.

    total_cards must be the real deck length. The old version read
    st.session_state['flashcards'], a key nothing ever set, so the length was
    always 0 and every self-assessment jumped back to card 1 (BUG-3).
    """
    if st.session_state.current_flashcard < total_cards - 1:
        st.session_state.current_flashcard += 1
    else:
        st.session_state.current_flashcard = 0  # Loop back to beginning
    st.session_state.flashcard_answer_visible = False
    st.rerun()


def display_outline(outline):
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


def render_outline_recursive(outline_items, depth):
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


def display_key_terms(terms):
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


def display_term(term):
    """Display a single KeyTerm model with its definition and context."""
    with st.expander(f"📖 {term.term or 'Term'}"):
        st.write(f"**Definition**: {term.definition or 'No definition available'}")
        if term.context:
            st.write(f"**Context**: {term.context}")
        if term.related_terms:
            st.write(f"**Related Terms**: {', '.join(term.related_terms)}")


def generate_quiz_content(
    final_text, quiz_type, num_questions, difficulty, mcq_count=0, tf_count=0, open_count=0
):
    """Generate a quiz and store it (as a Quiz model) in session state."""
    with st.spinner(f"🤖 Generating quiz using {ai_provider}..."):
        try:
            if quiz_type == "Open-ended Questions":
                quiz = quiz_gen.generate_open_ended(client, provider_cfg, final_text, num_questions, difficulty)
            elif quiz_type == "Complete Mix (All Types)":
                quiz = quiz_gen.generate_mixed(
                    client, provider_cfg, final_text, mcq_count, tf_count, open_count, difficulty
                )
            else:
                quiz = quiz_gen.generate_quiz(client, provider_cfg, final_text, quiz_type, num_questions, difficulty)

            # Track analytics
            analytics.track_feature_usage("quiz_generation")
            analytics.track_ai_provider_usage(st.session_state.ai_provider)

            st.session_state.quiz_generated = True
            st.session_state.quiz_data = quiz
            st.session_state.quiz_difficulty = difficulty  # Store difficulty for results
            st.session_state.quiz_type = quiz_type  # Store quiz type
            st.success("✅ Quiz generated successfully! Start answering below.")
            st.rerun()

        except GenerationFailed as e:
            st.error(f"❌ Could not generate a valid quiz: {e}")
            st.info("Try again, or switch to a more capable model/provider in the sidebar.")
        except Exception as e:
            st.error(f"❌ Error during quiz generation: {str(e)}")
            # Add debug information
            st.write("**Debug Info:**")
            st.write(f"- AI Provider: {ai_provider}")
            st.write(f"- Quiz Type: {quiz_type}")
            st.write(f"- Text Length: {len(final_text)} characters")
            if app_config.DEBUG_MODE:
                st.exception(e)


def generate_study_materials_content(final_text, material_type, local_vars):
    """Generate a study-material model and store it in session state."""
    generation_start_time = time.time()

    with st.spinner(f"📚 Generating {material_type.lower()} using {ai_provider}..."):
        try:
            if material_type == "Complete Study Guide":
                materials_data = materials_gen.generate_study_guide(
                    client,
                    provider_cfg,
                    final_text,
                    local_vars.get("guide_type", "comprehensive"),
                    generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            elif material_type == "Summary Only":
                materials_data = materials_gen.generate_summary(
                    client, provider_cfg, final_text, local_vars.get("summary_type", "detailed")
                )
            elif material_type == "Cheat Sheet":
                materials_data = materials_gen.generate_cheat_sheet(
                    client, provider_cfg, final_text, local_vars.get("cheat_format", "comprehensive")
                )
            elif material_type == "Flashcards":
                materials_data = materials_gen.generate_flashcards(
                    client,
                    provider_cfg,
                    final_text,
                    local_vars.get("card_count", 15),
                    local_vars.get("flashcard_difficulty", "mixed"),
                )
            elif material_type == "Study Outline":
                materials_data = materials_gen.generate_outline(
                    client, provider_cfg, final_text, local_vars.get("outline_depth", "detailed")
                )
            elif material_type == "Key Terms":
                materials_data = materials_gen.generate_key_terms(
                    client, provider_cfg, final_text, local_vars.get("term_count", 15)
                )
            else:
                st.error(f"❌ Unknown material type: {material_type}")
                return

            generation_time = time.time() - generation_start_time
            analytics.track_materials_generation(material_type, generation_time, True)
            analytics.track_feature_usage("study_materials")
            analytics.track_ai_provider_usage(st.session_state.ai_provider)

            st.session_state.materials_generated = True
            st.session_state.materials_data = materials_data
            st.session_state.material_type = material_type
            st.success(f"✅ {material_type} generated successfully!")
            st.rerun()

        except GenerationFailed as e:
            analytics.track_materials_generation(
                material_type, time.time() - generation_start_time, False
            )
            st.error(f"❌ Could not generate valid {material_type.lower()}: {e}")
            st.info("Try again, or switch to a more capable model/provider in the sidebar.")
        except Exception as e:
            analytics.track_materials_generation(
                material_type, time.time() - generation_start_time, False
            )
            st.error(f"❌ Error during {material_type.lower()} generation: {str(e)}")
            st.write("**Debug Info:**")
            st.write(f"- AI Provider: {ai_provider}")
            st.write(f"- Material Type: {material_type}")
            st.write(f"- Text Length: {len(final_text)} characters")
            if app_config.DEBUG_MODE:
                st.exception(e)


def main():
    global client, provider_cfg, ai_provider, client_successful, provider_error

    # Main navigation
    st.sidebar.title("🎯 Navigation")
    app_mode = st.sidebar.selectbox(
        "Choose App Mode",
        ["📚 Quiz & Study Materials", "📊 Learning Analytics"],
        help="Switch between main app features and learning analytics",
    )

    if app_mode == "📊 Learning Analytics":
        # Display the analytics dashboard
        analytics.display_analytics_dashboard()
        return

    # Main app continues here
    st.title("📚 AI Interactive Quiz & Study Materials Generator")

    # Display AI provider info - use the actual working provider, not the selected one
    if ai_provider == "Local AI (Ollama)":
        provider_emoji = "🏠"
        provider_color = "orange"
    elif ai_provider == "Google AI":
        provider_emoji = "🆕"
        provider_color = "green"
    else:
        provider_emoji = "⚡"
        provider_color = "blue"

    st.info(
        f"{provider_emoji} **Powered by {ai_provider}** - Advanced AI for intelligent quiz generation and study materials creation"
    )

    # Initialize session state
    if "quiz_generated" not in st.session_state:
        st.session_state.quiz_generated = False
    if "materials_generated" not in st.session_state:
        st.session_state.materials_generated = False
    if "text_summarized" not in st.session_state:
        st.session_state.text_summarized = False
    if "summarized_text" not in st.session_state:
        st.session_state.summarized_text = ""
    if "original_text" not in st.session_state:
        st.session_state.original_text = ""
    if "summarization_in_progress" not in st.session_state:
        st.session_state.summarization_in_progress = False

    # Sidebar for app configuration
    with st.sidebar:
        st.header("App Configuration")

        # AI Provider Selection with status
        selected_provider = session_manager.render_provider_selector()

        # If provider changed, reinitialize client
        if selected_provider != st.session_state.ai_provider:
            st.session_state.ai_provider = selected_provider
            client, provider_cfg, ai_provider, client_successful, provider_error = (
                resolve_active_client()
            )
            st.rerun()

        # API Key Configuration
        session_manager.render_api_key_inputs()

        st.markdown("---")

        uploaded_file = st.file_uploader(
            "Upload PDF, Word, or PPTX file", type=["pdf", "docx", "pptx"]
        )

        # Content generation type selector
        generation_type = st.selectbox(
            "Choose Generation Type",
            ["Interactive Quiz", "Study Materials"],
            help="Select whether to generate a quiz or study materials",
        )

        if generation_type == "Interactive Quiz":
            quiz_type = st.selectbox(
                "Choose Quiz Type",
                [
                    "Multiple Choice",
                    "True or False",
                    "Mixed (MCQ + T/F)",
                    "Open-ended Questions",
                    "Complete Mix (All Types)",
                ],
            )
            difficulty = st.selectbox(
                "Choose Difficulty Level",
                ["Standard", "Advanced", "Extreme"],
                index=0,  # Default to Standard
                help="Standard: University-level | Advanced: Graduate-level | Extreme: Expert-level with tricky elements",
            )

            # Adjust question count based on quiz type
            if quiz_type == "Open-ended Questions":
                num_questions = st.slider("Number of Questions", min_value=2, max_value=5, value=3)
                if st.session_state.ai_provider not in ["Local AI (Ollama)", "Google AI"]:
                    st.warning(
                        "💡 Open-ended questions use gpt-4o-mini for scoring and may increase API costs. Each answer requires an additional AI evaluation."
                    )
            elif quiz_type == "Complete Mix (All Types)":
                st.write("**Question Distribution:**")
                mcq_count = st.slider("Multiple Choice", min_value=1, max_value=5, value=2)
                tf_count = st.slider("True/False", min_value=1, max_value=5, value=2)
                open_count = st.slider("Open-ended", min_value=1, max_value=3, value=1)
                num_questions = mcq_count + tf_count + open_count
                st.info(f"Total questions: {num_questions}")
                if open_count > 0 and st.session_state.ai_provider not in [
                    "Local AI (Ollama)",
                    "Google AI",
                ]:
                    st.warning(
                        f"⚠️ {open_count} open-ended question(s) will use gpt-4o-mini for scoring (higher cost)"
                    )
            else:
                num_questions = st.slider(
                    "Number of Questions",
                    min_value=quiz_config.MIN_QUESTIONS,
                    max_value=quiz_config.MAX_QUESTIONS,
                    value=quiz_config.DEFAULT_QUESTIONS,
                )

        else:  # Study Materials
            material_type = st.selectbox(
                "Choose Study Material Type",
                [
                    "Complete Study Guide",
                    "Summary Only",
                    "Cheat Sheet",
                    "Flashcards",
                    "Study Outline",
                    "Key Terms",
                ],
                help="Select the type of study material to generate",
            )

            if material_type == "Complete Study Guide":
                guide_type = st.selectbox(
                    "Study Guide Type",
                    ["comprehensive", "exam_prep", "quick_review"],
                    format_func=lambda x: {
                        "comprehensive": "📚 Comprehensive Guide (4-6 hours study time)",
                        "exam_prep": "🎯 Exam Preparation (6-8 hours study time)",
                        "quick_review": "⚡ Quick Review (2-3 hours study time)",
                    }[x],
                )
            elif material_type == "Summary Only":
                summary_type = st.selectbox(
                    "Summary Type",
                    ["detailed", "concise", "bullet_points"],
                    format_func=lambda x: {
                        "detailed": "📖 Detailed Summary (300-500 words)",
                        "concise": "📝 Concise Summary (150-250 words)",
                        "bullet_points": "• Bullet Points Summary",
                    }[x],
                )
            elif material_type == "Cheat Sheet":
                cheat_format = st.selectbox(
                    "Cheat Sheet Format",
                    ["comprehensive", "formulas", "definitions", "quick_ref"],
                    format_func=lambda x: {
                        "comprehensive": "📋 Comprehensive Reference",
                        "formulas": "🔢 Formulas & Equations",
                        "definitions": "📚 Definitions & Terms",
                        "quick_ref": "⚡ Quick Reference",
                    }[x],
                )
            elif material_type == "Flashcards":
                card_count = st.slider("Number of Flashcards", min_value=5, max_value=30, value=15)
                flashcard_difficulty = st.selectbox(
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
            elif material_type == "Study Outline":
                outline_depth = st.selectbox(
                    "Outline Depth",
                    ["overview", "detailed", "comprehensive"],
                    index=1,  # Default to detailed
                    format_func=lambda x: {
                        "overview": "📝 Overview (1-2 levels)",
                        "detailed": "📋 Detailed (3-4 levels)",
                        "comprehensive": "📚 Comprehensive (4-5 levels)",
                    }[x],
                )
            elif material_type == "Key Terms":
                term_count = st.slider("Number of Key Terms", min_value=5, max_value=30, value=15)

        if uploaded_file:
            st.success("✅ File uploaded successfully!")

        # Show local AI status if selected
        if st.session_state.ai_provider == "Local AI (Ollama)":
            st.markdown("---")
            st.subheader("🏠 Local AI Status")
            ollama_base_url = f"http://{local_ai_config.HOST}:{local_ai_config.PORT}"
            available_models = list_ollama_models(ollama_base_url)
            if available_models:
                st.success("✅ Ollama server running")
                # Initialize selected model in session state
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

                # Update session state if model changed
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

                # Show current model info
                st.info(f"🎯 **Active Model:** {st.session_state.selected_local_model}")

                # Show all available models in expander
                with st.expander(f"📦 All Available Models ({len(available_models)})"):
                    for model in available_models:
                        is_current = model == st.session_state.selected_local_model
                        marker = "🔹 **" if is_current else "• "
                        end_marker = "** (Active)" if is_current else ""
                        st.write(f"{marker}{model}{end_marker}")
            else:
                st.error("❌ Ollama server not running, or no models installed")
                st.code("ollama serve\nollama pull gemma2:2b")

    if uploaded_file and not (
        st.session_state.quiz_generated or st.session_state.materials_generated
    ):
        # Enforce the upload size limit (README advertises it; nothing enforced it)
        max_upload_bytes = quiz_config.MAX_UPLOAD_MB * 1024 * 1024
        if uploaded_file.size > max_upload_bytes:
            st.error(
                f"❌ File is {uploaded_file.size / (1024 * 1024):.1f}MB, which exceeds "
                f"the {quiz_config.MAX_UPLOAD_MB}MB limit. Please upload a smaller file."
            )
            return

        ext = uploaded_file.name.split(".")[-1]

        # Create a unique identifier for the uploaded file
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        current_file_id = getattr(st.session_state, "current_file_id", None)

        # Check if this is a new file
        if file_id != current_file_id:
            # Reset all states for new file
            st.session_state.current_file_id = file_id
            st.session_state.text_summarized = False
            st.session_state.summarized_text = ""
            st.session_state.original_text = ""
            st.session_state.summarization_in_progress = False
            st.session_state.quiz_generated = False

            # Track document upload
            analytics.track_feature_usage("document_upload")
            analytics.add_to_learning_history(
                "document_upload",
                {
                    "filename": uploaded_file.name,
                    "file_type": uploaded_file.name.split(".")[-1],
                    "file_size": uploaded_file.size,
                },
            )

        # Extract text only if we don't have it already
        if not st.session_state.original_text:
            try:
                text = extract_text(uploaded_file.getvalue(), ext)
            except ExtractionError as e:
                st.error(f"❌ {e}")
                return

            if not text.strip():
                st.error("❌ No text found in the uploaded file")
                return

            # Store the original text
            st.session_state.original_text = text
        else:
            # Use the stored text
            text = st.session_state.original_text

        # Show document preview
        with st.expander("📄 Document Preview"):
            preview_text = (
                st.session_state.summarized_text if st.session_state.text_summarized else text
            )
            st.text_area(
                "Extracted Text",
                preview_text[:1000] + "..." if len(preview_text) > 1000 else preview_text,
                height=200,
            )

        # Handle summarization logic
        needs_summarization = (
            len(text) > quiz_config.SUMMARY_THRESHOLD and not st.session_state.text_summarized
        )

        if needs_summarization and not st.session_state.summarization_in_progress:
            # Start summarization automatically
            st.session_state.summarization_in_progress = True
            st.info("📄 Large content detected. Summarizing automatically...")

            # Check if we have a working client for summarization
            if not client_successful:
                st.warning("⚠️ No AI provider available for summarization. Using original text.")
                st.session_state.summarized_text = text
                st.session_state.text_summarized = True
                st.session_state.summarization_in_progress = False
                st.rerun()
            else:
                with st.spinner("Summarizing content..."):
                    summarized = summarize_text(text)
                    st.session_state.summarized_text = summarized
                    st.session_state.text_summarized = True
                    st.session_state.summarization_in_progress = False
                    st.success("✅ Content summarized successfully!")
                    st.rerun()

        # Show summarization status
        if st.session_state.summarization_in_progress:
            st.info("🔄 Summarization in progress... Please wait.")
            st.stop()  # Prevent the rest of the UI from rendering
        elif st.session_state.text_summarized:
            st.success(
                f"✅ Content summarized (Original: {len(text):,} chars → Summary: {len(st.session_state.summarized_text):,} chars)"
            )

        # Determine which text to use for quiz generation
        final_text = st.session_state.summarized_text if st.session_state.text_summarized else text

        # Generation button - only show if summarization is complete (if needed)
        if needs_summarization and not st.session_state.text_summarized:
            st.info("⏳ Please wait for summarization to complete before generating content.")
        else:
            if generation_type == "Interactive Quiz":
                button_text = "🎯 Generate Interactive Quiz"
                button_help = "Create an interactive quiz from your document"
            else:
                button_text = f"📚 Generate {material_type}"
                button_help = f"Create {material_type.lower()} from your document"

            if st.button(button_text, type="primary", help=button_help):
                # Check if we have a working client before attempting generation
                if not client_successful:
                    st.error(
                        "❌ No working AI provider available. Please configure an AI provider in the sidebar first."
                    )
                    st.info("💡 **Quick Setup Guide:**")
                    st.info(
                        "1. **Local AI**: Start Ollama server (`ollama serve`) and pull a model (`ollama pull gemma2:2b`)"
                    )
                    st.info("2. **Google AI**: Enter your Google AI API key in the sidebar")
                    st.info("3. **OpenAI**: Enter your OpenAI API key in the sidebar")
                    return

                if generation_type == "Interactive Quiz":
                    generate_quiz_content(
                        final_text,
                        quiz_type,
                        num_questions,
                        difficulty,
                        mcq_count if "mcq_count" in locals() else 0,
                        tf_count if "tf_count" in locals() else 0,
                        open_count if "open_count" in locals() else 0,
                    )
                else:
                    generate_study_materials_content(final_text, material_type, locals())

    elif uploaded_file and st.session_state.quiz_generated:
        # Display the interactive quiz
        st.markdown("---")
        display_quiz(st.session_state.quiz_data)

        # Reset quiz button in sidebar
        with st.sidebar:
            st.markdown("---")
            if st.button("🔄 Generate New Quiz"):
                st.session_state.quiz_generated = False
                st.session_state.current_question = 0
                st.session_state.user_answers = {}
                st.session_state.quiz_completed = False
                st.session_state.quiz_finalized = False
                st.session_state.quiz_results = {}
                # Keep the summarized text to avoid re-summarization
                st.rerun()

    elif uploaded_file and st.session_state.materials_generated:
        # Display the study materials
        st.markdown("---")
        display_study_materials(st.session_state.materials_data, st.session_state.material_type)

        # Reset materials button in sidebar
        with st.sidebar:
            st.markdown("---")
            if st.button("🔄 Generate New Materials"):
                st.session_state.materials_generated = False
                # Keep the summarized text to avoid re-summarization
                st.rerun()

    else:
        # Welcome screen with improved guidance

        # Quick Analytics Preview
        if (
            st.session_state.quiz_analytics["total_quizzes"] > 0
            or st.session_state.materials_analytics["total_materials"] > 0
        ):
            st.subheader("📊 Quick Analytics Overview")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Quizzes Completed", st.session_state.quiz_analytics["total_quizzes"])

            with col2:
                if st.session_state.quiz_analytics["performance_over_time"]:
                    scores = [
                        entry["score_percentage"]
                        for entry in st.session_state.quiz_analytics["performance_over_time"]
                    ]
                    avg_score = sum(scores) / len(scores)
                    st.metric("Average Score", f"{avg_score:.1f}%")
                else:
                    st.metric("Average Score", "N/A")

            with col3:
                st.metric(
                    "Materials Generated", st.session_state.materials_analytics["total_materials"]
                )

            with col4:
                session_duration = datetime.now() - st.session_state.session_start_time
                hours, remainder = divmod(session_duration.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                st.metric("Session Time", f"{int(hours):02d}:{int(minutes):02d}")

            # Quick recommendation
            if st.session_state.quiz_analytics["total_quizzes"] >= 2:
                analysis = analytics.get_strength_weakness_analysis()
                if analysis["recommendations"]:
                    st.info(f"💡 **Quick Tip**: {analysis['recommendations'][0]}")

            st.info("📊 **View detailed analytics by switching to Analytics mode in the sidebar!**")
            st.markdown("---")

        st.markdown("""
        ## Welcome to the AI Interactive Quiz Generator & Study Materials Creator! 🎓
        
        This application creates personalized, interactive quizzes and comprehensive study materials from your documents with **advanced AI scoring**, **graceful error handling**, and **comprehensive learning analytics**.
        
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
        - **📖 Complete Study Guide**: Comprehensive package with summary, cheat sheet, flashcards, key terms + study plan
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
            
            **📖 Summary**: "Cell membrane is a selectively permeable barrier that controls substance transport..."
            
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
            st.markdown("""
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
            
            # 3. Download Gemma 2B model (recommended for speed)
            ollama pull gemma2:2b
            
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
            - Check server status: `curl http://localhost:[PORT]/api/tags`
            - View logs: Check terminal where `ollama serve` is running
            """)

        # Add example of open-ended scoring
        with st.expander("🔍 See Open-ended Question Example"):
            st.markdown("""
            **Example Question:** *Explain the chemical composition and importance of water (4 marks)*
            
            **Sample Answer:** 
            "Water is a liquid encompassed with two hydrogens and one oxygen. It is a crucial composition that its existence guarantees life."
            
            **AI Scoring Breakdown:**
            - ✅ Chemical composition (H2O) - 2/2 marks
            - ⚠️ Physical properties mentioned - 1/1 mark  
            - ✅ Biological importance stated - 1/1 mark
            
            **Result:** 4/4 marks (100%) with specific feedback on scientific accuracy!
            """)

        st.info(
            "💡 **Pro Tip:** The app now works gracefully even with provider errors. Configure your preferred AI provider in the sidebar and start generating quizzes or study materials!"
        )


if __name__ == "__main__":
    main()
