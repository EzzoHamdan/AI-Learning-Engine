"""
Learning Analytics & Progress Tracking Module

This module provides comprehensive analytics and progress tracking capabilities
for the AI Learning Engine, analyzing data from the current session.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import json
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Any, Optional
import re

class LearningAnalytics:
    """Comprehensive learning analytics and progress tracking system."""
    
    def __init__(self):
        """Initialize the Learning Analytics system."""
        self.initialize_analytics_session_state()
    
    def initialize_analytics_session_state(self):
        """Initialize session state variables for analytics tracking."""
        
        # Session tracking
        if "session_start_time" not in st.session_state:
            st.session_state.session_start_time = datetime.now()
        
        # Learning history
        if "learning_history" not in st.session_state:
            st.session_state.learning_history = []
        
        # Quiz analytics
        if "quiz_analytics" not in st.session_state:
            st.session_state.quiz_analytics = {
                "total_quizzes": 0,
                "total_questions": 0,
                "total_correct": 0,
                "difficulty_breakdown": {"Standard": 0, "Advanced": 0, "Extreme": 0},
                "type_breakdown": {"Multiple Choice": 0, "True or False": 0, "Open-ended": 0, "Mixed": 0},
                "performance_over_time": [],
                "detailed_results": []
            }
        
        # Study materials analytics
        if "materials_analytics" not in st.session_state:
            st.session_state.materials_analytics = {
                "total_materials": 0,
                "material_types": {},
                "generation_times": [],
                "material_history": []
            }
        
        # Engagement metrics
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
                    "skipped_responses": 0
                }
            }
    
    def track_quiz_completion(self, quiz_data: Dict, user_answers: Dict, performance_stats: Dict):
        """Track quiz completion and update analytics."""
        
        completion_time = datetime.now()
        questions = quiz_data.get("questions", [])
        
        # Calculate basic metrics
        total_questions = len(questions)
        correct_count = performance_stats.get("traditional_correct", 0)
        overall_percentage = performance_stats.get("overall_percentage", 0)
        
        # Get quiz metadata
        difficulty = getattr(st.session_state, 'quiz_difficulty', 'Standard')
        quiz_type = getattr(st.session_state, 'quiz_type', 'Mixed')
        
        # Update quiz analytics
        st.session_state.quiz_analytics["total_quizzes"] += 1
        st.session_state.quiz_analytics["total_questions"] += total_questions
        st.session_state.quiz_analytics["total_correct"] += correct_count
        st.session_state.quiz_analytics["difficulty_breakdown"][difficulty] += 1
        
        # Map quiz types for analytics
        quiz_type_mapping = {
            "Multiple Choice": "Multiple Choice",
            "True or False": "True or False", 
            "Mixed (MCQ + T/F)": "Mixed",
            "Open-ended Questions": "Open-ended",
            "Complete Mix (All Types)": "Mixed"
        }
        mapped_type = quiz_type_mapping.get(quiz_type, "Mixed")
        st.session_state.quiz_analytics["type_breakdown"][mapped_type] += 1
        
        # Track performance over time
        performance_entry = {
            "timestamp": completion_time,
            "score_percentage": overall_percentage,
            "difficulty": difficulty,
            "quiz_type": quiz_type,
            "total_questions": total_questions,
            "correct_answers": correct_count
        }
        st.session_state.quiz_analytics["performance_over_time"].append(performance_entry)
        
        # Track detailed question results
        detailed_result = {
            "timestamp": completion_time,
            "quiz_id": len(st.session_state.quiz_analytics["detailed_results"]) + 1,
            "difficulty": difficulty,
            "quiz_type": quiz_type,
            "questions": [],
            "overall_score": overall_percentage
        }
        
        # Analyze each question
        for i, question in enumerate(questions):
            user_answer = user_answers.get(i, "")
            is_correct = False
            response_time = None  # Could be tracked in future
            
            if question.get('type') == 'open_ended':
                # For open-ended, we need to check the scoring result
                scoring_result = performance_stats.get('open_ended_scores', [])
                for scored_i, scored_q, result in scoring_result:
                    if scored_i == i:
                        is_correct = result.get('percentage', 0) >= 60  # Consider 60%+ as correct
                        break
            else:
                # For MCQ/T/F
                correct_answer = question['correct_answer']
                if len(question['options']) > 2:
                    user_letter = user_answer[0] if user_answer and user_answer[0] in ['A', 'B', 'C', 'D'] else ""
                else:
                    user_letter = user_answer
                is_correct = user_letter == correct_answer
            
            question_analysis = {
                "question_id": i + 1,
                "question_type": question.get('type', 'mcq_tf'),
                "correct": is_correct,
                "user_answer": user_answer,
                "correct_answer": question.get('correct_answer', ''),
                "response_time": response_time,
                "difficulty_tag": self._analyze_question_difficulty(question)
            }
            detailed_result["questions"].append(question_analysis)
        
        st.session_state.quiz_analytics["detailed_results"].append(detailed_result)
        
        # Add to learning history
        self.add_to_learning_history("quiz_completion", {
            "score": overall_percentage,
            "difficulty": difficulty,
            "type": quiz_type,
            "questions": total_questions
        })
    
    def track_materials_generation(self, material_type: str, generation_time: float, success: bool):
        """Track study materials generation."""
        
        timestamp = datetime.now()
        
        # Update materials analytics
        if success:
            st.session_state.materials_analytics["total_materials"] += 1
            
            if material_type not in st.session_state.materials_analytics["material_types"]:
                st.session_state.materials_analytics["material_types"][material_type] = 0
            st.session_state.materials_analytics["material_types"][material_type] += 1
        
        # Track generation times
        st.session_state.materials_analytics["generation_times"].append({
            "timestamp": timestamp,
            "material_type": material_type,
            "generation_time": generation_time,
            "success": success
        })
        
        # Add to materials history
        st.session_state.materials_analytics["material_history"].append({
            "timestamp": timestamp,
            "type": material_type,
            "success": success,
            "generation_time": generation_time
        })
        
        # Add to learning history
        self.add_to_learning_history("materials_generation", {
            "type": material_type,
            "success": success,
            "time": generation_time
        })
    
    def track_flashcard_interaction(self, action: str):
        """Track flashcard interactions."""
        
        valid_actions = ["correct", "incorrect", "skipped", "viewed"]
        if action not in valid_actions:
            return
        
        if action == "viewed":
            st.session_state.engagement_metrics["flashcard_interactions"]["cards_viewed"] += 1
        elif action == "correct":
            st.session_state.engagement_metrics["flashcard_interactions"]["correct_responses"] += 1
        elif action == "incorrect":
            st.session_state.engagement_metrics["flashcard_interactions"]["incorrect_responses"] += 1
        elif action == "skipped":
            st.session_state.engagement_metrics["flashcard_interactions"]["skipped_responses"] += 1
        
        # Update feature usage
        if "flashcards" not in st.session_state.engagement_metrics["feature_usage"]:
            st.session_state.engagement_metrics["feature_usage"]["flashcards"] = 0
        st.session_state.engagement_metrics["feature_usage"]["flashcards"] += 1
    
    def track_feature_usage(self, feature: str):
        """Track usage of different app features."""
        
        if "feature_usage" not in st.session_state.engagement_metrics:
            st.session_state.engagement_metrics["feature_usage"] = {}
        
        if feature not in st.session_state.engagement_metrics["feature_usage"]:
            st.session_state.engagement_metrics["feature_usage"][feature] = 0
        
        st.session_state.engagement_metrics["feature_usage"][feature] += 1
    
    def track_ai_provider_usage(self, provider: str):
        """Track AI provider usage."""
        
        if "ai_provider_usage" not in st.session_state.engagement_metrics:
            st.session_state.engagement_metrics["ai_provider_usage"] = {}
        
        if provider not in st.session_state.engagement_metrics["ai_provider_usage"]:
            st.session_state.engagement_metrics["ai_provider_usage"][provider] = 0
        
        st.session_state.engagement_metrics["ai_provider_usage"][provider] += 1
    
    def add_to_learning_history(self, activity_type: str, data: Dict):
        """Add an activity to the learning history."""
        
        entry = {
            "timestamp": datetime.now(),
            "type": activity_type,
            "data": data
        }
        st.session_state.learning_history.append(entry)
    
    def _analyze_question_difficulty(self, question: Dict) -> str:
        """Analyze question difficulty based on content."""
        
        question_text = question.get('question', '').lower()
        
        # Simple heuristics for difficulty analysis
        if any(word in question_text for word in ['analyze', 'evaluate', 'compare', 'synthesize', 'critique']):
            return "high"
        elif any(word in question_text for word in ['explain', 'describe', 'discuss', 'apply']):
            return "medium"
        else:
            return "basic"
    
    def calculate_learning_velocity(self) -> Dict:
        """Calculate learning velocity and trend metrics."""
        
        quiz_history = st.session_state.quiz_analytics["performance_over_time"]
        if len(quiz_history) < 2:
            return {"trend": "insufficient_data", "velocity": 0, "acceleration": 0}
        
        # Sort by timestamp
        sorted_history = sorted(quiz_history, key=lambda x: x["timestamp"])
        
        # Calculate score trend
        scores = [entry["score_percentage"] for entry in sorted_history]
        
        if len(scores) >= 2:
            # Simple linear trend
            x = np.arange(len(scores))
            z = np.polyfit(x, scores, 1)
            velocity = z[0]  # Slope represents learning velocity
            
            if len(scores) >= 3:
                # Calculate acceleration (change in velocity)
                recent_scores = scores[-3:]
                early_scores = scores[:3] if len(scores) >= 6 else scores[:len(scores)//2]
                
                if len(early_scores) >= 2 and len(recent_scores) >= 2:
                    early_trend = np.polyfit(range(len(early_scores)), early_scores, 1)[0]
                    recent_trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
                    acceleration = recent_trend - early_trend
                else:
                    acceleration = 0
            else:
                acceleration = 0
            
            # Determine trend
            if velocity > 1:
                trend = "improving"
            elif velocity < -1:
                trend = "declining"
            else:
                trend = "stable"
            
            return {
                "trend": trend,
                "velocity": velocity,
                "acceleration": acceleration,
                "confidence": min(len(scores) / 5, 1.0)  # Confidence increases with more data
            }
        
        return {"trend": "insufficient_data", "velocity": 0, "acceleration": 0}
    
    def get_strength_weakness_analysis(self) -> Dict:
        """Analyze strengths and weaknesses based on quiz performance."""
        
        detailed_results = st.session_state.quiz_analytics["detailed_results"]
        if not detailed_results:
            return {"strengths": [], "weaknesses": [], "recommendations": []}
        
        # Analyze by question type
        type_performance = {}
        difficulty_performance = {}
        
        for result in detailed_results:
            for question in result["questions"]:
                q_type = question["question_type"]
                difficulty = question["difficulty_tag"]
                is_correct = question["correct"]
                
                # Track by type
                if q_type not in type_performance:
                    type_performance[q_type] = {"correct": 0, "total": 0}
                type_performance[q_type]["total"] += 1
                if is_correct:
                    type_performance[q_type]["correct"] += 1
                
                # Track by difficulty
                if difficulty not in difficulty_performance:
                    difficulty_performance[difficulty] = {"correct": 0, "total": 0}
                difficulty_performance[difficulty]["total"] += 1
                if is_correct:
                    difficulty_performance[difficulty]["correct"] += 1
        
        # Calculate performance percentages
        type_percentages = {}
        for q_type, stats in type_performance.items():
            type_percentages[q_type] = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        difficulty_percentages = {}
        for difficulty, stats in difficulty_performance.items():
            difficulty_percentages[difficulty] = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        
        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []
        recommendations = []
        
        # Type-based analysis
        for q_type, percentage in type_percentages.items():
            if percentage >= 80:
                strengths.append(f"Strong performance in {q_type} questions ({percentage:.1f}%)")
            elif percentage < 60:
                weaknesses.append(f"Needs improvement in {q_type} questions ({percentage:.1f}%)")
                recommendations.append(f"Practice more {q_type} questions to improve understanding")
        
        # Difficulty-based analysis
        for difficulty, percentage in difficulty_percentages.items():
            if percentage >= 80:
                strengths.append(f"Excellent handling of {difficulty} difficulty questions ({percentage:.1f}%)")
            elif percentage < 60:
                weaknesses.append(f"Struggles with {difficulty} difficulty questions ({percentage:.1f}%)")
                recommendations.append(f"Focus on building foundational knowledge for {difficulty} concepts")
        
        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "type_performance": type_percentages,
            "difficulty_performance": difficulty_percentages
        }
    
    def display_analytics_dashboard(self):
        """Display the main analytics dashboard."""
        
        st.title("📊 Learning Analytics & Progress Tracking")
        st.markdown("---")
        
        # Session overview
        self.display_session_overview()
        
        # Main analytics tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Performance Analytics", 
            "🎯 Quiz Insights", 
            "📚 Study Materials", 
            "🚀 Progress Tracking",
            "🔍 Detailed Analysis"
        ])
        
        with tab1:
            self.display_performance_analytics()
        
        with tab2:
            self.display_quiz_insights()
        
        with tab3:
            self.display_materials_analytics()
        
        with tab4:
            self.display_progress_tracking()
        
        with tab5:
            self.display_detailed_analysis()
    
    def display_session_overview(self):
        """Display current session overview."""
        
        session_duration = datetime.now() - st.session_state.session_start_time
        hours, remainder = divmod(session_duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Session Duration",
                f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}",
                help="Total time spent in current session"
            )
        
        with col2:
            total_quizzes = st.session_state.quiz_analytics["total_quizzes"]
            st.metric(
                "Quizzes Completed",
                total_quizzes,
                help="Number of quizzes completed this session"
            )
        
        with col3:
            total_materials = st.session_state.materials_analytics["total_materials"]
            st.metric(
                "Materials Generated",
                total_materials,
                help="Study materials created this session"
            )
        
        with col4:
            avg_score = 0
            if st.session_state.quiz_analytics["performance_over_time"]:
                scores = [entry["score_percentage"] for entry in st.session_state.quiz_analytics["performance_over_time"]]
                avg_score = sum(scores) / len(scores)
            
            st.metric(
                "Average Score",
                f"{avg_score:.1f}%",
                help="Average quiz performance this session"
            )
    
    def display_performance_analytics(self):
        """Display performance analytics charts and metrics."""
        
        st.subheader("📈 Performance Analytics")
        
        quiz_analytics = st.session_state.quiz_analytics
        performance_data = quiz_analytics["performance_over_time"]
        
        if not performance_data:
            st.info("📝 Complete some quizzes to see performance analytics!")
            return
        
        # Performance over time chart
        df_performance = pd.DataFrame(performance_data)
        df_performance['quiz_number'] = range(1, len(df_performance) + 1)
        
        fig_performance = px.line(
            df_performance, 
            x='quiz_number', 
            y='score_percentage',
            title='📊 Quiz Performance Over Time',
            labels={'quiz_number': 'Quiz Number', 'score_percentage': 'Score (%)'},
            markers=True
        )
        
        fig_performance.add_hline(
            y=70, 
            line_dash="dash", 
            line_color="green", 
            annotation_text="Target: 70%"
        )
        
        fig_performance.update_layout(
            xaxis_title="Quiz Number",
            yaxis_title="Score Percentage (%)",
            showlegend=True
        )
        
        st.plotly_chart(fig_performance, use_container_width=True)
        
        # Performance by difficulty
        col1, col2 = st.columns(2)
        
        with col1:
            difficulty_data = quiz_analytics["difficulty_breakdown"]
            if any(difficulty_data.values()):
                fig_difficulty = px.pie(
                    values=list(difficulty_data.values()),
                    names=list(difficulty_data.keys()),
                    title="🎯 Quiz Difficulty Distribution"
                )
                st.plotly_chart(fig_difficulty, use_container_width=True)
        
        with col2:
            type_data = quiz_analytics["type_breakdown"]
            if any(type_data.values()):
                fig_types = px.pie(
                    values=list(type_data.values()),
                    names=list(type_data.keys()),
                    title="📝 Quiz Type Distribution"
                )
                st.plotly_chart(fig_types, use_container_width=True)
        
        # Learning velocity analysis
        velocity_data = self.calculate_learning_velocity()
        
        if velocity_data["trend"] != "insufficient_data":
            st.subheader("🚀 Learning Velocity Analysis")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}
                st.metric(
                    "Learning Trend",
                    f"{trend_emoji.get(velocity_data['trend'], '➡️')} {velocity_data['trend'].title()}",
                    help="Overall learning trend based on quiz performance"
                )
            
            with col2:
                st.metric(
                    "Velocity",
                    f"{velocity_data['velocity']:.2f}%/quiz",
                    help="Rate of improvement per quiz"
                )
            
            with col3:
                confidence = velocity_data.get('confidence', 0) * 100
                st.metric(
                    "Confidence",
                    f"{confidence:.0f}%",
                    help="Statistical confidence in the trend analysis"
                )
    
    def display_quiz_insights(self):
        """Display detailed quiz insights and patterns."""
        
        st.subheader("🎯 Quiz Insights & Patterns")
        
        detailed_results = st.session_state.quiz_analytics["detailed_results"]
        
        if not detailed_results:
            st.info("📝 Complete some quizzes to see detailed insights!")
            return
        
        # Strength and weakness analysis
        analysis = self.get_strength_weakness_analysis()
        
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
        
        # Performance breakdown charts
        if analysis["type_performance"]:
            st.subheader("📊 Performance by Question Type")
            
            type_df = pd.DataFrame([
                {"Type": k, "Performance": v} 
                for k, v in analysis["type_performance"].items()
            ])
            
            fig_type_performance = px.bar(
                type_df,
                x="Type",
                y="Performance",
                title="Performance by Question Type",
                color="Performance",
                color_continuous_scale="RdYlGn"
            )
            
            fig_type_performance.add_hline(
                y=70,
                line_dash="dash",
                annotation_text="Target: 70%"
            )
            
            st.plotly_chart(fig_type_performance, use_container_width=True)
        
        # Recent quiz analysis
        if detailed_results:
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
    
    def display_materials_analytics(self):
        """Display study materials analytics."""
        
        st.subheader("📚 Study Materials Analytics")
        
        materials_analytics = st.session_state.materials_analytics
        
        if materials_analytics["total_materials"] == 0:
            st.info("📚 Generate some study materials to see analytics!")
            return
        
        # Materials overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Materials", materials_analytics["total_materials"])
        
        with col2:
            material_types = len(materials_analytics["material_types"])
            st.metric("Unique Types", material_types)
        
        with col3:
            generation_times = materials_analytics["generation_times"]
            if generation_times:
                avg_time = sum(gt["generation_time"] for gt in generation_times if gt["success"]) / len([gt for gt in generation_times if gt["success"]])
                st.metric("Avg Generation Time", f"{avg_time:.1f}s")
        
        # Materials distribution
        if materials_analytics["material_types"]:
            fig_materials = px.bar(
                x=list(materials_analytics["material_types"].keys()),
                y=list(materials_analytics["material_types"].values()),
                title="📊 Generated Materials by Type",
                labels={'x': 'Material Type', 'y': 'Count'}
            )
            st.plotly_chart(fig_materials, use_container_width=True)
        
        # Generation success rate
        if generation_times:
            success_rate = sum(1 for gt in generation_times if gt["success"]) / len(generation_times) * 100
            st.metric("Generation Success Rate", f"{success_rate:.1f}%")
            
            # Generation time trend
            df_generation = pd.DataFrame(generation_times)
            df_generation['attempt_number'] = range(1, len(df_generation) + 1)
            
            fig_generation_time = px.scatter(
                df_generation,
                x='attempt_number',
                y='generation_time',
                color='success',
                title="📈 Material Generation Time Trend",
                labels={'attempt_number': 'Attempt Number', 'generation_time': 'Time (seconds)'}
            )
            
            st.plotly_chart(fig_generation_time, use_container_width=True)
    
    def display_progress_tracking(self):
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
                help="Set your target average quiz score"
            )
        
        with col2:
            target_quizzes = st.slider(
                "Quiz Goal (per session)",
                min_value=1,
                max_value=20,
                value=5,
                help="Set your target number of quizzes per session"
            )
        
        # Progress towards goals
        quiz_analytics = st.session_state.quiz_analytics
        current_avg = 0
        if quiz_analytics["performance_over_time"]:
            scores = [entry["score_percentage"] for entry in quiz_analytics["performance_over_time"]]
            current_avg = sum(scores) / len(scores)
        
        current_quizzes = quiz_analytics["total_quizzes"]
        
        col1, col2 = st.columns(2)
        
        with col1:
            score_progress = min(current_avg / target_score * 100, 100)
            st.metric(
                "Score Goal Progress",
                f"{current_avg:.1f}% / {target_score}%",
                delta=f"{score_progress:.1f}% complete"
            )
            
            # Score progress bar
            score_bar_color = "green" if score_progress >= 100 else "orange" if score_progress >= 70 else "red"
            st.progress(score_progress / 100)
        
        with col2:
            quiz_progress = min(current_quizzes / target_quizzes * 100, 100)
            st.metric(
                "Quiz Goal Progress",
                f"{current_quizzes} / {target_quizzes}",
                delta=f"{quiz_progress:.1f}% complete"
            )
            
            # Quiz progress bar
            st.progress(quiz_progress / 100)
        
        # Learning streaks
        st.subheader("🔥 Learning Streaks")
        
        learning_history = st.session_state.learning_history
        if learning_history:
            # Calculate current streak
            today = datetime.now().date()
            unique_days = set()
            
            for entry in learning_history:
                entry_date = entry["timestamp"].date()
                unique_days.add(entry_date)
            
            # Sort dates and calculate streak
            sorted_dates = sorted(unique_days, reverse=True)
            current_streak = 0
            
            for i, date in enumerate(sorted_dates):
                expected_date = today - timedelta(days=i)
                if date == expected_date:
                    current_streak += 1
                else:
                    break
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Current Streak", f"{current_streak} days")
            
            with col2:
                st.metric("Total Active Days", len(unique_days))
            
            with col3:
                # Calculate longest streak
                longest_streak = self._calculate_longest_streak(sorted_dates)
                st.metric("Longest Streak", f"{longest_streak} days")
        
        # Engagement metrics
        st.subheader("📊 Engagement Metrics")
        
        engagement = st.session_state.engagement_metrics
        
        if engagement["feature_usage"]:
            fig_engagement = px.bar(
                x=list(engagement["feature_usage"].keys()),
                y=list(engagement["feature_usage"].values()),
                title="🎯 Feature Usage Distribution",
                labels={'x': 'Feature', 'y': 'Usage Count'}
            )
            st.plotly_chart(fig_engagement, use_container_width=True)
        
        # AI Provider usage
        if engagement["ai_provider_usage"]:
            fig_providers = px.pie(
                values=list(engagement["ai_provider_usage"].values()),
                names=list(engagement["ai_provider_usage"].keys()),
                title="🤖 AI Provider Usage Distribution"
            )
            st.plotly_chart(fig_providers, use_container_width=True)
    
    def display_detailed_analysis(self):
        """Display detailed analysis and insights."""
        
        st.subheader("🔍 Detailed Analysis")
        
        # Session timeline
        st.subheader("⏱️ Session Timeline")
        
        learning_history = st.session_state.learning_history
        
        if learning_history:
            timeline_df = pd.DataFrame([
                {
                    "Time": entry["timestamp"].strftime("%H:%M:%S"),
                    "Activity": entry["type"].replace("_", " ").title(),
                    "Details": self._format_activity_details(entry)
                }
                for entry in learning_history
            ])
            
            st.dataframe(timeline_df, use_container_width=True)
        else:
            st.info("No activities recorded yet in this session.")
        
        # Detailed quiz statistics
        if st.session_state.quiz_analytics["detailed_results"]:
            st.subheader("📊 Detailed Quiz Statistics")
            
            with st.expander("📈 All Quiz Results"):
                for i, result in enumerate(st.session_state.quiz_analytics["detailed_results"], 1):
                    st.write(f"**Quiz {i}** - {result['timestamp'].strftime('%H:%M:%S')}")
                    st.write(f"- Type: {result['quiz_type']}")
                    st.write(f"- Difficulty: {result['difficulty']}")
                    st.write(f"- Score: {result['overall_score']:.1f}%")
                    st.write(f"- Questions: {len(result['questions'])}")
                    st.write("---")
        
        # Export data section
        st.subheader("💾 Data Export")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 Export Quiz Data"):
                export_data = {
                    "session_info": {
                        "start_time": st.session_state.session_start_time.isoformat(),
                        "export_time": datetime.now().isoformat()
                    },
                    "quiz_analytics": st.session_state.quiz_analytics,
                    "materials_analytics": st.session_state.materials_analytics,
                    "engagement_metrics": st.session_state.engagement_metrics
                }
                
                # Convert datetime objects to strings for JSON serialization
                export_json = self._prepare_export_data(export_data)
                
                st.download_button(
                    label="📥 Download JSON",
                    data=json.dumps(export_json, indent=2),
                    file_name=f"learning_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        with col2:
            if st.button("📈 Generate Report"):
                self._generate_summary_report()
    
    def _calculate_longest_streak(self, sorted_dates: List) -> int:
        """Calculate the longest learning streak."""
        
        if not sorted_dates:
            return 0
        
        longest = 1
        current = 1
        
        for i in range(1, len(sorted_dates)):
            # Check if dates are consecutive
            if (sorted_dates[i-1] - sorted_dates[i]).days == 1:
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        
        return longest
    
    def _format_activity_details(self, entry: Dict) -> str:
        """Format activity details for timeline display."""
        
        activity_type = entry["type"]
        data = entry["data"]
        
        if activity_type == "quiz_completion":
            return f"Score: {data.get('score', 0):.1f}% | {data.get('type', 'Unknown')} | {data.get('difficulty', 'Unknown')}"
        elif activity_type == "materials_generation":
            return f"Type: {data.get('type', 'Unknown')} | Success: {data.get('success', False)}"
        else:
            return str(data)
    
    def _prepare_export_data(self, data: Dict) -> Dict:
        """Prepare data for JSON export by converting datetime objects."""
        
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            else:
                return obj
        
        return convert_datetime(data)
    
    def _generate_summary_report(self):
        """Generate a comprehensive summary report."""
        
        st.subheader("📋 Learning Session Summary Report")
        
        session_duration = datetime.now() - st.session_state.session_start_time
        quiz_analytics = st.session_state.quiz_analytics
        materials_analytics = st.session_state.materials_analytics
        
        # Session overview
        st.write("**📊 Session Overview:**")
        st.write(f"- Duration: {session_duration}")
        st.write(f"- Quizzes Completed: {quiz_analytics['total_quizzes']}")
        st.write(f"- Total Questions Answered: {quiz_analytics['total_questions']}")
        st.write(f"- Materials Generated: {materials_analytics['total_materials']}")
        
        # Performance summary
        if quiz_analytics["performance_over_time"]:
            scores = [entry["score_percentage"] for entry in quiz_analytics["performance_over_time"]]
            st.write(f"- Average Score: {sum(scores)/len(scores):.1f}%")
            st.write(f"- Best Score: {max(scores):.1f}%")
            st.write(f"- Score Range: {max(scores) - min(scores):.1f}%")
        
        # Learning insights
        velocity_data = self.calculate_learning_velocity()
        if velocity_data["trend"] != "insufficient_data":
            st.write(f"- Learning Trend: {velocity_data['trend'].title()}")
            st.write(f"- Improvement Rate: {velocity_data['velocity']:.2f}% per quiz")
        
        # Recommendations
        analysis = self.get_strength_weakness_analysis()
        if analysis["recommendations"]:
            st.write("**💡 Key Recommendations:**")
            for rec in analysis["recommendations"][:3]:  # Top 3 recommendations
                st.write(f"- {rec}")


# Global analytics instance
if "analytics_instance" not in st.session_state:
    st.session_state.analytics_instance = LearningAnalytics()

analytics = st.session_state.analytics_instance
