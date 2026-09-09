from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Application, Interview, Job, Skill, SkillGap
from ..schemas import DashboardResponse


def get_dashboard(user_id: UUID, database: Session) -> DashboardResponse:
    applications = database.scalars(
        select(Application)
        .where(Application.user_id == user_id)
        .options(joinedload(Application.job))
        .order_by(Application.updated_at.desc())
        .limit(5)
    ).unique().all()
    interviews = database.scalars(
        select(Interview)
        .where(
            Interview.user_id == user_id,
            Interview.scheduled_at >= datetime.now(timezone.utc),
            Interview.status != "cancelled",
        )
        .options(joinedload(Interview.job))
        .order_by(Interview.scheduled_at.asc())
        .limit(5)
    ).unique().all()
    gaps = database.execute(
        select(SkillGap, Skill.name, Job.title, Job.company)
        .join(Skill, Skill.id == SkillGap.skill_id)
        .join(Job, Job.id == SkillGap.job_id)
        .where(SkillGap.user_id == user_id)
        .order_by(SkillGap.priority.desc(), SkillGap.updated_at.desc())
        .limit(5)
    ).all()

    def count(model: type[Application] | type[Interview]) -> int:
        return database.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) or 0

    def status_count(value: str) -> int:
        return database.scalar(
            select(func.count()).select_from(Application).where(Application.user_id == user_id, Application.status == value)
        ) or 0

    total = count(Application)
    interviews_count = count(Interview)
    offers = status_count("offer") + status_count("offered")
    rejections = status_count("rejected")

    activity = database.execute(
        select(Application.updated_at, Application.status, Job.company)
        .join(Job, Job.id == Application.job_id)
        .where(Application.user_id == user_id)
        .order_by(Application.updated_at.desc())
        .limit(7)
    ).all()

    return DashboardResponse(
        stats={
            "total_applications": total,
            "interviews": interviews_count,
            "offers": offers,
            "rejections": rejections,
            "success_rate": round((offers / total) * 100, 1) if total else 0,
        },
        recent_applications=[
            {"id": application.id, "company": application.job.company, "role": application.job.title, "status": application.status, "updated_at": application.updated_at}
            for application in applications
        ],
        upcoming_interviews=[
            {"id": interview.id, "company": interview.job.company, "role": interview.job.title, "type": interview.interview_type, "scheduled_at": interview.scheduled_at}
            for interview in interviews
        ],
        skill_gaps=[
            {"id": gap.id, "skill": name, "role": title, "company": company, "priority": gap.priority}
            for gap, name, title, company in gaps
        ],
        activity=[
            {"date": updated_at, "status": status, "company": company}
            for updated_at, status, company in activity
        ],
    )
