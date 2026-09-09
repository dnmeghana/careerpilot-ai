"""Tests for AI service with validation and fallback behavior.

Tests ensure AI provider is used when available, with proper validation
and fallback to local implementations on failure.
"""

from app.config import Settings
from app.services.ai_service import AIService
from app.services.interview_generator import generate_questions
from app.services.local_analysis import analyze_resume_job


class FailingProvider:
    """Provider that always fails."""

    def complete(self, prompt: str) -> str:
        raise RuntimeError("provider unavailable")


class InvalidJsonProvider:
    """Provider that returns invalid JSON."""

    def complete(self, prompt: str) -> str:
        return "not json"


class MalformedAnalysisProvider:
    """Provider that returns JSON but with wrong structure."""

    def complete(self, prompt: str) -> str:
        if "Analyze" in prompt:
            return '{"wrong_field": "value"}'
        if "Generate interview questions" in prompt:
            return '{"questions": "not_a_list"}'
        if "Evaluate" in prompt:
            return '{"score": "not_numeric"}'
        return '{"response": "text"}'


class ValidJsonProvider:
    """Provider that returns valid, correctly structured JSON."""

    def complete(self, prompt: str) -> str:
        if "Analyze" in prompt:
            return '''{
                "match_percentage": 80.5,
                "matching_skills": ["python", "sql"],
                "missing_skills": ["docker"],
                "missing_keywords": ["containerization"],
                "relevant_experience_keywords": ["backend"],
                "recommended_skills": ["docker", "kubernetes"],
                "resume_improvement_suggestions": ["Add Docker experience."]
            }'''
        if "Generate interview questions" in prompt:
            return '{"questions": [{"question": "Tell me about your work.", "category": "Experience", "difficulty": "Easy", "suggested_answer": "Use a concrete example."}]}'
        if "Evaluate" in prompt:
            return '{"score": 80, "strengths": ["Clear"], "improvements": ["Add results"]}'
        if "Respond helpfully" in prompt:
            return '{"response": "Choose one concrete next step."}'
        return '{"response": "default"}'


class TestMissingProvider:
    """Tests for behavior when AI provider is not configured."""

    def test_missing_provider_uses_local_analysis(self) -> None:
        """When no provider configured, analyze_job_match uses local implementation."""
        service = AIService(settings=Settings(ai_provider=None, ai_api_key=None, ai_api_url=None))
        expected = analyze_resume_job("Python", "Python APIs")

        result = service.analyze_job_match("Python", "Python APIs")

        assert result == expected

    def test_missing_provider_uses_local_questions(self) -> None:
        """When no provider configured, generate_interview_questions uses local implementation."""
        service = AIService(settings=Settings(ai_provider=None, ai_api_key=None, ai_api_url=None))
        expected = generate_questions("Engineer", "Build APIs", "Technical")

        result = service.generate_interview_questions("Engineer", "Build APIs", "Technical")

        assert result == expected

    def test_missing_provider_uses_fallback_evaluation(self) -> None:
        """When no provider configured, evaluate_interview_answer uses fallback."""
        service = AIService(settings=Settings(ai_provider=None, ai_api_key=None, ai_api_url=None))

        result = service.evaluate_interview_answer("Why this role?", "I enjoy this work.")

        assert 0 <= result["score"] <= 100
        assert result["strengths"]
        assert result["improvements"]


class TestProviderFailures:
    """Tests for behavior when AI provider fails."""

    def test_provider_exception_falls_back_without_breaking(self) -> None:
        """When provider raises exception, falls back gracefully."""
        service = AIService(provider=FailingProvider())

        result = service.evaluate_interview_answer("Why this role?", "I enjoy this work.")

        assert 0 <= result["score"] <= 100
        assert result["strengths"]
        assert result["improvements"]

    def test_provider_invalid_json_falls_back(self) -> None:
        """When provider returns invalid JSON, falls back gracefully."""
        service = AIService(provider=InvalidJsonProvider())

        result = service.evaluate_interview_answer("Why?", "Because.")

        assert 0 <= result["score"] <= 100
        assert result["strengths"]
        assert result["improvements"]

    def test_malformed_analysis_response_falls_back(self) -> None:
        """When provider returns wrong JSON structure, falls back gracefully."""
        service = AIService(provider=MalformedAnalysisProvider())

        result = service.analyze_job_match("Python", "Python APIs")

        # Should have all required fields from fallback
        assert "match_percentage" in result
        assert "matching_skills" in result
        assert "missing_skills" in result
        assert "missing_keywords" in result

    def test_malformed_questions_response_falls_back(self) -> None:
        """When provider returns malformed questions, falls back gracefully."""
        service = AIService(provider=MalformedAnalysisProvider())

        result = service.generate_interview_questions("Engineer", "Build APIs", "Technical")

        # Should return local questions
        assert isinstance(result, list)
        assert all("question" in q for q in result)

    def test_malformed_evaluation_response_falls_back(self) -> None:
        """When provider returns malformed evaluation, falls back gracefully."""
        service = AIService(provider=MalformedAnalysisProvider())

        result = service.evaluate_interview_answer("Why?", "Because.")

        assert result["score"] is None
        assert result["strengths"]
        assert result["improvements"]


class TestValidProvider:
    """Tests for behavior when AI provider returns valid responses."""

    def test_valid_provider_analysis_is_used(self) -> None:
        """When provider returns valid analysis, it's used and validated."""
        service = AIService(provider=ValidJsonProvider())

        result = service.analyze_job_match("Python background", "Python and Docker role")

        assert result["match_percentage"] == 80.5
        assert "python" in result["matching_skills"]
        assert "docker" in result["missing_skills"]
        assert "resume_improvement_suggestions" in result

    def test_valid_provider_questions_are_used(self) -> None:
        """When provider returns valid questions, they're used."""
        service = AIService(provider=ValidJsonProvider())

        result = service.generate_interview_questions("Engineer", "Build APIs", "Technical")

        assert len(result) == 1
        assert result[0]["question"] == "Tell me about your work."
        assert result[0]["category"] == "Experience"

    def test_valid_provider_evaluation_is_used(self) -> None:
        """When provider returns valid evaluation, it's used."""
        service = AIService(provider=ValidJsonProvider())

        result = service.evaluate_interview_answer("Why?", "Because.")

        assert result["score"] == 80
        assert result["strengths"] == ["Clear"]
        assert result["improvements"] == ["Add results"]

    def test_valid_provider_career_response_is_used(self) -> None:
        """When provider returns valid career response, it's used."""
        service = AIService(provider=ValidJsonProvider())

        result = service.career_assistant_response("What next?")

        assert result == "Choose one concrete next step."
