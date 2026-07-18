"""Open-ended question generation and scoring functionality."""

import json
import re
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from learning_engine.llm.providers import ProviderConfig

# Load environment variables
load_dotenv()

# Temperatures/limits kept per call type (Phase 7 moves these into settings).
GENERATION_TEMPERATURE = 0.7
GENERATION_MAX_TOKENS = 2000
SCORING_TEMPERATURE = 0.3
SCORING_MAX_TOKENS = 500


class OpenEndedQuestionProcessor:
    """Handles generation and scoring of open-ended questions."""

    def __init__(self, ai_client, cfg: ProviderConfig):
        self.client = ai_client
        self.cfg = cfg

    def generate_open_ended_questions(
        self, text: str, num_questions: int = 3, difficulty: str = "Standard"
    ) -> dict[str, Any]:
        """
        Generate open-ended questions with marking schemes.

        Args:
            text: Source text to generate questions from
            num_questions: Number of questions to generate
            difficulty: Difficulty level

        Returns:
            Dictionary containing questions with marking schemes
        """

        difficulty_instructions = {
            "Standard": """
            Create university-level open-ended questions that test comprehension and analysis.
            Questions should require explanation of concepts, relationships, and applications.
            Marking schemes should reward understanding, clarity, and correct use of terminology.
            """,
            "Advanced": """
            Create advanced open-ended questions requiring critical analysis and synthesis.
            Questions should involve evaluation, comparison, and complex problem-solving.
            Marking schemes should reward depth of analysis, original thinking, and sophisticated reasoning.
            """,
            "Extreme": """
            Create expert-level open-ended questions requiring deep critical thinking.
            Questions should involve complex scenarios, edge cases, and nuanced analysis.
            Marking schemes should reward exceptional insight, comprehensive understanding, and advanced reasoning.
            """,
        }

        prompt = f"""
Based on the following content, generate exactly {num_questions} open-ended questions with detailed marking schemes.

DIFFICULTY LEVEL: {difficulty}
{difficulty_instructions[difficulty]}

For each question:
1. Create a clear, specific question that requires a written response
2. Assign appropriate total marks (2-5 marks per question)
3. Break down the marking scheme into specific criteria with point allocations
4. Provide a model answer that demonstrates the expected response

Return the response in this exact JSON format:
{{
  "questions": [
    {{
      "question": "Question text here",
      "total_marks": 4,
      "marking_scheme": [
        {{
          "criterion": "Define water as H2O compound",
          "marks": 1,
          "keywords": ["H2O", "hydrogen", "oxygen", "compound", "molecule"]
        }},
        {{
          "criterion": "Explain physical properties",
          "marks": 1,
          "keywords": ["liquid", "room temperature", "boiling point", "freezing point"]
        }},
        {{
          "criterion": "Describe biological importance",
          "marks": 2,
          "keywords": ["life", "essential", "cellular", "metabolism", "survival"]
        }}
      ],
      "model_answer": "Water is a chemical compound composed of two hydrogen atoms and one oxygen atom (H2O). At room temperature, it exists as a liquid with a boiling point of 100°C. Water is essential for all life forms as it facilitates cellular processes and metabolic reactions.",
      "type": "open_ended"
    }}
  ]
}}

Content: {text}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.cfg.chat_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=GENERATION_TEMPERATURE,
                max_tokens=GENERATION_MAX_TOKENS,
            )

            # Parse JSON response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON from the response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                quiz_data = json.loads(json_match.group())
                return quiz_data
            else:
                return {"error": "Failed to parse quiz data from response"}

        except json.JSONDecodeError as e:
            return {"error": f"JSON parsing failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Question generation failed: {str(e)}"}

    def score_open_ended_answer(
        self, question_data: dict[str, Any], user_answer: str
    ) -> dict[str, Any]:
        """
        Score a user's open-ended answer using AI evaluation.

        Args:
            question_data: Question data including marking scheme
            user_answer: User's written response

        Returns:
            Scoring results with detailed feedback
        """

        if not user_answer.strip():
            return {
                "total_score": 0,
                "max_score": question_data["total_marks"],
                "percentage": 0,
                "feedback": "No answer provided.",
                "criterion_scores": [],
            }

        # Build the scoring prompt
        marking_scheme_text = "\n".join(
            [
                f"- {criterion['criterion']} ({criterion['marks']} marks): "
                f"Look for keywords: {', '.join(criterion['keywords'])}"
                for criterion in question_data["marking_scheme"]
            ]
        )

        prompt = f"""
