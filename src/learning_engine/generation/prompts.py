"""All prompt text in one place — the single source for difficulty instructions.

Previously the difficulty instructions existed in three divergent copies
(app.py, settings.DIFFICULTY_CONFIG, open_ended_processor). generate_structured
appends the JSON schema and a "respond with only JSON" instruction, so these
prompts describe the task and answer conventions, not the JSON shape.

This module must not import Streamlit (architecture rule R1).
"""

from __future__ import annotations

from learning_engine.models import OpenEndedQuestion

# --------------------------------------------------------------------------- #
# Difficulty instructions (single source)
# --------------------------------------------------------------------------- #

QUIZ_DIFFICULTY_INSTRUCTIONS: dict[str, str] = {
    "Standard": """
        Create university-level questions that test comprehension, analysis, and
        application of the material. Questions should be straightforward but require
        good understanding. Focus on key concepts, definitions, and logical connections.
    """,
    "Advanced": """
        Create advanced questions that require synthesis, evaluation, and critical
        thinking. Include scenario-based questions and complex problem-solving, suitable
        for graduate-level study. Challenging but fair.
    """,
    "Extreme": """
        Create EXTREMELY challenging questions that require critical thinking, careful
        reading, and deep analysis. Make them tricky — use subtle distinctions, edge
        cases, and nuanced interpretations. Some questions may have multiple technically
        correct options where only ONE is the BEST/MOST COMPLETE answer; make incorrect
        options plausible and tempting. Beyond university level.
    """,
}

OPEN_ENDED_DIFFICULTY_INSTRUCTIONS: dict[str, str] = {
    "Standard": """
        Create university-level open-ended questions that test comprehension and analysis.
        Marking schemes should reward understanding, clarity, and correct terminology.
    """,
    "Advanced": """
        Create advanced open-ended questions requiring critical analysis and synthesis.
        Marking schemes should reward depth of analysis and sophisticated reasoning.
    """,
    "Extreme": """
        Create expert-level open-ended questions requiring deep critical thinking, complex
        scenarios, and nuanced analysis. Marking schemes should reward exceptional insight.
    """,
}


def _difficulty(instructions: dict[str, str], difficulty: str) -> str:
    return instructions.get(difficulty, instructions["Standard"])


# --------------------------------------------------------------------------- #
# Quiz prompts
# --------------------------------------------------------------------------- #

_MCQ_FORMAT = (
    "Each multiple-choice question has exactly 4 options formatted as "
    '"A) ...", "B) ...", "C) ...", "D) ..."; correct_answer is the letter only '
    '(one of A, B, C, D). Set type to "mcq".'
)
_TF_FORMAT = (
    'Each true/false question has options exactly ["True", "False"]; correct_answer '
    'is "True" or "False". Set type to "tf".'
)


def build_quiz_prompt(
    text: str,
    quiz_type: str,
    num_questions: int,
    difficulty: str,
    mcq_count: int = 0,
    tf_count: int = 0,
) -> str:
    diff = _difficulty(QUIZ_DIFFICULTY_INSTRUCTIONS, difficulty)
    if quiz_type == "Mixed (MCQ + T/F)":
        composition = (
            f"Generate exactly {num_questions} questions: {mcq_count} multiple-choice "
            f"and {tf_count} true/false. {_MCQ_FORMAT} {_TF_FORMAT}"
        )
    elif quiz_type == "True or False":
        composition = f"Generate exactly {num_questions} true/false questions. {_TF_FORMAT}"
    else:  # Multiple Choice
        composition = (
            f"Generate exactly {num_questions} multiple-choice questions. {_MCQ_FORMAT}"
        )
    return (
        f"{composition}\n\nDIFFICULTY LEVEL: {difficulty}\n{diff}\n"
        f"Include a brief explanation for each correct answer.\n\nContent:\n{text}"
    )


def build_open_ended_prompt(text: str, num_questions: int, difficulty: str) -> str:
    diff = _difficulty(OPEN_ENDED_DIFFICULTY_INSTRUCTIONS, difficulty)
    return (
        f"Generate exactly {num_questions} open-ended questions with detailed marking "
        f"schemes based on the content.\n\nDIFFICULTY LEVEL: {difficulty}\n{diff}\n"
        "For each question: write a clear question requiring a written response; assign "
        "total_marks (2-5); break the marking scheme into criteria, each with its marks "
        "and a list of keywords to look for; and provide a model_answer. Set type to "
        '"open_ended".\n\nContent:\n' + text
    )


def build_scoring_prompt(question: OpenEndedQuestion, user_answer: str) -> str:
    scheme = "\n".join(
        f"- {c.criterion} ({c.marks} marks); keywords: {', '.join(c.keywords)}"
        for c in question.marking_scheme
    )
    return (
        "You are an expert examiner. Score the student's answer against the marking "
        "scheme. Award partial marks fairly, accept synonyms and valid alternative "
        "phrasing, and deduct only for factual errors or missing key concepts.\n\n"
        f"QUESTION: {question.question}\nTOTAL MARKS: {question.total_marks}\n\n"
        f"MARKING SCHEME:\n{scheme}\n\nMODEL ANSWER (reference):\n{question.model_answer}\n\n"
        f"STUDENT'S ANSWER:\n{user_answer}\n\n"
        "For each criterion report marks_awarded and max_marks with brief feedback, then "
        "give total_score, max_score, percentage, overall_feedback, strengths, and "
        "improvements."
    )


def build_summarize_prompt(text: str) -> str:
    return f"Summarize the following text into clear key points:\n{text}"
