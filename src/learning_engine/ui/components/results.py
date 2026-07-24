"""Quiz scoring-on-completion and the read-only results view.

finalize_quiz runs exactly once, on the transition into the completed state:
it scores (including the open-ended LLM calls) and records analytics, storing
everything in session state. display_results only reads (BUG-2 stays fixed).
"""

from __future__ import annotations

import streamlit as st

from learning_engine.export import quiz_to_markdown
from learning_engine.generation import quiz as quiz_gen
from learning_engine.models import MCQQuestion, OpenEndedQuestion, Quiz
from learning_engine.ui import difficulty as difficulty_ui
from learning_engine.ui import state
from learning_engine.ui.providers import ActiveProvider

Question = MCQQuestion | OpenEndedQuestion


def mcq_letter(user_answer: str) -> str:
    """Extract the chosen A/B/C/D letter from a selected option string."""
    if user_answer and user_answer[0] in ("A", "B", "C", "D"):
        return user_answer[0]
    return ""


def finalize_quiz(
    questions: list[Question], user_answers: dict[int, str], active: ActiveProvider
) -> None:
    """Score the quiz and record analytics exactly once, on completion (BUG-2)."""
    # isinstance rather than a `.type` comparison: it partitions the union into
    # the two concrete models, so each branch below gets the fields it needs.
    traditional = [(i, q) for i, q in enumerate(questions) if isinstance(q, MCQQuestion)]
    open_ended = [(i, q) for i, q in enumerate(questions) if isinstance(q, OpenEndedQuestion)]

    # Score traditional questions
    traditional_correct = 0
    for i, q in traditional:
        answer = user_answers.get(i, "")
        user_letter = mcq_letter(answer) if len(q.options) > 2 else answer
        if user_letter == q.correct_answer:
            traditional_correct += 1
    total_traditional = len(traditional)

    # Score open-ended questions with AI (runs once, not on every rerun)
    open_ended_scores = []  # list of (index, OpenEndedQuestion, ScoringResult)
    total_open_ended_marks = 0.0
    earned_open_ended_marks = 0.0
    if open_ended and active.ok:
        st.info("🤖 Scoring open-ended questions with AI... This may take a moment.")
        progress_bar = st.progress(0)
        client, cfg = active.require()
        for idx, (i, open_q) in enumerate(open_ended):
            result = quiz_gen.score_open_ended(client, cfg, open_q, user_answers.get(i, ""))
            open_ended_scores.append((i, open_q, result))
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

    state.set_quiz_results(
        {
            "traditional_correct": traditional_correct,
            "total_traditional": total_traditional,
            "open_ended_scores": open_ended_scores,
            "total_open_ended_marks": total_open_ended_marks,
            "earned_open_ended_marks": earned_open_ended_marks,
            "overall_percentage": overall,
        }
    )

    # Analytics consumes plain dicts (the persistent store arrives in Phase 6).
    quiz = state.quiz_data()
    state.tracker().track_quiz_completion(
        quiz_data=quiz.model_dump() if quiz else {"questions": []},
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


def display_results(questions: list[Question], user_answers: dict[int, str]) -> None:
    """Render quiz results (read-only; scoring/tracking happened in finalize_quiz)."""
    st.success("🎉 Quiz Completed!")
    difficulty = state.quiz_difficulty()

    results = state.quiz_results()
    traditional_correct = results.get("traditional_correct", 0)
    total_traditional = results.get("total_traditional", 0)
    open_ended_scores = results.get("open_ended_scores", [])
    total_open_ended_marks = results.get("total_open_ended_marks", 0)
    earned_open_ended_marks = results.get("earned_open_ended_marks", 0)
    overall_percentage = results.get("overall_percentage", 0)
    emoji = difficulty_ui.emoji(difficulty)

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
    kind, message = difficulty_ui.band(difficulty, overall_percentage)
    {"success": st.success, "info": st.info, "warning": st.warning}[kind](message)

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
            user_letter = mcq_letter(user_answer) if len(question.options) > 2 else user_answer
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

    st.markdown("---")
    col_again, col_export = st.columns(2)
    with col_again:
        if st.button("Take Quiz Again"):
            state.reset_quiz_progress()
            st.rerun()
    with col_export:
        # Keep the quiz after the session ends: a worksheet plus an answer key.
        st.download_button(
            "⬇️ Download quiz (Markdown)",
            data=quiz_to_markdown(Quiz(questions=list(questions))),
            file_name="quiz.md",
            mime="text/markdown",
            help="The questions and an answer key, as a file you can keep or print.",
        )
