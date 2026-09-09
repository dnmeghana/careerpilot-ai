import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Job, MockInterview, MockInterviewAnswer, Resume, User
from ..schemas import MockInterviewAnswerCreate, MockInterviewCreate, MockInterviewResponse
from ..services.ai_service import get_ai_service

router = APIRouter(prefix="/api/mock-interviews", tags=["Mock Interviews"])


def owned_mock_interview(interview_id: UUID, user_id: UUID, database: Session) -> MockInterview:
    interview = database.scalar(
        select(MockInterview)
        .where(MockInterview.id == interview_id, MockInterview.user_id == user_id)
        .options(joinedload(MockInterview.job), joinedload(MockInterview.answers))
    )
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock interview not found")
    interview.answers.sort(key=lambda item: item.position)
    return interview


def feedback_for(answer: MockInterviewAnswer) -> dict[str, object] | None:
    if not answer.feedback:
        return None
    try:
        value = json.loads(answer.feedback)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def response(interview: MockInterview) -> MockInterviewResponse:
    answered = [item for item in interview.answers if item.answer.strip()]
    evaluations = [(item, feedback_for(item)) for item in answered]
    strong_areas = sorted({item.category for item, feedback in evaluations if item.score is not None and item.score >= 75 and item.category})
    weak_areas = sorted({item.category for item, feedback in evaluations if item.score is not None and item.score < 70 and item.category})
    recommendations: list[str] = []
    for _, feedback in evaluations:
        if feedback:
            recommendations.extend(item for item in feedback.get("suggestions", []) if isinstance(item, str))
    questions = [
        {
            "id": item.id,
            "question": item.question,
            "category": item.category,
            "difficulty": item.difficulty,
            "suggested_answer": item.suggested_answer,
            "answer": item.answer,
            "score": item.score,
            "feedback": feedback_for(item),
        }
        for item in interview.answers
    ]
    return MockInterviewResponse.model_validate({
        "id": interview.id,
        "job_id": interview.job_id,
        "job_title": interview.job.title if interview.job else None,
        "company": interview.job.company if interview.job else None,
        "interview_type": interview.interview_type,
        "started_at": interview.started_at,
        "completed_at": interview.completed_at,
        "overall_score": interview.overall_score,
        "current_question": next((index for index, item in enumerate(interview.answers) if not item.answer.strip()), len(interview.answers)),
        "questions": questions,
        "strong_areas": strong_areas,
        "weak_areas": weak_areas,
        "recommendations": list(dict.fromkeys(recommendations)),
    })


@router.post(
    "",
    response_model=MockInterviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a mock interview",
    description="Start a practice interview for an optional user-owned job and generate questions using optional resume context.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The job or resume was not found."}},
)
def start_mock_interview(payload: MockInterviewCreate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> MockInterviewResponse:
    job = None
    if payload.job_id is not None:
        job = database.scalar(select(Job).where(Job.id == payload.job_id, Job.user_id == current_user.id))
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    resume_text = None
    if payload.resume_id is not None:
        resume = database.scalar(select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == current_user.id))
        if resume is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
        resume_text = resume.extracted_text
    title = job.title if job else "the role"
    description = job.description if job else "Explore the candidate's experience, judgment, and communication."
    interview = MockInterview(user_id=current_user.id, job_id=job.id if job else None, interview_type=payload.interview_type.title(), started_at=datetime.now(timezone.utc))
    interview.answers = [MockInterviewAnswer(position=index, question=item["question"], category=item.get("category"), difficulty=item.get("difficulty"), suggested_answer=item.get("suggested_answer"), answer="") for index, item in enumerate(get_ai_service().generate_interview_questions(title, description, payload.interview_type.title(), resume_text))]
    database.add(interview)
    database.commit()
    return response(owned_mock_interview(interview.id, current_user.id, database))


@router.get(
    "",
    response_model=list[MockInterviewResponse],
    summary="List mock interviews",
    description="List mock interviews owned by the authenticated user, newest first.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def list_mock_interviews(current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[MockInterviewResponse]:
    interviews = database.scalars(select(MockInterview).where(MockInterview.user_id == current_user.id).options(joinedload(MockInterview.job), joinedload(MockInterview.answers)).order_by(MockInterview.started_at.desc())).unique().all()
    return [response(interview) for interview in interviews]


@router.get(
    "/{interview_id}",
    response_model=MockInterviewResponse,
    summary="Get a mock interview",
    description="Return one mock interview and its questions when it belongs to the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Mock interview not found."}},
)
def get_mock_interview(interview_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> MockInterviewResponse:
    return response(owned_mock_interview(interview_id, current_user.id, database))


@router.post(
    "/{interview_id}/answers/{answer_id}",
    response_model=MockInterviewResponse,
    summary="Submit a mock interview answer",
    description="Submit an answer to an unanswered question in a user-owned mock interview and return the updated evaluation.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The mock interview or question was not found."}, 409: {"description": "The question has already been answered."}},
)
def submit_mock_answer(interview_id: UUID, answer_id: UUID, payload: MockInterviewAnswerCreate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> MockInterviewResponse:
    interview = owned_mock_interview(interview_id, current_user.id, database)
    answer_record = next((item for item in interview.answers if item.id == answer_id), None)
    if answer_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock interview question not found")
    if answer_record.answer.strip():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This answer has already been submitted")
    evaluation = get_ai_service().evaluate_interview_answer(answer_record.question, payload.answer, interview.interview_type)
    answer_record.answer = payload.answer.strip()
    answer_record.score = evaluation.get("score")
    answer_record.feedback = json.dumps({"strengths": evaluation.get("strengths", []), "weaknesses": evaluation.get("weaknesses", []), "suggestions": evaluation.get("suggestions", evaluation.get("improvements", []))})
    if all(item.answer.strip() for item in interview.answers):
        scores = [item.score for item in interview.answers if item.score is not None]
        interview.overall_score = sum(scores) / len(scores) if scores else None
        interview.completed_at = datetime.now(timezone.utc)
    database.commit()
    return response(owned_mock_interview(interview.id, current_user.id, database))