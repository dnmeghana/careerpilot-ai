"""Validation utilities for AI service responses.

Ensures AI responses conform to expected schemas before returning to clients.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Required fields for resume/job analysis
ANALYSIS_REQUIRED_FIELDS = {
    "match_percentage": (float, int),
    "matching_skills": list,
    "missing_skills": list,
    "missing_keywords": list,
    "relevant_experience_keywords": list,
    "recommended_skills": list,
    "resume_improvement_suggestions": list,
}

# Field constraints
ANALYSIS_FIELD_CONSTRAINTS = {
    "match_percentage": (0, 100),  # min, max
}


def validate_analysis_response(response: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize a resume/job analysis response.

    Checks that the response contains all required fields with correct types.
    Falls back to local analysis if validation fails.

    Args:
        response: Raw response from AI provider or validation source
        fallback: Local analysis result to use if validation fails

    Returns:
        Validated analysis result with all required fields
    """
    if not isinstance(response, dict):
        logger.warning("Analysis response is not a dictionary; using fallback")
        return fallback

    validated = {}
    missing_fields = []

    # Validate each required field
    for field, expected_type in ANALYSIS_REQUIRED_FIELDS.items():
        if field not in response:
            missing_fields.append(field)
            validated[field] = fallback.get(field)
            continue

        value = response[field]

        # Type validation
        if not isinstance(value, expected_type):
            logger.warning(
                "Field %s has incorrect type %s (expected %s); using fallback value",
                field,
                type(value).__name__,
                expected_type.__name__ if not isinstance(expected_type, tuple) else str(expected_type),
            )
            validated[field] = fallback.get(field)
            continue

        # Value validation
        if field == "match_percentage":
            if not isinstance(value, (int, float)) or not (0 <= value <= 100):
                logger.warning("match_percentage is out of range [0, 100]: %s; using fallback", value)
                validated[field] = fallback["match_percentage"]
                continue

        # List validation - ensure all items are strings for skill lists
        if field in ("matching_skills", "missing_skills", "missing_keywords", "relevant_experience_keywords", "recommended_skills", "resume_improvement_suggestions"):
            if not isinstance(value, list):
                logger.warning("Field %s is not a list; using fallback", field)
                validated[field] = fallback.get(field, [])
                continue

            # Validate list contents
            if field != "resume_improvement_suggestions":
                # Skill lists should contain only strings
                if not all(isinstance(item, str) for item in value):
                    logger.warning("Field %s contains non-string items; filtering", field)
                    validated[field] = [item for item in value if isinstance(item, str)]
            else:
                # Suggestions should also be strings
                if not all(isinstance(item, str) for item in value):
                    logger.warning("Field %s contains non-string items; filtering", field)
                    validated[field] = [item for item in value if isinstance(item, str)]

            # Set the value after validation
            if field not in validated:
                validated[field] = value
        else:
            validated[field] = value

    # Log if any fields were missing
    if missing_fields:
        logger.warning("Analysis response missing fields: %s; using fallback values", ", ".join(missing_fields))

    # Ensure all fields are present with at least fallback values
    for field in ANALYSIS_REQUIRED_FIELDS:
        if field not in validated:
            validated[field] = fallback.get(field)

    return validated


def validate_interview_questions_response(response: dict[str, Any] | None, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    """Validate interview questions response from AI provider.

    Ensures response contains valid question objects with required fields.

    Args:
        response: Raw response from AI provider
        fallback: Local generation result to use if validation fails

    Returns:
        List of validated question dictionaries
    """
    if not isinstance(response, dict):
        logger.warning("Interview questions response is not a dictionary; using fallback")
        return fallback

    questions = response.get("questions")
    if not isinstance(questions, list):
        logger.warning("Response questions field is not a list; using fallback")
        return fallback

    required_question_fields = ("question", "category", "difficulty", "suggested_answer")
    validated_questions = []

    for idx, item in enumerate(questions):
        if not isinstance(item, dict):
            logger.warning("Question item %d is not a dictionary; skipping", idx)
            continue

        # Check all required fields are strings
        allowed_categories = {"Technical", "Behavioral", "Experience", "Problem Solving", "Role Specific"}
        if all(isinstance(item.get(field), str) for field in required_question_fields) and item["category"] in allowed_categories:
            validated_questions.append(item)
        else:
            logger.warning("Question item %d missing or invalid required fields; skipping", idx)

    if not validated_questions:
        logger.warning("No valid questions found in response; using fallback")
        return fallback

    return validated_questions


def validate_interview_evaluation_response(response: dict[str, Any] | None, fallback: dict[str, Any]) -> dict[str, Any]:
    """Validate interview answer evaluation response from AI provider.

    Ensures response contains score and feedback arrays.

    Args:
        response: Raw response from AI provider
        fallback: Local evaluation result to use if validation fails

    Returns:
        Validated evaluation result
    """
    if not isinstance(response, dict):
        logger.warning("Evaluation response is not a dictionary; using fallback")
        return fallback

    validated = {}

    # Validate score (optional, can be None)
    score = response.get("score")
    if score is not None:
        if not isinstance(score, (int, float)):
            logger.warning("Score is not numeric; using None")
            validated["score"] = None
        elif not (0 <= score <= 100):
            logger.warning("Score is out of range [0, 100]: %s; using None", score)
            validated["score"] = None
        else:
            validated["score"] = score
    else:
        validated["score"] = None

    # Validate strengths array
    strengths = response.get("strengths")
    if isinstance(strengths, list) and all(isinstance(s, str) for s in strengths):
        validated["strengths"] = strengths
    else:
        logger.warning("Strengths is not a valid string list; using fallback")
        validated["strengths"] = fallback.get("strengths", [])

    weaknesses = response.get("weaknesses")
    if isinstance(weaknesses, list) and all(isinstance(item, str) for item in weaknesses):
        validated["weaknesses"] = weaknesses
    else:
        validated["weaknesses"] = fallback.get("weaknesses", [])

    suggestions = response.get("suggestions", response.get("improvements"))
    if isinstance(suggestions, list) and all(isinstance(item, str) for item in suggestions):
        validated["suggestions"] = suggestions
    else:
        validated["suggestions"] = fallback.get("suggestions", fallback.get("improvements", []))

    # Preserve the legacy key for existing callers.
    improvements = response.get("improvements", suggestions)
    if isinstance(improvements, list) and all(isinstance(i, str) for i in improvements):
        validated["improvements"] = improvements
    else:
        logger.warning("Improvements is not a valid string list; using fallback")
        validated["improvements"] = fallback.get("improvements", [])

    if "improvements" not in validated:
        validated["improvements"] = validated["suggestions"]

    return validated
