from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    resumes: Mapped[List[Resume]] = relationship(back_populates="user", cascade="all, delete-orphan")
    jobs: Mapped[List[Job]] = relationship(back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List[Application]] = relationship(back_populates="user", cascade="all, delete-orphan")
    skill_gaps: Mapped[List[SkillGap]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interviews: Mapped[List[Interview]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mock_interviews: Mapped[List[MockInterview]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_analyses: Mapped[List[AIAnalysis]] = relationship(back_populates="user", cascade="all, delete-orphan")
    candidate_profile: Mapped[Optional[CandidateProfile]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    automation_runs: Mapped[List[AutomationRun]] = relationship(back_populates="user", cascade="all, delete-orphan")
    automation_scenarios: Mapped[List[AutomationScenario]] = relationship(back_populates="user", cascade="all, delete-orphan")
    automation_setting: Mapped[Optional[AutomationSetting]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("ix_resumes_user_active", "user_id", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    user: Mapped[User] = relationship(back_populates="resumes")
    skills: Mapped[List[Skill]] = relationship(secondary="resume_skills", back_populates="resumes")
    skill_gaps: Mapped[List[SkillGap]] = relationship(back_populates="resume")
    ai_analyses: Mapped[List[AIAnalysis]] = relationship(back_populates="resume")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_user_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(2048))
    location: Mapped[Optional[str]] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="jobs")
    applications: Mapped[List[Application]] = relationship(back_populates="job", cascade="all, delete-orphan")
    skills: Mapped[List[Skill]] = relationship(secondary="job_skills", back_populates="jobs")
    skill_gaps: Mapped[List[SkillGap]] = relationship(back_populates="job")
    interviews: Mapped[List[Interview]] = relationship(back_populates="job", cascade="all, delete-orphan")
    mock_interviews: Mapped[List[MockInterview]] = relationship(back_populates="job", cascade="all, delete-orphan")
    ai_analyses: Mapped[List[AIAnalysis]] = relationship(back_populates="job")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
        CheckConstraint("salary IS NULL OR salary >= 0", name="ck_applications_salary_nonnegative"),
        Index("ix_applications_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="saved", server_default="saved")
    application_date: Mapped[Optional[date]] = mapped_column(Date)
    interview_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    recruiter_name: Mapped[Optional[str]] = mapped_column(String(120))
    recruiter_email: Mapped[Optional[str]] = mapped_column(String(320))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    automation_status: Mapped[Optional[str]] = mapped_column(String(32))
    last_automation_attempt: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="applications")
    job: Mapped[Job] = relationship(back_populates="applications")
    automation_runs: Mapped[List[AutomationRun]] = relationship(back_populates="application")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)

    resumes: Mapped[List[Resume]] = relationship(secondary="resume_skills", back_populates="skills")
    jobs: Mapped[List[Job]] = relationship(secondary="job_skills", back_populates="skills")
    skill_gaps: Mapped[List[SkillGap]] = relationship(back_populates="skill")


class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class SkillGap(TimestampMixin, Base):
    __tablename__ = "skill_gaps"
    __table_args__ = (
        UniqueConstraint("user_id", "resume_id", "job_id", "skill_id", name="uq_skill_gaps_context"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_skill_gaps_priority_range"),
        Index("ix_skill_gaps_user_priority", "user_id", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped[User] = relationship(back_populates="skill_gaps")
    resume: Mapped[Resume] = relationship(back_populates="skill_gaps")
    job: Mapped[Job] = relationship(back_populates="skill_gaps")
    skill: Mapped[Skill] = relationship(back_populates="skill_gaps")


class Interview(TimestampMixin, Base):
    __tablename__ = "interviews"
    __table_args__ = (Index("ix_interviews_user_scheduled_at", "user_id", "scheduled_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled", server_default="scheduled")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="interviews")
    job: Mapped[Job] = relationship(back_populates="interviews")
    questions: Mapped[List[InterviewQuestion]] = relationship(back_populates="interview", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (Index("ix_interview_questions_interview", "interview_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    difficulty: Mapped[Optional[str]] = mapped_column(String(32))
    suggested_answer: Mapped[Optional[str]] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    interview: Mapped[Interview] = relationship(back_populates="questions")


class MockInterview(TimestampMixin, Base):
    __tablename__ = "mock_interviews"
    __table_args__ = (
        CheckConstraint("overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)", name="ck_mock_interviews_score_range"),
        Index("ix_mock_interviews_user_started_at", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    interview_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Behavioral", server_default="Behavioral")
    overall_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="mock_interviews")
    job: Mapped[Optional[Job]] = relationship(back_populates="mock_interviews")
    answers: Mapped[List[MockInterviewAnswer]] = relationship(back_populates="mock_interview", cascade="all, delete-orphan")


class MockInterviewAnswer(Base):
    __tablename__ = "mock_interview_answers"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_mock_interview_answers_score_range"),
        Index("ix_mock_interview_answers_mock_interview", "mock_interview_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mock_interview_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mock_interviews.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    difficulty: Mapped[Optional[str]] = mapped_column(String(32))
    suggested_answer: Mapped[Optional[str]] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)

    mock_interview: Mapped[MockInterview] = relationship(back_populates="answers")


class AIAnalysis(TimestampMixin, Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (Index("ix_ai_analyses_user_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"), index=True)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    match_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    analysis_result: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("match_percentage >= 0 AND match_percentage <= 100", name="ck_ai_analyses_match_range"),
        Index("ix_ai_analyses_user_created_at", "user_id", "created_at"),
    )

    user: Mapped[User] = relationship(back_populates="ai_analyses")
    resume: Mapped[Optional[Resume]] = relationship(back_populates="ai_analyses")
    job: Mapped[Optional[Job]] = relationship(back_populates="ai_analyses")


class CandidateProfile(TimestampMixin, Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (Index("ix_candidate_profiles_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(1024))
    github_url: Mapped[Optional[str]] = mapped_column(String(1024))
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(1024))
    work_authorization: Mapped[Optional[str]] = mapped_column(String(120))
    requires_sponsorship: Mapped[Optional[bool]] = mapped_column(Boolean)
    demographic_sharing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    years_of_experience: Mapped[Optional[int]] = mapped_column(Integer)
    education_degree: Mapped[Optional[str]] = mapped_column(String(120))
    education_field: Mapped[Optional[str]] = mapped_column(String(120))
    education_school: Mapped[Optional[str]] = mapped_column(String(255))
    answers_json: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="candidate_profile")


class AutomationScenario(TimestampMixin, Base):
    __tablename__ = "automation_scenarios"
    __table_args__ = (
        Index("ix_automation_scenarios_company_field", "company", "field_key"),
        Index("ix_automation_scenarios_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, default="*", server_default="*")
    page_signature: Mapped[str] = mapped_column(String(255), nullable=False, default="*", server_default="*")
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    element_strategy_json: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value_source: Mapped[str] = mapped_column(String(64), nullable=False)
    static_value: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="HIGH", server_default="HIGH")
    confidence_reason: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[Optional[User]] = relationship(back_populates="automation_scenarios")


class AutomationRun(TimestampMixin, Base):
    __tablename__ = "automation_runs"
    __table_args__ = (
        Index("ix_automation_runs_user_status", "user_id", "status"),
        Index("ix_automation_runs_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), index=True)
    application_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[Optional[str]] = mapped_column(String(2048))
    current_url: Mapped[Optional[str]] = mapped_column(String(2048))
    page_title: Mapped[Optional[str]] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED", server_default="DISCOVERED")
    current_step: Mapped[Optional[str]] = mapped_column(String(120))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    requires_user_action: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    user_prompt: Mapped[Optional[str]] = mapped_column(Text)
    user_prompt_context_json: Mapped[Optional[str]] = mapped_column(Text)
    suggested_action_json: Mapped[Optional[str]] = mapped_column(Text)
    user_response_json: Mapped[Optional[str]] = mapped_column(Text)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(1024))
    scenarios_used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="automation_runs")
    job: Mapped[Optional[Job]] = relationship()
    application: Mapped[Optional[Application]] = relationship(back_populates="automation_runs")
    action_logs: Mapped[List[AutomationActionLog]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AutomationActionLog(Base):
    __tablename__ = "automation_action_logs"
    __table_args__ = (
        Index("ix_automation_action_logs_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action_source: Mapped[str] = mapped_column(String(32), nullable=False)
    step_name: Mapped[Optional[str]] = mapped_column(String(120))
    selector_used: Mapped[Optional[str]] = mapped_column(String(512))
    value_used: Mapped[Optional[str]] = mapped_column(Text)
    current_url: Mapped[Optional[str]] = mapped_column(String(2048))
    page_title: Mapped[Optional[str]] = mapped_column(String(512))
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="HIGH", server_default="HIGH")
    confidence_reason: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="success", server_default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped[AutomationRun] = relationship(back_populates="action_logs")


class AutomationSetting(TimestampMixin, Base):
    __tablename__ = "automation_settings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    schedule_interval: Mapped[str] = mapped_column(String(32), default="manual", server_default="manual")
    auto_submit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    allowed_companies_json: Mapped[Optional[str]] = mapped_column(Text)
    max_daily_applications: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    delay_between_actions_ms: Mapped[int] = mapped_column(Integer, default=800, server_default="800")

    user: Mapped[User] = relationship(back_populates="automation_setting")