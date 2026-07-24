"""Learning-analytics dashboard (rendering only; the math lives in analytics/metrics).

Ported from the display half of the old learning_analytics.py God class.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

import pandas as pd
import plotly.express as px
import streamlit as st

from learning_engine.analytics import metrics
from learning_engine.ui import state
from learning_engine.ui.tracking import AnalyticsTracker

if TYPE_CHECKING:
    from learning_engine.analytics.store import AnalyticsStore


class AnalyticsView(Protocol):
    """The read surface the dashboard needs — satisfied by both the session tracker
    (in-memory, "This session") and _StoreView (persistent, "All time").

    Members are read-only properties so both a property-backed tracker and an
    attribute-backed _StoreView structurally conform."""

    @property
    def quiz_analytics(self) -> dict: ...
    @property
    def materials_analytics(self) -> dict: ...
    @property
    def engagement_metrics(self) -> dict: ...
    @property
    def learning_history(self) -> list[dict]: ...


class _StoreView:
    """All-time analytics reconstructed from the persistent store.

    Exposes the same attributes as AnalyticsTracker so every render helper works
    unchanged whether the user is viewing "This session" or "All time".
    """

    def __init__(self, store: AnalyticsStore) -> None:
        totals = store.totals()
        self.quiz_analytics = {
            "total_quizzes": totals["total_quizzes"],
            "total_questions": totals["total_questions"],
            "total_correct": totals["total_correct"],
            "difficulty_breakdown": store.difficulty_breakdown(),
            "type_breakdown": store.type_breakdown(),
            "performance_over_time": store.performance_over_time(),
            "detailed_results": store.detailed_results(),
        }
        self.materials_analytics = store.material_stats()
        self.engagement_metrics = {
            # feature/provider usage aren't persisted (session-only); existing
            # `if` guards hide their empty charts in the all-time view.
            "ai_provider_usage": {},
            "feature_usage": {},
            "flashcard_interactions": store.flashcard_totals(),
        }
        self.learning_history = store.learning_history()


def render() -> None:
    """Render the analytics dashboard page."""
    tracker = state.tracker()
    store = state.store()

    st.title("📊 Learning Analytics & Progress Tracking")

    scope = "This session"
    if store is not None:
        scope = (
            st.segmented_control(
                "View",
                ["This session", "All time"],
                default="All time",
                key="analytics_scope",
                help="'All time' spans every session (persisted); 'This session' is live only.",
            )
            or "All time"
        )
    st.markdown("---")

    view: AnalyticsView = (
        _StoreView(store) if store is not None and scope == "All time" else tracker
    )

    _session_overview(tracker, view, scope)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📈 Performance Analytics",
            "🎯 Quiz Insights",
            "📚 Study Materials",
            "🚀 Progress Tracking",
            "🔍 Detailed Analysis",
        ]
    )

    with tab1:
        _performance_analytics(view)
    with tab2:
        _quiz_insights(view)
    with tab3:
        _materials_analytics(view)
    with tab4:
        _progress_tracking(view)
    with tab5:
        _detailed_analysis(tracker, view, store, scope)


def _session_overview(tracker: AnalyticsTracker, view: AnalyticsView, scope: str) -> None:
    """Display the top-of-page overview (duration is always this session)."""
    session_duration = datetime.now() - tracker.session_start_time
    hours, remainder = divmod(session_duration.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    suffix = "this session" if scope == "This session" else "all time"

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Session Duration",
            f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}",
            help="Total time spent in current session",
        )

    with col2:
        st.metric(
            "Quizzes Completed",
            view.quiz_analytics["total_quizzes"],
            help=f"Number of quizzes completed ({suffix})",
        )

    with col3:
        st.metric(
            "Materials Generated",
            view.materials_analytics["total_materials"],
            help=f"Study materials created ({suffix})",
        )

    with col4:
        avg_score = metrics.average_score(view.quiz_analytics["performance_over_time"])
        st.metric("Average Score", f"{avg_score:.1f}%", help=f"Average quiz performance ({suffix})")


def _performance_analytics(view: AnalyticsView) -> None:
    """Display performance analytics charts and metrics."""
    st.subheader("📈 Performance Analytics")

    quiz_analytics = view.quiz_analytics
    performance_data = quiz_analytics["performance_over_time"]

    if not performance_data:
        st.info("📝 Complete some quizzes to see performance analytics!")
        return

    # Performance over time chart
    df_performance = pd.DataFrame(performance_data)
    df_performance["quiz_number"] = range(1, len(df_performance) + 1)

    fig_performance = px.line(
        df_performance,
        x="quiz_number",
        y="score_percentage",
        title="📊 Quiz Performance Over Time",
        labels={"quiz_number": "Quiz Number", "score_percentage": "Score (%)"},
        markers=True,
    )
    fig_performance.add_hline(
        y=70, line_dash="dash", line_color="green", annotation_text="Target: 70%"
    )
    fig_performance.update_layout(
        xaxis_title="Quiz Number", yaxis_title="Score Percentage (%)", showlegend=True
    )
    st.plotly_chart(fig_performance, width="stretch")

    # Performance by difficulty / type
    col1, col2 = st.columns(2)

    with col1:
        difficulty_data = quiz_analytics["difficulty_breakdown"]
        if any(difficulty_data.values()):
            fig_difficulty = px.pie(
                values=list(difficulty_data.values()),
                names=list(difficulty_data.keys()),
                title="🎯 Quiz Difficulty Distribution",
            )
            st.plotly_chart(fig_difficulty, width="stretch")

    with col2:
        type_data = quiz_analytics["type_breakdown"]
        if any(type_data.values()):
            fig_types = px.pie(
                values=list(type_data.values()),
                names=list(type_data.keys()),
                title="📝 Quiz Type Distribution",
            )
            st.plotly_chart(fig_types, width="stretch")

    # Learning velocity analysis
    velocity_data = metrics.calculate_learning_velocity(performance_data)

    if velocity_data["trend"] != "insufficient_data":
        st.subheader("🚀 Learning Velocity Analysis")

        col1, col2, col3 = st.columns(3)

        with col1:
            trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}
            trend = velocity_data["trend"]
            st.metric(
                "Learning Trend",
                f"{trend_emoji.get(trend, '➡️')} {trend.title()}",
                help="Overall learning trend based on quiz performance",
            )

        with col2:
            st.metric(
                "Velocity",
                f"{velocity_data['velocity']:.2f}%/quiz",
                help="Rate of improvement per quiz",
            )

        with col3:
            confidence = velocity_data.get("confidence", 0) * 100
            st.metric(
                "Confidence",
                f"{confidence:.0f}%",
                help="Statistical confidence in the trend analysis",
            )


def _quiz_insights(view: AnalyticsView) -> None:
    """Display detailed quiz insights and patterns."""
    st.subheader("🎯 Quiz Insights & Patterns")

    detailed_results = view.quiz_analytics["detailed_results"]

    if not detailed_results:
        st.info("📝 Complete some quizzes to see detailed insights!")
        return

    # Strength and weakness analysis
    analysis = metrics.strength_weakness_analysis(detailed_results)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💪 Strengths")
        if analysis["strengths"]:
            for strength in analysis["strengths"]:
                st.success(f"✅ {strength}")
        else:
            st.info("Complete more quizzes to identify strengths")

    with col2:
        st.subheader("🎯 Areas for Improvement")
        if analysis["weaknesses"]:
            for weakness in analysis["weaknesses"]:
                st.warning(f"⚠️ {weakness}")
        else:
            st.success("No major weaknesses identified!")

    # Recommendations
    if analysis["recommendations"]:
        st.subheader("💡 Personalized Recommendations")
        for i, recommendation in enumerate(analysis["recommendations"], 1):
            st.info(f"{i}. {recommendation}")

    # Topic breakdown — the actionable view: what to revise, not which format.
    topic_performance = analysis.get("topic_performance", {})
    if topic_performance:
        st.subheader("📚 Performance by Topic")
        topic_df = pd.DataFrame(
            [{"Topic": k, "Performance": v} for k, v in topic_performance.items()]
            # Descending, because plotly draws the FIRST row at the bottom of a
            # horizontal bar chart — so sorting descending puts the weakest topic
            # at the top, matching the title. (update_yaxes(autorange="reversed")
            # does not survive px.bar's categorical axis here.)
        ).sort_values("Performance", ascending=False)

        fig_topic = px.bar(
            topic_df,
            x="Performance",
            y="Topic",
            orientation="h",  # topic names are long; horizontal keeps them readable
            title="Accuracy by topic (weakest first)",
            color="Performance",
            color_continuous_scale="RdYlGn",
            range_color=(0, 100),
            # A 0% topic has a zero-length bar, which reads as a broken chart;
            # the text label keeps every row legible.
            text=topic_df["Performance"].map(lambda v: f"{v:.0f}%"),
        )
        fig_topic.update_traces(textposition="outside", cliponaxis=False)
        # Leave room for the outside percentage labels.
        fig_topic.update_xaxes(range=[0, 115])
        fig_topic.add_vline(x=70, line_dash="dash", annotation_text="Target: 70%")
        fig_topic.update_layout(height=max(240, 34 * len(topic_df)))
        st.plotly_chart(fig_topic, width="stretch")
    else:
        st.info(
            "📚 Topic breakdown appears once you complete a quiz generated with topic "
            "tagging — every new quiz labels its questions automatically."
        )

    # Performance breakdown charts
    if analysis["type_performance"]:
        st.subheader("📊 Performance by Question Type")

        type_df = pd.DataFrame(
            [{"Type": k, "Performance": v} for k, v in analysis["type_performance"].items()]
        )

        fig_type_performance = px.bar(
            type_df,
            x="Type",
            y="Performance",
            title="Performance by Question Type",
            color="Performance",
            color_continuous_scale="RdYlGn",
        )
        fig_type_performance.add_hline(y=70, line_dash="dash", annotation_text="Target: 70%")
        st.plotly_chart(fig_type_performance, width="stretch")

    # Recent quiz analysis
    st.subheader("📋 Recent Quiz Performance")

    recent_quiz = detailed_results[-1]
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Overall Score", f"{recent_quiz['overall_score']:.1f}%")

    with col2:
        correct_count = sum(1 for q in recent_quiz["questions"] if q["correct"])
        total_count = len(recent_quiz["questions"])
        st.metric("Questions Correct", f"{correct_count}/{total_count}")

    with col3:
        st.metric("Difficulty Level", recent_quiz["difficulty"])

    # Question-by-question breakdown
    with st.expander("🔍 Question-by-Question Analysis"):
        for i, question in enumerate(recent_quiz["questions"], 1):
            status_emoji = "✅" if question["correct"] else "❌"
            difficulty_emoji = {"high": "🔴", "medium": "🟡", "basic": "🟢"}

            st.write(
                f"{status_emoji} **Q{i}** ({question['question_type']}) "
                f"{difficulty_emoji.get(question['difficulty_tag'], '⚪')} "
                f"{question['difficulty_tag'].title()} difficulty"
            )


def _materials_analytics(view: AnalyticsView) -> None:
    """Display study materials analytics."""
    st.subheader("📚 Study Materials Analytics")

    materials_analytics = view.materials_analytics

    if materials_analytics["total_materials"] == 0:
        st.info("📚 Generate some study materials to see analytics!")
        return

    # Materials overview
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Materials", materials_analytics["total_materials"])

    with col2:
        st.metric("Unique Types", len(materials_analytics["material_types"]))

    with col3:
        generation_times = materials_analytics["generation_times"]
        successful = [gt for gt in generation_times if gt["success"]]
        if successful:
            avg_time = sum(gt["generation_time"] for gt in successful) / len(successful)
            st.metric("Avg Generation Time", f"{avg_time:.1f}s")

    # Materials distribution
    if materials_analytics["material_types"]:
        fig_materials = px.bar(
            x=list(materials_analytics["material_types"].keys()),
            y=list(materials_analytics["material_types"].values()),
            title="📊 Generated Materials by Type",
            labels={"x": "Material Type", "y": "Count"},
        )
        st.plotly_chart(fig_materials, width="stretch")

    # Generation success rate
    if generation_times:
        success_rate = len(successful) / len(generation_times) * 100
        st.metric("Generation Success Rate", f"{success_rate:.1f}%")

        # Generation time trend
        df_generation = pd.DataFrame(generation_times)
        df_generation["attempt_number"] = range(1, len(df_generation) + 1)

        fig_generation_time = px.scatter(
            df_generation,
            x="attempt_number",
            y="generation_time",
            color="success",
            title="📈 Material Generation Time Trend",
            labels={"attempt_number": "Attempt Number", "generation_time": "Time (seconds)"},
        )
        st.plotly_chart(fig_generation_time, width="stretch")


def _progress_tracking(view: AnalyticsView) -> None:
    """Display progress tracking and goal setting."""
    st.subheader("🚀 Progress Tracking & Goals")

    # Learning goals section
    st.subheader("🎯 Learning Goals")

    col1, col2 = st.columns(2)

    with col1:
        target_score = st.slider(
            "Target Average Score (%)",
            min_value=50,
            max_value=100,
            value=80,
            help="Set your target average quiz score",
        )

    with col2:
        target_quizzes = st.slider(
            "Quiz Goal (per session)",
            min_value=1,
            max_value=20,
            value=5,
            help="Set your target number of quizzes per session",
        )

    # Progress towards goals
    quiz_analytics = view.quiz_analytics
    current_avg = metrics.average_score(quiz_analytics["performance_over_time"])
    current_quizzes = quiz_analytics["total_quizzes"]

    col1, col2 = st.columns(2)

    with col1:
        score_progress = min(current_avg / target_score * 100, 100)
        st.metric(
            "Score Goal Progress",
            f"{current_avg:.1f}% / {target_score}%",
            delta=f"{score_progress:.1f}% complete",
        )
        st.progress(score_progress / 100)

    with col2:
        quiz_progress = min(current_quizzes / target_quizzes * 100, 100)
        st.metric(
            "Quiz Goal Progress",
            f"{current_quizzes} / {target_quizzes}",
            delta=f"{quiz_progress:.1f}% complete",
        )
        st.progress(quiz_progress / 100)

    # Learning streaks
    st.subheader("🔥 Learning Streaks")

    learning_history = view.learning_history
    if learning_history:
        unique_days = {entry["timestamp"].date() for entry in learning_history}
        current_streak = metrics.calculate_current_streak(unique_days, datetime.now().date())

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Current Streak", f"{current_streak} days")

        with col2:
            st.metric("Total Active Days", len(unique_days))

        with col3:
            longest_streak = metrics.calculate_longest_streak(unique_days)
            st.metric("Longest Streak", f"{longest_streak} days")

    # Engagement metrics
    st.subheader("📊 Engagement Metrics")

    engagement = view.engagement_metrics

    if engagement["feature_usage"]:
        fig_engagement = px.bar(
            x=list(engagement["feature_usage"].keys()),
            y=list(engagement["feature_usage"].values()),
            title="🎯 Feature Usage Distribution",
            labels={"x": "Feature", "y": "Usage Count"},
        )
        st.plotly_chart(fig_engagement, width="stretch")

    # AI Provider usage
    if engagement["ai_provider_usage"]:
        fig_providers = px.pie(
            values=list(engagement["ai_provider_usage"].values()),
            names=list(engagement["ai_provider_usage"].keys()),
            title="🤖 AI Provider Usage Distribution",
        )
        st.plotly_chart(fig_providers, width="stretch")


def _detailed_analysis(
    tracker: AnalyticsTracker,
    view: AnalyticsView,
    store: AnalyticsStore | None,
    scope: str,
) -> None:
    """Display detailed analysis, data export, and (persistent) data reset."""
    st.subheader("🔍 Detailed Analysis")

    all_time = scope != "This session"
    ts_format = "%Y-%m-%d %H:%M" if all_time else "%H:%M:%S"

    # Activity timeline
    st.subheader("⏱️ Activity Timeline")

    learning_history = view.learning_history

    if learning_history:
        timeline_df = pd.DataFrame(
            [
                {
                    "Time": entry["timestamp"].strftime(ts_format),
                    "Activity": entry["type"].replace("_", " ").title(),
                    "Details": _format_activity_details(entry),
                }
                for entry in learning_history
            ]
        )
        st.dataframe(timeline_df, width="stretch")
    else:
        st.info("No activities recorded yet.")

    # Detailed quiz statistics
    detailed_results = view.quiz_analytics["detailed_results"]
    if detailed_results:
        st.subheader("📊 Detailed Quiz Statistics")

        with st.expander("📈 All Quiz Results"):
            for i, result in enumerate(detailed_results, 1):
                st.write(f"**Quiz {i}** - {result['timestamp'].strftime(ts_format)}")
                st.write(f"- Type: {result['quiz_type']}")
                st.write(f"- Difficulty: {result['difficulty']}")
                st.write(f"- Score: {result['overall_score']:.1f}%")
                st.write(f"- Questions: {len(result['questions'])}")
                st.write("---")

    # Export data section
    st.subheader("💾 Data Export")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📊 Export This Session"):
            export_data = {
                "session_info": {
                    "start_time": tracker.session_start_time.isoformat(),
                    "export_time": datetime.now().isoformat(),
                },
                "quiz_analytics": tracker.quiz_analytics,
                "materials_analytics": tracker.materials_analytics,
                "engagement_metrics": tracker.engagement_metrics,
            }

            # Convert datetime objects to strings for JSON serialization
            export_json = _convert_datetimes(export_data)

            st.download_button(
                label="📥 Download session JSON",
                data=json.dumps(export_json, indent=2),
                file_name=f"learning_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

    with col2:
        if store is not None and st.button("🗄️ Export All-Time Data"):
            st.download_button(
                label="📥 Download all-time JSON",
                data=json.dumps(store.export(), indent=2),
                file_name=f"learning_analytics_all_time_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )

    if st.button("📈 Generate Report"):
        _summary_report(tracker, view, scope)

    # Reset persisted data (with confirmation)
    if store is not None:
        st.markdown("---")
        st.subheader("🗑️ Reset Saved Data")
        st.caption(
            "Permanently deletes all persisted analytics (the 'All time' view). "
            "Your current session's live view stays until you refresh."
        )
        confirm = st.checkbox("I understand this permanently deletes my saved analytics.")
        if st.button("Delete all saved data", type="primary", disabled=not confirm):
            store.reset()
            st.success("✅ All saved analytics deleted.")


def _format_activity_details(entry: dict) -> str:
    """Format activity details for timeline display."""
    activity_type = entry["type"]
    data = entry["data"]

    if activity_type == "quiz_completion":
        return (
            f"Score: {data.get('score', 0):.1f}% | {data.get('type', 'Unknown')} | "
            f"{data.get('difficulty', 'Unknown')}"
        )
    elif activity_type == "materials_generation":
        return f"Type: {data.get('type', 'Unknown')} | Success: {data.get('success', False)}"
    else:
        return str(data)


def _convert_datetimes(obj):
    """Prepare data for JSON export by converting datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes(item) for item in obj]
    else:
        return obj


