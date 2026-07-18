"""Session-scoped analytics tracking (the write side of analytics).

Extracted from the old learning_analytics.py God class: this keeps only the
event-recording methods that mutate st.session_state. Pure math lives in
analytics/metrics.py; dashboard rendering lives in ui/pages/analytics.py.
The tracker is constructed once per session via ui.state.tracker() — the old
import-time singleton is gone.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from learning_engine.analytics import metrics


class AnalyticsTracker:
    """Records learning events into st.session_state for the current session."""

    def __init__(self) -> None:
        self._init_session_state()

    def _init_session_state(self) -> None:
        if "session_start_time" not in st.session_state:
            st.session_state.session_start_time = datetime.now()

        if "learning_history" not in st.session_state:
            st.session_state.learning_history = []

        if "quiz_analytics" not in st.session_state:
            st.session_state.quiz_analytics = {
                "total_quizzes": 0,
                "total_questions": 0,
                "total_correct": 0,
                "difficulty_breakdown": {"Standard": 0, "Advanced": 0, "Extreme": 0},
                "type_breakdown": {
                    "Multiple Choice": 0,
                    "True or False": 0,
                    "Open-ended": 0,
                    "Mixed": 0,
                },
                "performance_over_time": [],
                "detailed_results": [],
            }

        if "materials_analytics" not in st.session_state:
            st.session_state.materials_analytics = {
                "total_materials": 0,
                "material_types": {},
                "generation_times": [],
                "material_history": [],
            }

        if "engagement_metrics" not in st.session_state:
            st.session_state.engagement_metrics = {
                "total_time_spent": 0,
                "documents_processed": 0,
                "ai_provider_usage": {},
                "feature_usage": {},
                "flashcard_interactions": {
                    "cards_viewed": 0,
                    "correct_responses": 0,
                    "incorrect_responses": 0,
                    "skipped_responses": 0,
                },
            }

    # ----------------------------------------------------------------- #
    # Read-side conveniences for the dashboard / welcome screen
    # ----------------------------------------------------------------- #

    @property
    def session_start_time(self) -> datetime:
        return st.session_state.session_start_time

    @property
    def learning_history(self) -> list[dict]:
        return st.session_state.learning_history

    @property
    def quiz_analytics(self) -> dict:
        return st.session_state.quiz_analytics

    @property
    def materials_analytics(self) -> dict:
        return st.session_state.materials_analytics

    @property
    def engagement_metrics(self) -> dict:
        return st.session_state.engagement_metrics

    # ----------------------------------------------------------------- #
    # Event tracking
    # ----------------------------------------------------------------- #

    def track_quiz_completion(
        self, quiz_data: dict, user_answers: dict, performance_stats: dict
    ) -> None:
        """Track quiz completion and update analytics."""
        completion_time = datetime.now()
        questions = quiz_data.get("questions", [])

        total_questions = len(questions)
        correct_count = performance_stats.get("traditional_correct", 0)
        overall_percentage = performance_stats.get("overall_percentage", 0)

        difficulty = st.session_state.get("quiz_difficulty", "Standard")
        quiz_type = st.session_state.get("quiz_type", "Mixed")

        analytics = self.quiz_analytics
        analytics["total_quizzes"] += 1
        analytics["total_questions"] += total_questions
        analytics["total_correct"] += correct_count
        analytics["difficulty_breakdown"][difficulty] += 1

        quiz_type_mapping = {
            "Multiple Choice": "Multiple Choice",
            "True or False": "True or False",
            "Mixed (MCQ + T/F)": "Mixed",
            "Open-ended Questions": "Open-ended",
            "Complete Mix (All Types)": "Mixed",
        }
        mapped_type = quiz_type_mapping.get(quiz_type, "Mixed")
        analytics["type_breakdown"][mapped_type] += 1

        analytics["performance_over_time"].append(
            {
                "timestamp": completion_time,
                "score_percentage": overall_percentage,
                "difficulty": difficulty,
                "quiz_type": quiz_type,
                "total_questions": total_questions,
                "correct_answers": correct_count,
            }
        )

        detailed_result = {
            "timestamp": completion_time,
            "quiz_id": len(analytics["detailed_results"]) + 1,
            "difficulty": difficulty,
            "quiz_type": quiz_type,
            "questions": [],
            "overall_score": overall_percentage,
        }

        for i, question in enumerate(questions):
            user_answer = user_answers.get(i, "")
            is_correct = False

            if question.get("type") == "open_ended":
                for scored_i, _question, result in performance_stats.get("open_ended_scores", []):
                    if scored_i == i:
                        # Consider 60%+ as correct
                        is_correct = result.get("percentage", 0) >= 60
                        break
            else:
                correct_answer = question["correct_answer"]
                if len(question["options"]) > 2:
                    user_letter = (
                        user_answer[0]
                        if user_answer and user_answer[0] in ["A", "B", "C", "D"]
                        else ""
                    )
                else:
                    user_letter = user_answer
                is_correct = user_letter == correct_answer

            detailed_result["questions"].append(
                {
                    "question_id": i + 1,
                    "question_type": question.get("type", "mcq_tf"),
                    "correct": is_correct,
                    "user_answer": user_answer,
                    "correct_answer": question.get("correct_answer", ""),
                    "response_time": None,  # could be tracked in future
                    "difficulty_tag": metrics.analyze_question_difficulty(
                        question.get("question", "")
                    ),
                }
            )

        analytics["detailed_results"].append(detailed_result)

        self.add_to_learning_history(
            "quiz_completion",
            {
                "score": overall_percentage,
                "difficulty": difficulty,
                "type": quiz_type,
                "questions": total_questions,
            },
        )

    def track_materials_generation(
        self, material_type: str, generation_time: float, success: bool
    ) -> None:
        """Track study materials generation."""
        timestamp = datetime.now()
        analytics = self.materials_analytics

        if success:
            analytics["total_materials"] += 1
            analytics["material_types"].setdefault(material_type, 0)
            analytics["material_types"][material_type] += 1

        analytics["generation_times"].append(
            {
                "timestamp": timestamp,
                "material_type": material_type,
                "generation_time": generation_time,
                "success": success,
            }
        )
        analytics["material_history"].append(
            {
                "timestamp": timestamp,
                "type": material_type,
                "success": success,
                "generation_time": generation_time,
            }
        )

        self.add_to_learning_history(
            "materials_generation",
            {"type": material_type, "success": success, "time": generation_time},
        )

    def track_flashcard_interaction(self, action: str) -> None:
        """Track flashcard interactions."""
        counters = {
            "viewed": "cards_viewed",
            "correct": "correct_responses",
            "incorrect": "incorrect_responses",
            "skipped": "skipped_responses",
        }
        counter = counters.get(action)
        if counter is None:
            return

        self.engagement_metrics["flashcard_interactions"][counter] += 1
        self.track_feature_usage("flashcards")

    def track_feature_usage(self, feature: str) -> None:
        """Track usage of different app features."""
        usage = self.engagement_metrics.setdefault("feature_usage", {})
        usage.setdefault(feature, 0)
        usage[feature] += 1

    def track_ai_provider_usage(self, provider: str) -> None:
        """Track AI provider usage."""
        usage = self.engagement_metrics.setdefault("ai_provider_usage", {})
        usage.setdefault(provider, 0)
        usage[provider] += 1

    def add_to_learning_history(self, activity_type: str, data: dict) -> None:
        """Add an activity to the learning history."""
        self.learning_history.append(
            {"timestamp": datetime.now(), "type": activity_type, "data": data}
        )
