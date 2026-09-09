"""Tests for response validation utilities.

Tests ensure AI responses are properly validated and fall back gracefully
when validation fails.
"""

import pytest

from app.services.local_analysis import analyze_resume_job
from app.services.response_validator import (
    validate_analysis_response,
    validate_interview_evaluation_response,
    validate_interview_questions_response,
)


class TestAnalysisResponseValidation:
    """Tests for resume/job analysis response validation."""

    def test_validates_correct_response_structure(self) -> None:
        """Valid response with all required fields passes validation."""
        response = {
            "match_percentage": 75.5,
            "matching_skills": ["python", "sql"],
            "missing_skills": ["docker", "kubernetes"],
            "missing_keywords": ["containerization"],
            "relevant_experience_keywords": ["backend"],
            "recommended_skills": ["docker", "kubernetes"],
            "resume_improvement_suggestions": ["Add Docker experience"],
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert result["match_percentage"] == 75.5
        assert result["matching_skills"] == ["python", "sql"]
        assert result["missing_skills"] == ["docker", "kubernetes"]

    def test_uses_fallback_for_non_dict_response(self) -> None:
        """Non-dictionary responses are rejected."""
        fallback = analyze_resume_job("test", "test")
        result = validate_analysis_response("not a dict", fallback)

        assert result == fallback

    def test_uses_fallback_for_missing_fields(self) -> None:
        """Response with missing fields uses fallback for missing fields."""
        response = {
            "match_percentage": 50,
            "matching_skills": ["python"],
            # Missing all other fields
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert result["match_percentage"] == 50
        assert result["matching_skills"] == ["python"]
        # Missing fields should come from fallback
        assert "missing_skills" in result
        assert "resume_improvement_suggestions" in result

    def test_rejects_out_of_range_match_percentage(self) -> None:
        """Match percentage outside [0, 100] is rejected."""
        response = {
            "match_percentage": 150,  # Invalid
            "matching_skills": [],
            "missing_skills": [],
            "missing_keywords": [],
            "relevant_experience_keywords": [],
            "recommended_skills": [],
            "resume_improvement_suggestions": [],
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert result["match_percentage"] == fallback["match_percentage"]

    def test_rejects_invalid_type_for_match_percentage(self) -> None:
        """Non-numeric match percentage is rejected."""
        response = {
            "match_percentage": "75%",  # String instead of number
            "matching_skills": [],
            "missing_skills": [],
            "missing_keywords": [],
            "relevant_experience_keywords": [],
            "recommended_skills": [],
            "resume_improvement_suggestions": [],
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert isinstance(result["match_percentage"], (int, float))

    def test_filters_non_string_items_from_skill_lists(self) -> None:
        """Non-string items in skill lists are filtered out."""
        response = {
            "match_percentage": 50,
            "matching_skills": ["python", 123, "sql"],  # 123 is invalid
            "missing_skills": ["docker"],
            "missing_keywords": [],
            "relevant_experience_keywords": [],
            "recommended_skills": [],
            "resume_improvement_suggestions": [],
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert result["matching_skills"] == ["python", "sql"]

    def test_handles_non_list_skill_fields(self) -> None:
        """Non-list skill fields are replaced with fallback."""
        response = {
            "match_percentage": 50,
            "matching_skills": "python,sql",  # String instead of list
            "missing_skills": ["docker"],
            "missing_keywords": [],
            "relevant_experience_keywords": [],
            "recommended_skills": [],
            "resume_improvement_suggestions": [],
        }
        fallback = analyze_resume_job("test", "test")

        result = validate_analysis_response(response, fallback)

        assert isinstance(result["matching_skills"], list)


class TestInterviewQuestionsValidation:
    """Tests for interview questions response validation."""

    def test_validates_correct_questions_response(self) -> None:
        """Valid questions response passes validation."""
        response = {
            "questions": [
                {
                    "question": "Tell me about your experience.",
                    "category": "Experience",
                    "difficulty": "Medium",
                    "suggested_answer": "Describe a project.",
                }
            ]
        }
        fallback = [{"question": "q", "category": "c", "difficulty": "d", "suggested_answer": "a"}]

        result = validate_interview_questions_response(response, fallback)

        assert len(result) == 1
        assert result[0]["question"] == "Tell me about your experience."

    def test_uses_fallback_for_non_dict_response(self) -> None:
        """Non-dictionary responses use fallback."""
        fallback = [{"question": "q", "category": "c", "difficulty": "d", "suggested_answer": "a"}]
        result = validate_interview_questions_response("not a dict", fallback)

        assert result == fallback

    def test_uses_fallback_when_questions_not_list(self) -> None:
        """Response without questions list uses fallback."""
        response = {"questions": "not a list"}
        fallback = [{"question": "q", "category": "c", "difficulty": "d", "suggested_answer": "a"}]

        result = validate_interview_questions_response(response, fallback)

        assert result == fallback

    def test_filters_invalid_question_items(self) -> None:
        """Invalid question items are filtered out."""
        response = {
            "questions": [
                {
                    "question": "Valid question",
                    "category": "Experience",
                    "difficulty": "Medium",
                    "suggested_answer": "Valid answer",
                },
                {
                    "question": "Invalid question",
                    "category": "Experience",
                    "difficulty": "Medium",
                    # Missing suggested_answer
                },
                "not a dict",  # Invalid entirely
            ]
        }
        fallback = [{"question": "q", "category": "c", "difficulty": "d", "suggested_answer": "a"}]

        result = validate_interview_questions_response(response, fallback)

        assert len(result) == 1
        assert result[0]["question"] == "Valid question"

    def test_uses_fallback_when_no_valid_questions(self) -> None:
        """If no valid questions found, use fallback."""
        response = {
            "questions": [
                {
                    "question": "Missing category",
                    "difficulty": "Medium",
                    "suggested_answer": "Answer",
                },
                {
                    "question": "Missing difficulty",
                    "category": "Experience",
                    "suggested_answer": "Answer",
                },
            ]
        }
        fallback = [{"question": "q", "category": "c", "difficulty": "d", "suggested_answer": "a"}]

        result = validate_interview_questions_response(response, fallback)

        assert result == fallback


class TestInterviewEvaluationValidation:
    """Tests for interview evaluation response validation."""

    def test_validates_correct_evaluation_response(self) -> None:
        """Valid evaluation response passes validation."""
        response = {
            "score": 85,
            "strengths": ["Clear communication", "Technical knowledge"],
            "improvements": ["Add examples", "More concise"],
        }
        fallback = {
            "score": None,
            "strengths": ["Fallback strength"],
            "improvements": ["Fallback improvement"],
        }

        result = validate_interview_evaluation_response(response, fallback)

        assert result["score"] == 85
        assert result["strengths"] == ["Clear communication", "Technical knowledge"]

    def test_uses_fallback_for_non_dict_response(self) -> None:
        """Non-dictionary responses use fallback."""
        fallback = {
            "score": None,
            "strengths": ["Fallback"],
            "improvements": ["Fallback"],
        }
        result = validate_interview_evaluation_response(not_a_dict := None, fallback)

        assert result == fallback

    def test_handles_missing_score(self) -> None:
        """Missing score defaults to None."""
        response = {
            "strengths": ["Good"],
            "improvements": ["Better"],
        }
        fallback = {
            "score": None,
            "strengths": ["Fallback"],
            "improvements": ["Fallback"],
        }

        result = validate_interview_evaluation_response(response, fallback)

        assert result["score"] is None
        assert result["strengths"] == ["Good"]

    def test_rejects_out_of_range_score(self) -> None:
        """Score outside [0, 100] is rejected."""
        response = {
            "score": 150,  # Invalid
            "strengths": ["Good"],
            "improvements": ["Better"],
        }
        fallback = {
            "score": None,
            "strengths": ["Fallback"],
            "improvements": ["Fallback"],
        }

        result = validate_interview_evaluation_response(response, fallback)

        assert result["score"] is None

    def test_rejects_non_numeric_score(self) -> None:
        """Non-numeric score is rejected."""
        response = {
            "score": "85",  # String instead of number
            "strengths": ["Good"],
            "improvements": ["Better"],
        }
        fallback = {
            "score": None,
            "strengths": ["Fallback"],
            "improvements": ["Fallback"],
        }

        result = validate_interview_evaluation_response(response, fallback)

        assert result["score"] is None

    def test_filters_non_string_items_from_arrays(self) -> None:
        """Non-string items in strengths/improvements are filtered."""
        response = {
            "score": 75,
            "strengths": ["Good", 123, "Clear"],  # 123 is invalid
            "improvements": ["Better", None],  # None is invalid
        }
        fallback = {
            "score": None,
            "strengths": ["Fallback"],
            "improvements": ["Fallback"],
        }

        result = validate_interview_evaluation_response(response, fallback)

        # Invalid arrays should use fallback
        assert result["strengths"] == fallback["strengths"]
        assert result["improvements"] == fallback["improvements"]
