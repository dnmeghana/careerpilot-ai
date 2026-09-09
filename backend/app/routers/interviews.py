from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Interview, InterviewQuestion, Job, Resume, User
from ..schemas import InterviewCreate, InterviewRegenerate, InterviewResponse, InterviewUpdate
from ..services.ai_service import get_ai_service

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])


def owned_interview(interview_id: UUID, user_id: UUID, database: Session) -> Interview:
    interview = database.execute(
        select(Interview)
        .where(Interview.id == interview_id, Interview.user_id == user_id)
        .options(joinedload(Interview.job), joinedload(Interview.questions))
    ).unique().scalar_one_or_none()
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return interview


def response(interview: Interview) -> InterviewResponse:
    return InterviewResponse.model_validate({**{field: getattr(interview, field) for field in ("id", "job_id", "interview_type", "scheduled_at", "status", "notes", "created_at", "updated_at")}, "job_title": interview.job.title, "company": interview.job.company, "questions": interview.questions})


@router.post(
    "",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create interview preparation",
    description="Create an interview plan for a user-owned job and generate preparation questions, optionally using a user-owned resume.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The job or resume was not found."}},
)
def create_interview(payload: InterviewCreate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> InterviewResponse:
    job = database.scalar(select(Job).where(Job.id == payload.job_id, Job.user_id == current_user.id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    resume = None
    if payload.resume_id is not None:
        resume = database.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id))
        if resume is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    interview = Interview(user_id=current_user.id, job_id=job.id, interview_type=payload.interview_type, scheduled_at=datetime.now(timezone.utc), notes=payload.notes)
    interview.questions = [InterviewQuestion(**question) for question in get_ai_service().generate_interview_questions(job.title, job.description, payload.interview_type, resume.extracted_text if resume else None)]
    database.add(interview)
    database.commit()
    database.refresh(interview)
    interview.job = job
    return response(interview)


@router.post(
    "/{interview_id}/regenerate",
    response_model=InterviewResponse,
    summary="Regenerate interview questions",
    description="Replace the questions for a user-owned interview plan, optionally using a user-owned resume as context.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The interview or resume was not found."}},
)
def regenerate_interview(interview_id: UUID, payload: InterviewRegenerate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> InterviewResponse:
    interview = owned_interview(interview_id, current_user.id, database)
    resume = None
    if payload.resume_id is not None:
        resume = database.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id))
        if resume is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    interview.questions = [InterviewQuestion(**question) for question in get_ai_service().generate_interview_questions(interview.job.title, interview.job.description, interview.interview_type, resume.extracted_text if resume else None)]
    database.commit()
    return response(owned_interview(interview_id, current_user.id, database))


@router.get(
    "",
    response_model=list[InterviewResponse],
    summary="List interview plans",
    description="List interview preparation plans owned by the authenticated user, newest first.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def list_interviews(current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[InterviewResponse]:
    interviews = database.scalars(select(Interview).where(Interview.user_id == current_user.id).options(joinedload(Interview.job), joinedload(Interview.questions)).order_by(Interview.created_at.desc())).unique().all()
    return [response(interview) for interview in interviews]


@router.get(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Get an interview plan",
    description="Return one interview preparation plan when it belongs to the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Interview not found."}},
)
def get_interview(interview_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> InterviewResponse:
    return response(owned_interview(interview_id, current_user.id, database))


@router.patch(
    "/{interview_id}",
    response_model=InterviewResponse,
    summary="Update interview preparation",
    description="Update notes or mark a question complete on a user-owned interview plan.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The interview or question was not found."}},
)
def update_interview(interview_id: UUID, payload: InterviewUpdate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> InterviewResponse:
    interview = owned_interview(interview_id, current_user.id, database)
    if payload.question_id is not None:
        question = next((item for item in interview.questions if item.id == payload.question_id), None)
        if question is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview question not found")
        if payload.completed is not None:
            question.completed = payload.completed
    if payload.notes is not None:
        interview.notes = payload.notes
    database.commit()
    database.refresh(interview)
    return response(interview)