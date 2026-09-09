from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Application, Interview, Job, Resume, Skill, SkillGap, User
from ..schemas import AssistantChatRequest, AssistantChatResponse
from ..services.ai_service import get_ai_service

router = APIRouter(prefix="/api/assistant", tags=["AI Assistant"])


def owned(model, item_id: UUID, user_id: UUID, database: Session):
    item = database.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found")
    return item


def build_context(payload: AssistantChatRequest, user: User, database: Session) -> tuple[str, list[str]]:
    sections: list[str] = [f"User name: {user.name}"]
    labels: list[str] = []
    active_resume = database.scalar(select(Resume).where(Resume.user_id == user.id, Resume.is_active.is_(True)).order_by(Resume.updated_at.desc()))
    if active_resume:
        sections.append(f"Active resume ({active_resume.filename}):\n{(active_resume.extracted_text or '')[:7000]}")
        labels.append(f"Active resume: {active_resume.filename}")

    selected_job = owned(Job, payload.job_id, user.id, database) if payload.job_id else None
    if selected_job:
        sections.append(f"Selected job: {selected_job.title} at {selected_job.company}\n{selected_job.description or 'No job description provided.'}")
        labels.append(f"Job: {selected_job.title} at {selected_job.company}")

    saved_jobs = database.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.updated_at.desc()).limit(10)).all()
    if saved_jobs:
        sections.append("Saved roles:\n" + "\n".join(f"- {job.title} at {job.company}: {job.description or 'no description'}" for job in saved_jobs))
        labels.append(f"Saved roles: {len(saved_jobs)}")

    applications_query = select(Application).where(Application.user_id == user.id).options(joinedload(Application.job))
    if selected_job:
        applications_query = applications_query.where(Application.job_id == selected_job.id)
    applications_query = applications_query.order_by(Application.updated_at.desc()).limit(8)
    applications = database.scalars(applications_query).unique().all()
    if applications:
        sections.append("Applications:\n" + "\n".join(f"- {item.job.title} at {item.job.company}: {item.status}; notes: {item.notes or 'none'}" for item in applications))
        labels.append(f"Applications: {len(applications)}")

    gap_query = select(SkillGap, Skill.name, Job.title, Job.company).join(Skill, Skill.id == SkillGap.skill_id).join(Job, Job.id == SkillGap.job_id).where(SkillGap.user_id == user.id)
    if selected_job:
        gap_query = gap_query.where(SkillGap.job_id == selected_job.id)
    gap_query = gap_query.order_by(SkillGap.priority.desc()).limit(10)
    gaps = database.execute(gap_query).all()
    if gaps:
        sections.append("Skill gaps:\n" + "\n".join(f"- {name} for {title} at {company} (priority {gap.priority}/5)" for gap, name, title, company in gaps))
        labels.append(f"Skill gaps: {len(gaps)}")

    interview_query = select(Interview).where(Interview.user_id == user.id).options(joinedload(Interview.job), joinedload(Interview.questions)).order_by(Interview.scheduled_at.desc()).limit(6)
    if payload.interview_id:
        interview_query = interview_query.where(Interview.id == payload.interview_id)
    elif selected_job:
        interview_query = interview_query.where(Interview.job_id == selected_job.id)
    interviews = database.scalars(interview_query).unique().all()
    if interviews:
        sections.append("Interview information:\n" + "\n".join(f"- {item.interview_type} interview for {item.job.title} at {item.job.company}; status {item.status}; notes: {item.notes or 'none'}; questions: {' | '.join(question.question for question in item.questions[:5]) or 'none'}" for item in interviews))
        labels.append(f"Interviews: {len(interviews)}")

    return "\n\n".join(sections), labels


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Ask the AI career assistant",
    description="Send a career question using the authenticated user's resume, jobs, applications, skill gaps, and interview context.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "A selected job or interview was not found."}},
)
def chat(payload: AssistantChatRequest, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> AssistantChatResponse:
    context, labels = build_context(payload, current_user, database)
    answer = get_ai_service().career_assistant_response(payload.message.strip(), context)
    return AssistantChatResponse(response=answer, context_labels=labels)