You are an expert examiner scoring an open-ended question. Score the student's answer based on the detailed marking scheme provided.

QUESTION: {question_data["question"]}
TOTAL MARKS: {question_data["total_marks"]}

MARKING SCHEME:
{marking_scheme_text}

MODEL ANSWER (for reference):
{question_data["model_answer"]}

STUDENT'S ANSWER:
{user_answer}

SCORING INSTRUCTIONS:
1. Award marks for each criterion based on how well the student's answer addresses it
2. Be fair but thorough - partial marks are encouraged
3. Consider synonyms and alternative valid explanations
4. Reward clear understanding even if wording differs from model answer
5. Deduct marks only for factual errors or missing key concepts

Return your evaluation in this exact JSON format:
{{
  "criterion_scores": [
    {{
      "criterion": "Define water as H2O compound",
      "marks_awarded": 1,
      "max_marks": 1,
      "feedback": "Correctly identified water as H2O compound"
    }},
    {{
      "criterion": "Explain physical properties", 
      "marks_awarded": 0.5,
      "max_marks": 1,
      "feedback": "Mentioned it's liquid but missed temperature details"
    }}
  ],
  "total_score": 3.5,
  "max_score": 4,
  "percentage": 87.5,
  "overall_feedback": "Good understanding demonstrated. Consider including more specific details about physical properties.",
  "strengths": ["Clear definition", "Good biological context"],
  "improvements": ["Add more specific physical property details", "Use more scientific terminology"]
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.cfg.scoring_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=SCORING_TEMPERATURE,
                max_tokens=SCORING_MAX_TOKENS,
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                scoring_result = json.loads(json_match.group())
                return scoring_result
            else:
                # Fallback scoring if JSON parsing fails
                return self._fallback_scoring(question_data, user_answer)

        except Exception as e:
            st.error(f"Scoring failed: {str(e)}")
            return self._fallback_scoring(question_data, user_answer)

    def _fallback_scoring(self, question_data: dict[str, Any], user_answer: str) -> dict[str, Any]:
        """Provide basic fallback scoring when AI scoring fails."""
        total_marks = question_data["total_marks"]
        word_count = len(user_answer.split())

        # Basic heuristic scoring based on answer length and keyword presence
        base_score = min(1.0, word_count / 50)  # Basic participation score

        # Check for keywords
        keyword_score = 0
        total_keywords = 0
        for criterion in question_data["marking_scheme"]:
            criterion_keywords = criterion["keywords"]
            total_keywords += len(criterion_keywords)
            found_keywords = sum(
                1 for keyword in criterion_keywords if keyword.lower() in user_answer.lower()
            )
            keyword_score += found_keywords

        keyword_ratio = keyword_score / max(total_keywords, 1)
        final_score = (base_score * 0.3 + keyword_ratio * 0.7) * total_marks

        return {
            "total_score": round(final_score, 1),
            "max_score": total_marks,
            "percentage": round((final_score / total_marks) * 100, 1),
            "overall_feedback": "Answer evaluated using basic scoring. AI detailed scoring unavailable.",
            "criterion_scores": [],
            "strengths": ["Answer provided"],
            "improvements": ["Consider adding more specific details"],
        }

    def generate_mixed_quiz(
        self,
        text: str,
        mcq_count: int = 3,
        tf_count: int = 2,
        open_ended_count: int = 2,
        difficulty: str = "Standard",
    ) -> dict[str, Any]:
        """Generate a mixed quiz with MCQ, T/F, and open-ended questions."""

        # Generate different question types
        from app import generate_quiz  # Import from main app

        try:
            # Generate MCQ and T/F questions
            traditional_quiz = generate_quiz(
                text, "Mixed (MCQ + T/F)", mcq_count + tf_count, difficulty
            )

            # Generate open-ended questions
            open_ended_quiz = self.generate_open_ended_questions(text, open_ended_count, difficulty)

            if "error" in traditional_quiz or "error" in open_ended_quiz:
                return {"error": "Failed to generate mixed quiz"}

            # Combine all questions
            all_questions = traditional_quiz["questions"] + open_ended_quiz["questions"]

            return {"questions": all_questions}

        except Exception as e:
            return {"error": f"Mixed quiz generation failed: {str(e)}"}
