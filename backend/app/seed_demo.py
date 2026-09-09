"""Create synthetic development data for a local CareerPilot database.

This module is intentionally command-line-only. It never runs during application startup.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import get_settings
from .database import SessionLocal
from .models import (
    AIAnalysis,
    Application,
    Interview,
    InterviewQuestion,
    Job,
    MockInterview,
    MockInterviewAnswer,
    Resume,
    Skill,
    SkillGap,
    User,
)

DEMO_EMAIL = "demo.user@careerpilot.local"
DEMO_PASSWORD = "DemoPassword123!"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed synthetic CareerPilot development data.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm that this command should write demo data to the configured database.",
    )
    return parser.parse_args()


def ensure_development_environment() -> None:
    environment = get_settings().environment.lower()
    if environment in {"production", "prod", "staging"}:
        raise RuntimeError("Demo seeding is disabled in production and staging environments")


def get_or_create_skills(database: Session, names: list[str]) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for name in names:
        skill = database.scalar(select(Skill).where(Skill.name == name))
        if skill is None:
            skill = Skill(name=name)
            database.add(skill)
            database.flush()
        skills[name] = skill
    return skills


def seed_demo_data(database: Session) -> User:
    existing_user = database.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing_user is not None:
        database.delete(existing_user)
        database.flush()

    user = User(name="Demo Career Navigator", email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
    database.add(user)
    database.flush()

    skills = get_or_create_skills(
        database,
        ["Python", "FastAPI", "SQL", "PostgreSQL", "React", "TypeScript", "Docker", "AWS", "System Design", "Testing"],
    )

    resume_primary = Resume(
        user_id=user.id,
        filename="demo_backend_resume.pdf",
        file_path="uploads/resumes/demo_backend_resume.pdf",
        extracted_text=(
            "Demo Career Navigator. Backend engineer with Python, FastAPI, SQL, PostgreSQL, Docker, "
            "automated testing, and cloud deployment experience."
        ),
        is_active=True,
    )
    resume_frontend = Resume(
        user_id=user.id,
        filename="demo_product_engineering_resume.pdf",
        file_path="uploads/resumes/demo_product_engineering_resume.pdf",
        extracted_text=(
            "Demo Career Navigator. Product-minded engineer with React, TypeScript, API integration, "
            "accessibility, and user-focused delivery experience."
        ),
        is_active=False,
    )
    resume_primary.skills = [skills[name] for name in ("Python", "FastAPI", "SQL", "PostgreSQL", "Docker", "Testing")]
    resume_frontend.skills = [skills[name] for name in ("React", "TypeScript", "Testing")]
    database.add_all([resume_primary, resume_frontend])

    jobs = [
        Job(
            user_id=user.id,
            title="Backend Platform Engineer",
            company="Northstar Labs",
            description="Build reliable Python APIs, improve PostgreSQL data services, and ship tested platform capabilities.",
            url="https://jobs.example.test/northstar-backend",
            location="Remote",
        ),
        Job(
            user_id=user.id,
            title="Product Engineer",
            company="Orbit Works",
            description="Create thoughtful product experiences with React and TypeScript while partnering across design and backend teams.",
            url="https://jobs.example.test/orbit-product",
            location="Hybrid",
        ),
        Job(
            user_id=user.id,
            title="Cloud Systems Developer",
            company="Summit Grid",
            description="Modernize containerized services, improve observability, and operate secure cloud infrastructure.",
            url="https://jobs.example.test/summit-cloud",
            location="Remote",
        ),
        Job(
            user_id=user.id,
            title="Technical Program Analyst",
            company="Cedar Systems",
            description="Coordinate technical delivery, communicate risks, and turn complex system work into clear execution plans.",
            url="https://jobs.example.test/cedar-programs",
            location="New York (fictional listing)",
        ),
    ]
    jobs[0].skills = [skills[name] for name in ("Python", "FastAPI", "SQL", "PostgreSQL", "Testing")]
    jobs[1].skills = [skills[name] for name in ("React", "TypeScript", "Testing")]
    jobs[2].skills = [skills[name] for name in ("Docker", "AWS", "PostgreSQL", "System Design")]
    jobs[3].skills = [skills[name] for name in ("SQL", "System Design", "Testing")]
    database.add_all(jobs)
    database.flush()

    applications = [
        Application(user_id=user.id, job_id=jobs[0].id, status="interview", application_date=date.today() - timedelta(days=18), interview_date=datetime.now(timezone.utc) + timedelta(days=3), salary=Decimal("132000"), recruiter_name="Demo Recruiter", recruiter_email="recruiter@northstar.example.test", notes="Technical conversation scheduled."),
        Application(user_id=user.id, job_id=jobs[1].id, status="offer", application_date=date.today() - timedelta(days=35), salary=Decimal("125000"), notes="Offer received; comparing role scope and growth."),
        Application(user_id=user.id, job_id=jobs[2].id, status="screening", application_date=date.today() - timedelta(days=8), salary=Decimal("140000"), notes="Recruiter screen pending."),
        Application(user_id=user.id, job_id=jobs[3].id, status="rejected", application_date=date.today() - timedelta(days=42), notes="Closed after initial review."),
    ]
    database.add_all(applications)

    interview = Interview(
        user_id=user.id,
        job_id=jobs[0].id,
        interview_type="Technical",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=3),
        status="scheduled",
        notes="Review API design, query performance, and testing tradeoffs.",
        questions=[
            InterviewQuestion(question="How would you design a resilient API for asynchronous work?", category="Technical", difficulty="Hard", suggested_answer="Discuss queues, idempotency, retries, observability, and failure boundaries.", completed=False),
            InterviewQuestion(question="Tell us about a time you improved a slow database query.", category="Behavioral", difficulty="Medium", suggested_answer="Use a concise situation, measurement, change, and outcome structure.", completed=True),
            InterviewQuestion(question="How do you decide what to test at the unit and integration levels?", category="Testing", difficulty="Medium", suggested_answer="Explain fast unit coverage plus a small set of contract and workflow tests.", completed=False),
        ],
    )
    database.add(interview)

    mock_interview = MockInterview(
        user_id=user.id,
        job_id=jobs[1].id,
        interview_type="Behavioral",
        started_at=datetime.now(timezone.utc) - timedelta(days=2),
        completed_at=datetime.now(timezone.utc) - timedelta(days=2),
        overall_score=Decimal("82"),
        answers=[
            MockInterviewAnswer(position=0, question="Describe a product decision you changed after learning from users.", category="Behavioral", difficulty="Medium", suggested_answer="Connect user evidence to the decision and measurable result.", answer="I used feedback from a pilot group to simplify the workflow and improve completion.", score=Decimal("86"), feedback=json.dumps({"strengths": ["Clear ownership"], "weaknesses": ["Add more measurable detail"], "suggestions": ["Include the before-and-after completion rate."]})),
            MockInterviewAnswer(position=1, question="How do you handle disagreement with a design partner?", category="Collaboration", difficulty="Medium", suggested_answer="Show curiosity, shared goals, evidence, and a decision path.", answer="I clarify the shared goal, compare evidence, and document the decision so the team can move forward.", score=Decimal("78"), feedback=json.dumps({"strengths": ["Collaborative framing"], "weaknesses": [], "suggestions": ["Name the tradeoff you accepted."]})),
        ],
    )
    database.add(mock_interview)

    database.add_all([
        SkillGap(user_id=user.id, resume_id=resume_primary.id, job_id=jobs[2].id, skill_id=skills["AWS"].id, priority=5),
        SkillGap(user_id=user.id, resume_id=resume_primary.id, job_id=jobs[2].id, skill_id=skills["System Design"].id, priority=4),
        SkillGap(user_id=user.id, resume_id=resume_frontend.id, job_id=jobs[0].id, skill_id=skills["FastAPI"].id, priority=3),
    ])

    database.add(AIAnalysis(
        user_id=user.id,
        resume_id=resume_primary.id,
        job_id=jobs[0].id,
        match_percentage=Decimal("88"),
        analysis_result=json.dumps({
            "matching_skills": ["Python", "FastAPI", "SQL", "PostgreSQL", "Testing"],
            "missing_skills": ["AWS"],
            "missing_keywords": ["event-driven systems"],
            "relevant_experience_keywords": ["API design", "database performance"],
            "recommended_skills": ["AWS", "event-driven systems"],
            "resume_improvement_suggestions": ["Add measurable outcomes to platform projects."],
        }),
    ))

    database.commit()
    database.refresh(user)
    return user


def main() -> None:
    args = parse_args()
    ensure_development_environment()
    if not args.confirm:
        raise SystemExit("Refusing to seed without --confirm. This command is for development databases only.")

    with SessionLocal() as database:
        user = seed_demo_data(database)
    print(f"Seeded synthetic demo data for {user.email}.")
    print(f"Demo password: {DEMO_PASSWORD}")
    print("Existing data for this demo account was replaced; other users were not modified.")


if __name__ == "__main__":
    main()
