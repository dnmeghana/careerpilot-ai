"""Resume and job analysis endpoints.

Provides API routes for analyzing resumes against job descriptions using AI service
with local fallback, and retrieving skill gap analyses.
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AIAnalysis, Job, Resume, User
from ..schemas import ResumeJobAnalysisRequest, ResumeJobAnalysisResponse, SkillGapResponse, SkillPriority
from ..services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


def owned(model, item_id: UUID, user_id: UUID, database: Session):
    """Verify that a resource is owned by the current user.

    Args:
        model: SQLAlchemy model class
        item_id: ID of the item to check
        user_id: ID of the user
        database: Database session

    Returns:
        The model instance if found and owned by user

    Raises:
        HTTPException: 404 if item not found or not owned by user
    """
    item = database.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found")
    return item


@router.post(
    "/resume-job",
    response_model=ResumeJobAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Analyze resume fit for a job",
    description="Compare a user-owned resume with a user-owned job, store the structured result, and return match details.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The resume or job was not found."}, 422: {"description": "The resume has no extracted text or the job has no description."}, 500: {"description": "The analysis service failed."}},
)
def resume_job_analysis(
    payload: ResumeJobAnalysisRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ResumeJobAnalysisResponse:
    """Analyze a resume against a job description.

    Performs comprehensive analysis by:
    1. Verifying ownership of resume and job
    2. Calling AI service with validated fallback to local analysis
    3. Validating and storing results in PostgreSQL
    4. Returning structured analysis data

    Args:
        payload: Request containing resume_id and job_id
        current_user: Authenticated user
        database: Database session

    Returns:
        ResumeJobAnalysisResponse with match percentage, skills, keywords, and suggestions

    Raises:
        HTTPException: 404 if resume or job not found or not owned by user
    """
    # Verify ownership of both resume and job
    resume = owned(Resume, payload.resume_id, current_user.id, database)
    job = owned(Job, payload.job_id, current_user.id, database)

    # Validate required data
    if not resume.extracted_text:
        logger.warning("Resume %s has no extracted text", resume.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume must have extracted text. Please re-upload or parse the resume.",
        )

    if not job.description:
        logger.warning("Job %s has no description", job.id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job must have a description to analyze.",
        )

    # Perform analysis using AI service (with local fallback)
    job_text = f"{job.title}\n{job.description}"
    logger.info("Analyzing resume %s against job %s for user %s", resume.id, job.id, current_user.id)

    try:
        result = get_ai_service().analyze_job_match(resume.extracted_text, job_text)
    except Exception as error:
        logger.error("Analysis failed: %s; returning error to client", error, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed. Please try again.",
        ) from error

    # Validate match_percentage is in valid range
    try:
        match_percentage = float(result.get("match_percentage", 0))
        if not (0 <= match_percentage <= 100):
            logger.warning("Invalid match_percentage %s; clamping to range", match_percentage)
            match_percentage = min(100, max(0, match_percentage))
    except (TypeError, ValueError) as error:
        logger.warning("Could not parse match_percentage: %s", error)
        match_percentage = 0

    # Store analysis in database
    analysis = AIAnalysis(
        user_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        match_percentage=match_percentage,
        analysis_result=json.dumps(result),
    )
    database.add(analysis)
    database.commit()
    database.refresh(analysis)

    logger.info(
        "Analysis stored: id=%s, match_percentage=%s, user=%s",
        analysis.id,
        match_percentage,
        current_user.id,
    )

    # Return analysis with all fields
    return ResumeJobAnalysisResponse(
        id=analysis.id,
        resume_id=resume.id,
        job_id=job.id,
        created_at=analysis.created_at,
        **result,
    )


@router.get(
    "/skill-gap",
    response_model=SkillGapResponse,
    tags=["Skills"],
    summary="Get the latest skill gap",
    description="Return the authenticated user's latest resume/job analysis with prioritized missing skills and recommended learning areas.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def skill_gap(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> SkillGapResponse:
    """Get the most recent skill gap analysis for the user.

    Returns the latest analysis with computed skill priorities based on missing skills.

    Args:
        current_user: Authenticated user
        database: Database session

    Returns:
        SkillGapResponse with analysis details or empty response if no analysis exists
    """
    analysis = database.scalar(
        select(AIAnalysis).where(AIAnalysis.user_id == current_user.id).order_by(AIAnalysis.created_at.desc())
    )

    if analysis is None:
        logger.info("No analysis found for user %s", current_user.id)
        return SkillGapResponse(has_analysis=False)

    # Parse stored analysis result
    try:
        result = json.loads(analysis.analysis_result)
    except json.JSONDecodeError as error:
        logger.error("Failed to parse analysis result for analysis %s: %s", analysis.id, error)
        return SkillGapResponse(has_analysis=False)

    # Load related resume and job
    job = database.scalar(select(Job).where(Job.id == analysis.job_id))
    resume = database.scalar(select(Resume).where(Resume.id == analysis.resume_id))

    missing = result.get("missing_skills", [])
    # Compute priority: highest index (most important) gets highest priority (5)
    priorities = [
        SkillPriority(skill=skill, priority=max(1, 5 - index))
        for index, skill in enumerate(missing)
    ]

    logger.info(
        "Returning skill gap: analysis=%s, missing_skills=%d, user=%s",
        analysis.id,
        len(missing),
        current_user.id,
    )

    return SkillGapResponse(
        has_analysis=True,
        analysis_id=analysis.id,
        resume_id=analysis.resume_id,
        job_id=analysis.job_id,
        resume_name=resume.filename if resume else None,
        job_title=job.title if job else None,
        company=job.company if job else None,
        match_percentage=result.get("match_percentage", 0),
        matching_skills=result.get("matching_skills", []),
        missing_skills=missing,
        skill_priorities=priorities,
        recommended_learning_areas=result.get("recommended_skills", []),
        created_at=analysis.created_at,
    )