def _summary_report(tracker: AnalyticsTracker, view: AnalyticsView, scope: str) -> None:
    """Generate a comprehensive summary report for the selected scope."""
    label = "Session" if scope == "This session" else "All-Time"
    st.subheader(f"📋 Learning {label} Summary Report")

    quiz_analytics = view.quiz_analytics
    materials_analytics = view.materials_analytics

    # Overview
    st.write(f"**📊 {label} Overview:**")
    if scope == "This session":
        st.write(f"- Duration: {datetime.now() - tracker.session_start_time}")
    st.write(f"- Quizzes Completed: {quiz_analytics['total_quizzes']}")
    st.write(f"- Total Questions Answered: {quiz_analytics['total_questions']}")
    st.write(f"- Materials Generated: {materials_analytics['total_materials']}")

    # Performance summary
    performance = quiz_analytics["performance_over_time"]
    if performance:
        scores = [entry["score_percentage"] for entry in performance]
        st.write(f"- Average Score: {sum(scores) / len(scores):.1f}%")
        st.write(f"- Best Score: {max(scores):.1f}%")
        st.write(f"- Score Range: {max(scores) - min(scores):.1f}%")

    # Learning insights
    velocity_data = metrics.calculate_learning_velocity(performance)
    if velocity_data["trend"] != "insufficient_data":
        st.write(f"- Learning Trend: {velocity_data['trend'].title()}")
        st.write(f"- Improvement Rate: {velocity_data['velocity']:.2f}% per quiz")

    # Recommendations
    analysis = metrics.strength_weakness_analysis(quiz_analytics["detailed_results"])
    if analysis["recommendations"]:
        st.write("**💡 Key Recommendations:**")
        for rec in analysis["recommendations"][:3]:  # Top 3 recommendations
            st.write(f"- {rec}")
