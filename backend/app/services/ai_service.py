import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import Settings, get_settings
from .interview_generator import generate_questions as generate_local_questions
from .local_analysis import analyze_resume_job
from .response_validator import (
    validate_analysis_response,
    validate_interview_evaluation_response,
    validate_interview_questions_response,
)

logger = logging.getLogger(__name__)


class AIProvider(Protocol):
    def complete(self, prompt: str) -> str:
        """Return a provider response for a prompt."""


class HttpAIProvider:
    """Small OpenAI-compatible provider adapter kept behind the service boundary."""

    def __init__(self, api_url: str, api_key: str, model: str, timeout: float) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        request = Request(
            self.api_url,
            data=json.dumps({
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"])


class AIService:
    def __init__(self, provider: AIProvider | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or self._configured_provider()

    def _configured_provider(self) -> AIProvider | None:
        if not self.settings.ai_provider or not self.settings.ai_api_key or not self.settings.ai_api_url:
            logger.info("AI provider is not configured; using local implementations")
            return None
        if self.settings.ai_provider.lower() != "openai_compatible":
            logger.warning("Unsupported AI provider '%s'; using local implementations", self.settings.ai_provider)
            return None
        return HttpAIProvider(self.settings.ai_api_url, self.settings.ai_api_key, self.settings.ai_model, self.settings.ai_timeout_seconds)

    def _provider_json(self, prompt: str) -> Mapping[str, Any] | None:
        """Call AI provider and parse JSON response.

        Handles various error cases gracefully, logging warnings but not raising exceptions.

        Args:
            prompt: The prompt to send to the AI provider

        Returns:
            Parsed JSON response as a dictionary, or None if provider unavailable or errors occur
        """
        if self.provider is None:
            logger.debug("No AI provider configured")
            return None
        try:
            response_text = self.provider.complete(prompt)
            result = json.loads(response_text)
            if not isinstance(result, dict):
                logger.warning("AI provider response was not a JSON object: %s", type(result).__name__)
                return None
            logger.debug("AI provider returned valid JSON response")
            return result
        except (HTTPError, URLError) as error:
            logger.warning("Network error calling AI provider: %s", error)
            return None
        except TimeoutError as error:
            logger.warning("AI provider request timed out: %s", error)
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Failed to parse AI provider response: %s", error)
            return None
        except Exception as error:
            logger.exception("Unexpected error calling AI provider: %s", error)
            return None

    def analyze_resume(self, resume_text: str, job_description: str = "") -> dict[str, Any]:
        """Analyze resume against job description using AI with local fallback.

        Args:
            resume_text: Extracted text from resume
            job_description: Job description to match against

        Returns:
            Validated analysis result with all required fields
        """
        fallback = analyze_resume_job(resume_text, job_description)
        result = self._provider_json(
            f"Analyze this resume against the job description. Return JSON matching this schema: {json.dumps(fallback)}. Resume: {resume_text}\nJob: {job_description}"
        )
        if result is None:
            logger.info("No AI provider result; using local analysis fallback")
            return fallback

        # Validate and sanitize the AI response
        validated = validate_analysis_response(dict(result), fallback)
        logger.info("Analysis validated: match_percentage=%s, %d matching skills", validated["match_percentage"], len(validated["matching_skills"]))
        return validated

    def analyze_job_match(self, resume_text: str, job_description: str) -> dict[str, Any]:
        return self.analyze_resume(resume_text, job_description)

    def generate_interview_questions(self, title: str, description: str | None, interview_type: str, resume_text: str | None = None) -> list[dict[str, str]]:
        """Generate interview questions using AI with local fallback.

        Args:
            title: Job title
            description: Job description
            interview_type: Type of interview (HR, Behavioral, Technical, System Design)

        Returns:
            List of validated question dictionaries
        """
        fallback = generate_local_questions(title, description, interview_type, resume_text)
        result = self._provider_json(
            f"Generate interview questions for a {interview_type} interview for {title}. Return JSON with a questions array; each item must include question, category, difficulty, and suggested_answer. Categories must be exactly Technical, Behavioral, Experience, Problem Solving, or Role Specific. Use relevant evidence from the resume when present. Job description: {description or ''}\nResume: {resume_text or ''}"
        )
        if result is None:
            logger.info("No AI provider result; using local question generation fallback")
            return fallback

        # Validate and sanitize the AI response
        validated = validate_interview_questions_response(dict(result), fallback)
        logger.info("Questions validated: %d questions", len(validated))
        return validated

    def evaluate_interview_answer(self, question: str, answer: str, interview_type: str = "") -> dict[str, Any]:
        """Evaluate interview answer using AI with sensible fallback.

        Args:
            question: Interview question
            answer: Candidate's answer
            interview_type: Type of interview for context

        Returns:
            Validated evaluation result with score, strengths, and improvements
        """
        answer_length = len(answer.strip())
        score = min(100, 35 + min(40, answer_length // 12) + (15 if any(marker in answer.lower() for marker in ("result", "impact", "%", "increased", "reduced")) else 0) + (10 if any(marker in answer.lower() for marker in ("because", "first", "then", "finally")) else 0))
        fallback = {
            "score": score,
            "strengths": ["You provided a concrete response that can be developed further." if answer_length >= 80 else "You started answering the question directly."],
            "weaknesses": ["The answer would be stronger with more specific evidence and measurable impact."],
            "suggestions": ["Use a clear situation, action, result structure and name what changed because of your work."],
            "improvements": ["Use a clear situation, action, result structure and name what changed because of your work."],
        }
        result = self._provider_json(
            f"Evaluate this {interview_type} interview answer. Return JSON with score from 0 to 100, strengths array, weaknesses array, and suggestions array. Give specific, actionable feedback. Question: {question}\nAnswer: {answer}"
        )
        if result is None:
            logger.info("No AI provider result; using fallback evaluation")
            return fallback

        # Validate and sanitize the AI response
        validated = validate_interview_evaluation_response(dict(result), fallback)
        logger.info("Evaluation validated: score=%s", validated.get("score"))
        return validated

    def career_assistant_response(self, message: str, context: str = "") -> str:
        fallback = (
            "I can help you make this concrete. Review the role requirements against your resume, "
            "choose one evidence-based example, and turn it into a specific next step."
        )
        result = self._provider_json(
            f"Respond helpfully as a practical career coach. Answer the user's question directly and concisely. "
            f"Use only the private career context supplied below when it is relevant. Do not invent facts. "
            f"Return JSON with a response string. Context: {context}\nQuestion: {message}"
        )
        if result is not None and isinstance(result.get("response"), str):
            return result["response"]
        return fallback


def get_ai_service() -> AIService:
    return AIService()