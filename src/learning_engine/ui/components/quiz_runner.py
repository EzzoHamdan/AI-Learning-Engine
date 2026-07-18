"""Interactive quiz runner: question navigation and answer capture."""

from __future__ import annotations

import streamlit as st

from learning_engine.models import Quiz
from learning_engine.ui import state
from learning_engine.ui.components.results import display_results, finalize_quiz
from learning_engine.ui.providers import ActiveProvider


def display_quiz(quiz: Quiz, active: ActiveProvider) -> None:
    """Display the interactive quiz (a Quiz model) and capture user answers."""
    questions = quiz.questions
    if not questions:
        st.error("No questions found in the quiz data.")
        return

    # Initialize / reset progress whenever a new quiz object is loaded
    if "current_question" not in st.session_state or state.quiz_data() is not quiz:
        state.begin_quiz(quiz)

    total_questions = len(questions)

    if not state.quiz_completed():
        current_q = state.current_question()
        question = questions[current_q]

        st.progress(current_q / total_questions)
        st.write(f"Question {current_q + 1} of {total_questions}")
        st.subheader(f"Q{current_q + 1}: {question.question}")

        is_open_ended = question.type == "open_ended"
        if is_open_ended:
            st.info(f"📝 **Open-ended Question** | Total Marks: {question.total_marks}")
            st.caption("💡 Write a comprehensive answer. Quality matters more than quantity!")
            current_answer = state.user_answers().get(current_q, "")
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
                state.set_current_question(current_q - 1)
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
                        state.record_answer(current_q, user_answer)
                        state.set_current_question(current_q + 1)
                        st.rerun()
                elif st.button("Submit Quiz"):
                    state.record_answer(current_q, user_answer)
                    state.set_quiz_completed()
                    st.rerun()
            elif is_open_ended:
                st.caption("⚠️ Please write at least 5 words to proceed")
            else:
                st.caption("⚠️ Please select an answer to proceed")
    else:
        # Score + record analytics exactly once on entry to the completed state,
        # then render read-only (BUG-2).
        if not state.quiz_finalized():
            finalize_quiz(questions, state.user_answers(), active)
            state.set_quiz_finalized()
        display_results(questions, state.user_answers())
