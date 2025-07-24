"""
Study Materials Generator
========================

This module generates various study materials including summaries, cheat sheets, and flashcards
from document content using AI providers.

Supported Materials:
- Comprehensive Summaries
- Quick Reference Cheat Sheets  
- Interactive Flashcards
- Study Outlines
- Key Terms & Definitions
"""

import json
import re
import logging
from typing import Dict, Any, Tuple
import streamlit as st
from datetime import datetime

logger = logging.getLogger(__name__)


class StudyMaterialsGenerator:
    """Generates various study materials from document content."""
    
    def __init__(self, client, use_google_ai=False, use_local_ai=False):
        """
        Initialize the study materials generator.
        
        Args:
            client: AI client (OpenAI-compatible interface)
            use_google_ai: Whether using Google AI provider
            use_local_ai: Whether using Local AI provider
        """
        self.client = client
        self.use_google_ai = use_google_ai
        self.use_local_ai = use_local_ai
    
    def _get_model_config(self) -> Tuple[str, float]:
        """Get appropriate model and temperature based on provider."""
        if self.use_local_ai:
            # Use selected model from session state if available
            model = getattr(st.session_state, 'selected_local_model', 'gemma2:2b')
            temperature = 0.3  # Lower temperature for more consistent study materials
        elif self.use_google_ai:
            model = "gemini-2.0-flash-exp"
            temperature = 0.3
        else:
            model = "gpt-3.5-turbo"
            temperature = 0.3
        
        return model, temperature
    
    def _make_api_call(self, prompt: str) -> str:
        """Make API call with error handling."""
        model, temperature = self._get_model_config()
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            raise Exception(f"Failed to generate content: {str(e)}")
    
    def generate_comprehensive_summary(self, text: str, summary_type: str = "detailed") -> Dict[str, Any]:
        """
        Generate a comprehensive summary of the document content.
        
        Args:
            text: Input text to summarize
            summary_type: Type of summary ("detailed", "concise", "bullet_points")
            
        Returns:
            Dict containing the summary and metadata
        """
        
        type_instructions = {
            "detailed": """
            Create a comprehensive, detailed summary that covers all major topics and subtopics.
            Include important details, examples, and explanations.
            Organize into clear sections with headings.
            Aim for 300-500 words depending on source length.
            """,
            "concise": """
            Create a concise summary focusing on the most essential points.
            Keep it brief but comprehensive, covering all main ideas.
            Use clear, direct language.
            Aim for 150-250 words.
            """,
            "bullet_points": """
            Create a well-organized bullet point summary.
            Use hierarchical bullet points (main points and sub-points).
            Each bullet should be a complete thought.
            Group related concepts together.
            """
        }
        
        instruction = type_instructions.get(summary_type, type_instructions["detailed"])
        
        prompt = f"""
        Please create a {summary_type} summary of the following content.
        
        {instruction}
        
        Format the response as JSON with this structure:
        {{
            "summary": "The main summary content",
            "key_points": ["point1", "point2", "point3", ...],
            "main_topics": ["topic1", "topic2", "topic3", ...],
            "word_count": number_of_words_in_summary,
            "summary_type": "{summary_type}"
        }}
        
        Content to summarize:
        {text}
        """
        
        try:
            response_content = self._make_api_call(prompt)
            
            # Try to parse JSON response
            try:
                summary_data = json.loads(response_content)
                return summary_data
            except json.JSONDecodeError:
                # Fallback: extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    summary_data = json.loads(json_match.group())
                    return summary_data
                else:
                    # Manual fallback
                    return {
                        "summary": response_content,
                        "key_points": [],
                        "main_topics": [],
                        "word_count": len(response_content.split()),
                        "summary_type": summary_type,
                        "error": "Could not parse structured response"
                    }
                    
        except Exception as e:
            return {"error": f"Failed to generate summary: {str(e)}"}
    
    def generate_cheat_sheet(self, text: str, format_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Generate a quick reference cheat sheet.
        
        Args:
            text: Input text to create cheat sheet from
            format_type: Type of cheat sheet ("comprehensive", "formulas", "definitions", "quick_ref")
            
        Returns:
            Dict containing the cheat sheet and metadata
        """
        
        format_instructions = {
            "comprehensive": """
            Create a comprehensive cheat sheet with:
            - Key concepts and definitions
            - Important formulas or principles
            - Step-by-step procedures
            - Quick reference tables
            - Memory aids and mnemonics
            """,
            "formulas": """
            Focus on formulas, equations, and mathematical relationships:
            - List all formulas with explanations
            - Include variable definitions
            - Show example calculations
            - Group related formulas together
            """,
            "definitions": """
            Focus on key terms and definitions:
            - Important terminology with clear definitions
            - Acronyms and abbreviations
            - Classifications and categories
            - Related concepts and connections
            """,
            "quick_ref": """
            Create a ultra-concise quick reference:
            - Most essential information only
            - Bullet points and short phrases
            - Easy to scan format
            - Critical facts and figures
            """
        }
        
        instruction = format_instructions.get(format_type, format_instructions["comprehensive"])
        
        prompt = f"""
        Create a study cheat sheet from the following content.
        
        {instruction}
        
        Format as a well-organized cheat sheet that students can use for quick reference.
        Use clear headings, bullet points, and structured layout.
        
        Return the response in JSON format:
        {{
            "title": "Cheat Sheet Title",
            "sections": [
                {{
                    "heading": "Section Name",
                    "content": "Section content with formatting",
                    "items": ["item1", "item2", "item3"]
                }}
            ],
            "key_terms": [
                {{
                    "term": "Term Name",
                    "definition": "Definition"
                }}
            ],
            "formulas": [
                {{
                    "name": "Formula Name", 
                    "formula": "Mathematical expression",
                    "explanation": "What it calculates"
                }}
            ],
            "quick_tips": ["tip1", "tip2", "tip3"],
            "format_type": "{format_type}"
        }}
        
        Content:
        {text}
        """
        
        try:
            response_content = self._make_api_call(prompt)
            
            # Try to parse JSON response
            try:
                cheat_sheet_data = json.loads(response_content)
                return cheat_sheet_data
            except json.JSONDecodeError:
                # Fallback: extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    cheat_sheet_data = json.loads(json_match.group())
                    return cheat_sheet_data
                else:
                    # Manual fallback
                    return {
                        "title": "Study Cheat Sheet",
                        "sections": [{"heading": "Content", "content": response_content, "items": []}],
                        "key_terms": [],
                        "formulas": [],
                        "quick_tips": [],
                        "format_type": format_type,
                        "error": "Could not parse structured response"
                    }
                    
        except Exception as e:
            return {"error": f"Failed to generate cheat sheet: {str(e)}"}
    
    def generate_flashcards(self, text: str, card_count: int = 10, difficulty: str = "mixed") -> Dict[str, Any]:
        """
        Generate interactive flashcards for active study.
        
        Args:
            text: Input text to create flashcards from
            card_count: Number of flashcards to generate
            difficulty: Difficulty level ("basic", "intermediate", "advanced", "mixed")
            
        Returns:
            Dict containing flashcard data
        """
        
        difficulty_instructions = {
            "basic": """
            Create basic flashcards focusing on:
            - Simple definitions and terminology
            - Basic facts and figures
            - Straightforward concepts
            - Direct question-answer pairs
            """,
            "intermediate": """
            Create intermediate flashcards with:
            - Concept explanations and applications
            - Cause-and-effect relationships
            - Comparison questions
            - Problem-solving scenarios
            """,
            "advanced": """
            Create advanced flashcards featuring:
            - Complex analysis and synthesis
            - Critical thinking questions
            - Multi-step problem solving
            - Advanced application scenarios
            """,
            "mixed": """
            Create a mix of difficulty levels:
            - 30% basic (definitions, facts)
            - 40% intermediate (concepts, applications) 
            - 30% advanced (analysis, synthesis)
            """
        }
        
        instruction = difficulty_instructions.get(difficulty, difficulty_instructions["mixed"])
        
        prompt = f"""
        Create exactly {card_count} study flashcards from the following content.
        
        {instruction}
        
        Each flashcard should have:
        - A clear, focused question on the front
        - A comprehensive answer on the back
        - Optional hints or memory aids
        
        Return as JSON:
        {{
            "flashcards": [
                {{
                    "id": 1,
                    "front": "Question or prompt",
                    "back": "Answer or explanation", 
                    "hint": "Optional hint",
                    "difficulty": "basic|intermediate|advanced",
                    "category": "Topic category"
                }}
            ],
            "total_cards": {card_count},
            "difficulty_distribution": {{
                "basic": number_of_basic_cards,
                "intermediate": number_of_intermediate_cards,
                "advanced": number_of_advanced_cards
            }},
            "categories": ["category1", "category2", ...],
            "study_tips": ["tip1", "tip2", "tip3"]
        }}
        
        Content:
        {text}
        """
        
        try:
            response_content = self._make_api_call(prompt)
            
            # Try to parse JSON response
            try:
                flashcard_data = json.loads(response_content)
                return flashcard_data
            except json.JSONDecodeError:
                # Fallback: extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    flashcard_data = json.loads(json_match.group())
                    return flashcard_data
                else:
                    # Manual fallback - create simple flashcards from response
                    return {
                        "flashcards": [
                            {
                                "id": 1,
                                "front": "Study the content",
                                "back": response_content[:500] + "..." if len(response_content) > 500 else response_content,
                                "hint": "",
                                "difficulty": "basic",
                                "category": "General"
                            }
                        ],
                        "total_cards": 1,
                        "difficulty_distribution": {"basic": 1, "intermediate": 0, "advanced": 0},
                        "categories": ["General"],
                        "study_tips": [],
                        "error": "Could not parse structured response"
                    }
                    
        except Exception as e:
            return {"error": f"Failed to generate flashcards: {str(e)}"}
    
    def generate_study_outline(self, text: str, outline_depth: str = "detailed") -> Dict[str, Any]:
        """
        Generate a structured study outline.
        
        Args:
            text: Input text to create outline from
            outline_depth: Depth level ("overview", "detailed", "comprehensive")
            
        Returns:
            Dict containing outline structure and metadata
        """
        
        depth_instructions = {
            "overview": """
            Create a high-level overview outline:
            - Main topics only (I, II, III...)
            - 1-2 levels of detail
            - Focus on big picture concepts
            """,
            "detailed": """
            Create a detailed outline:
            - Main topics and subtopics (I.A.1.a...)
            - 3-4 levels of detail
            - Include key examples and details
            """,
            "comprehensive": """
            Create a comprehensive outline:
            - Full hierarchical structure
            - 4-5 levels of detail
            - Include examples, formulas, and specifics
            - Cross-references and connections
            """
        }
        
        instruction = depth_instructions.get(outline_depth, depth_instructions["detailed"])
        
        prompt = f"""
        Create a structured study outline from the following content.
        
        {instruction}
        
        Use proper outline formatting with:
        - Roman numerals for main topics (I, II, III...)
        - Capital letters for subtopics (A, B, C...)
        - Numbers for details (1, 2, 3...)
        - Lowercase letters for specifics (a, b, c...)
        
        Return as JSON:
        {{
            "outline": [
                {{
                    "level": 1,
                    "marker": "I",
                    "text": "Main topic",
                    "children": [
                        {{
                            "level": 2,
                            "marker": "A",
                            "text": "Subtopic",
                            "children": []
                        }}
                    ]
                }}
            ],
            "total_sections": number_of_main_sections,
            "max_depth": maximum_nesting_level,
            "study_sequence": ["section1", "section2", ...],
            "time_estimates": {{
                "total_study_time": "X hours",
                "per_section": ["30 min", "45 min", ...]
            }},
            "outline_depth": "{outline_depth}"
        }}
        
        Content:
        {text}
        """
        
        try:
            response_content = self._make_api_call(prompt)
            
            # Try to parse JSON response
            try:
                outline_data = json.loads(response_content)
                return outline_data
            except json.JSONDecodeError:
                # Fallback: extract JSON from response or create simple structure
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    outline_data = json.loads(json_match.group())
                    return outline_data
                else:
                    # Manual fallback - create simple outline
                    return {
                        "outline": [
                            {
                                "level": 1,
                                "marker": "I",
                                "text": "Study Content",
                                "children": [
                                    {
                                        "level": 2,
                                        "marker": "A",
                                        "text": response_content[:200] + "..." if len(response_content) > 200 else response_content,
                                        "children": []
                                    }
                                ]
                            }
                        ],
                        "total_sections": 1,
                        "max_depth": 2,
                        "study_sequence": ["Content Review"],
                        "time_estimates": {
                            "total_study_time": "1-2 hours",
                            "per_section": ["1-2 hours"]
                        },
                        "outline_depth": outline_depth,
                        "error": "Could not parse structured response"
                    }
                    
        except Exception as e:
            return {"error": f"Failed to generate outline: {str(e)}"}
    
    def generate_key_terms(self, text: str, term_count: int = 15) -> Dict[str, Any]:
        """
        Extract and define key terms from the content.
        
        Args:
            text: Input text to extract terms from
            term_count: Number of key terms to extract
            
        Returns:
            Dict containing key terms and definitions
        """
        
        prompt = f"""
        Extract the {term_count} most important key terms and concepts from the following content.
        
        For each term, provide:
        - Clear, concise definition
        - Context of how it's used
        - Any related terms or synonyms
        
        Focus on terms that are:
        - Central to understanding the content
        - Technical or specialized vocabulary
        - Concepts that appear multiple times
        - Terms students would need to know for exams
        
        Return as JSON:
        {{
            "key_terms": [
                {{
                    "term": "Term name",
                    "definition": "Clear definition",
                    "context": "How it's used in the content",
                    "related_terms": ["term1", "term2"],
                    "importance": "high|medium|low"
                }}
            ],
            "total_terms": {term_count},
            "categories": [
                {{
                    "category": "Category name",
                    "terms": ["term1", "term2"]
                }}
            ],
            "study_suggestions": ["suggestion1", "suggestion2"]
        }}
        
        Content:
        {text}
        """
        
        try:
            response_content = self._make_api_call(prompt)
            
            # Try to parse JSON response
            try:
                terms_data = json.loads(response_content)
                return terms_data
            except json.JSONDecodeError:
                # Fallback: extract JSON from response
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    terms_data = json.loads(json_match.group())
                    return terms_data
                else:
                    # Manual fallback
                    return {
                        "key_terms": [
                            {
                                "term": "Key Concepts",
                                "definition": response_content[:300] + "..." if len(response_content) > 300 else response_content,
                                "context": "General content",
                                "related_terms": [],
                                "importance": "high"
                            }
                        ],
                        "total_terms": 1,
                        "categories": [{"category": "General", "terms": ["Key Concepts"]}],
                        "study_suggestions": ["Review the extracted content"],
                        "error": "Could not parse structured response"
                    }
                    
        except Exception as e:
            return {"error": f"Failed to generate key terms: {str(e)}"}
    
    def generate_study_guide(self, text: str, guide_type: str = "comprehensive") -> Dict[str, Any]:
        """
        Generate a complete study guide combining multiple study materials.
        
        Args:
            text: Input text to create study guide from
            guide_type: Type of guide ("comprehensive", "exam_prep", "quick_review")
            
        Returns:
            Dict containing complete study guide
        """
        
        # Generate different components based on guide type
        if guide_type == "comprehensive":
            summary = self.generate_comprehensive_summary(text, "detailed")
            cheat_sheet = self.generate_cheat_sheet(text, "comprehensive")
            flashcards = self.generate_flashcards(text, 15, "mixed")
            key_terms = self.generate_key_terms(text, 20)
            
        elif guide_type == "exam_prep":
            summary = self.generate_comprehensive_summary(text, "concise")
            cheat_sheet = self.generate_cheat_sheet(text, "quick_ref")
            flashcards = self.generate_flashcards(text, 20, "mixed")
            key_terms = self.generate_key_terms(text, 25)
            
        else:  # quick_review
            summary = self.generate_comprehensive_summary(text, "bullet_points")
            cheat_sheet = self.generate_cheat_sheet(text, "definitions")
            flashcards = self.generate_flashcards(text, 10, "basic")
            key_terms = self.generate_key_terms(text, 10)
        
        # Combine all components
        study_guide = {
            "title": f"Study Guide - {guide_type.title()}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "guide_type": guide_type,
            "components": {
                "summary": summary,
                "cheat_sheet": cheat_sheet,
                "flashcards": flashcards,
                "key_terms": key_terms
            },
            "study_plan": self._generate_study_plan(guide_type),
            "errors": []
        }
        
        # Collect any errors from components
        for component_name, component_data in study_guide["components"].items():
            if isinstance(component_data, dict) and "error" in component_data:
                study_guide["errors"].append(f"{component_name}: {component_data['error']}")
        
        return study_guide
    
    def _generate_study_plan(self, guide_type: str) -> Dict[str, Any]:
        """Generate a suggested study plan based on guide type."""
        
        plans = {
            "comprehensive": {
                "total_time": "4-6 hours",
                "sessions": [
                    {"session": 1, "focus": "Read summary and outline", "time": "45-60 min"},
                    {"session": 2, "focus": "Review cheat sheet and key terms", "time": "30-45 min"},
                    {"session": 3, "focus": "Practice with flashcards", "time": "45-60 min"},
                    {"session": 4, "focus": "Review and self-test", "time": "60-90 min"},
                    {"session": 5, "focus": "Final review before exam", "time": "30-45 min"}
                ]
            },
            "exam_prep": {
                "total_time": "6-8 hours",
                "sessions": [
                    {"session": 1, "focus": "Study outline thoroughly", "time": "90-120 min"},
                    {"session": 2, "focus": "Memorize key terms", "time": "45-60 min"},
                    {"session": 3, "focus": "Intensive flashcard practice", "time": "60-90 min"},
                    {"session": 4, "focus": "Use cheat sheet for quick review", "time": "30-45 min"},
                    {"session": 5, "focus": "Comprehensive review", "time": "60-90 min"},
                    {"session": 6, "focus": "Final preparation", "time": "30-45 min"}
                ]
            },
            "quick_review": {
                "total_time": "2-3 hours",
                "sessions": [
                    {"session": 1, "focus": "Read bullet point summary", "time": "30-45 min"},
                    {"session": 2, "focus": "Review key definitions", "time": "30-45 min"},
                    {"session": 3, "focus": "Practice basic flashcards", "time": "45-60 min"},
                    {"session": 4, "focus": "Final overview", "time": "30-45 min"}
                ]
            }
        }
        
        return plans.get(guide_type, plans["comprehensive"])
