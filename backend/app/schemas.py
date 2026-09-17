from datetime import date, datetime
import json
from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator, computed_field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

    @field_validator("confirm_password")
    @classmethod
    def passwords_must_match(cls, value: str, info) -> str:
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    dev_reset_url: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("confirm_password")
    @classmethod
    def passwords_must_match(cls, value: str, info) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return value


class ResetPasswordResponse(BaseModel):
    message: str


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    extracted_text: str | None = None
    extracted_text_preview: str = ""


class JobBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str | None) -> str | None:
        return str(TypeAdapter(AnyHttpUrl).validate_python(value)) if value is not None else None

    @field_validator("title", "company")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be blank")
        return value

    @field_validator("description", "location")
    @classmethod
    def optional_text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class JobCreate(JobBase):
    pass


class JobUpdate(JobBase):
    pass


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


INTERVIEW_TYPES = ("HR", "Behavioral", "Technical", "System Design")


class InterviewCreate(BaseModel):
    job_id: UUID
    interview_type: str
    resume_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=12000)

    @field_validator("interview_type")
    @classmethod
    def interview_type_must_be_known(cls, value: str) -> str:
        value = value.strip().title()
        if value not in INTERVIEW_TYPES:
            raise ValueError(f"Interview type must be one of: {', '.join(INTERVIEW_TYPES)}")
        return value


class InterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str
    category: str | None = None
    difficulty: str | None = None
    suggested_answer: str | None = None
    completed: bool


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    job_title: str
    company: str
    interview_type: str
    scheduled_at: datetime
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    questions: list[InterviewQuestionResponse]


class InterviewUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=12000)
    question_id: UUID | None = None
    completed: bool | None = None


class InterviewRegenerate(BaseModel):
    resume_id: UUID | None = None


class MockInterviewCreate(BaseModel):
    job_id: UUID | None = None
    interview_type: str = "Behavioral"
    resume_id: UUID | None = None

    @field_validator("interview_type")
    @classmethod
    def mock_interview_type_must_be_known(cls, value: str) -> str:
        value = value.strip().title()
        if value not in INTERVIEW_TYPES:
            raise ValueError(f"Interview type must be one of: {', '.join(INTERVIEW_TYPES)}")
        return value


class MockInterviewAnswerCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)


class MockInterviewQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question: str
    category: str | None = None
    difficulty: str | None = None
    suggested_answer: str | None = None
    answer: str
    score: float | None = None
    feedback: dict[str, object] | None = None


class MockInterviewResponse(BaseModel):
    id: UUID
    job_id: UUID | None = None
    job_title: str | None = None
    company: str | None = None
    interview_type: str
    started_at: datetime
    completed_at: datetime | None = None
    overall_score: float | None = None
    current_question: int
    questions: list[MockInterviewQuestionResponse]
    strong_areas: list[str] = []
    weak_areas: list[str] = []
    recommendations: list[str] = []


APPLICATION_STATUSES = (
    "wishlist", "applied", "screening", "interview", "technical_interview", "final_round", "offer", "rejected"
)


class ApplicationBase(BaseModel):
    job_id: UUID
    status: str = "wishlist"
    application_date: date | None = None
    interview_date: datetime | None = None
    salary: float | None = Field(default=None, ge=0)
    recruiter_name: str | None = Field(default=None, max_length=120)
    recruiter_email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=12000)

    @field_validator("status")
    @classmethod
    def status_must_be_known(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in APPLICATION_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(APPLICATION_STATUSES)}")
        return value


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(ApplicationBase):
    pass


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company: str
    title: str
    location: str | None = None
    created_at: datetime
    updated_at: datetime
    automation_status: str | None = None
    last_automation_attempt: datetime | None = None


class ResumeJobAnalysisRequest(BaseModel):
    resume_id: UUID
    job_id: UUID


class ResumeJobAnalysisResponse(BaseModel):
    id: UUID
    resume_id: UUID
    job_id: UUID
    match_percentage: float
    matching_skills: list[str]
    missing_skills: list[str]
    missing_keywords: list[str]
    relevant_experience_keywords: list[str]
    recommended_skills: list[str]
    resume_improvement_suggestions: list[str]
    created_at: datetime


class SkillPriority(BaseModel):
    skill: str
    priority: int


class SkillGapResponse(BaseModel):
    has_analysis: bool
    analysis_id: UUID | None = None
    resume_id: UUID | None = None
    job_id: UUID | None = None
    resume_name: str | None = None
    job_title: str | None = None
    company: str | None = None
    match_percentage: float = 0
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    skill_priorities: list[SkillPriority] = []
    recommended_learning_areas: list[str] = []
    created_at: datetime | None = None


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    job_id: UUID | None = None
    interview_id: UUID | None = None


class AssistantChatResponse(BaseModel):
    response: str
    context_labels: list[str] = []


class DashboardStats(BaseModel):
    total_applications: int
    interviews: int
    offers: int
    rejections: int
    success_rate: float


class DashboardApplication(BaseModel):
    id: UUID
    company: str
    role: str
    status: str
    updated_at: datetime


class DashboardInterview(BaseModel):
    id: UUID
    company: str
    role: str
    type: str
    scheduled_at: datetime


class DashboardSkillGap(BaseModel):
    id: UUID
    skill: str
    role: str
    company: str
    priority: int


class DashboardActivity(BaseModel):
    date: datetime
    status: str
    company: str


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_applications: list[DashboardApplication]
    upcoming_interviews: list[DashboardInterview]
    skill_gaps: list[DashboardSkillGap]
    activity: list[DashboardActivity]


class HealthResponse(BaseModel):
    status: str
    service: str


# ============================================================================
# V2 Automation Schemas
# ============================================================================

AUTOMATION_STATES = (
    "DISCOVERED",
    "JOB_SELECTED",
    "APPLICATION_STARTED",
    "FORM_IN_PROGRESS",
    "WAITING_FOR_USER",
    "UNKNOWN_SCENARIO",
    "AI_RESOLUTION",
    "FORM_COMPLETED",
    "SUBMISSION_REVIEW",
    "SUBMITTED",
    "FAILED",
    "PAUSED",
)


class CandidateProfileBase(BaseModel):
    phone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    linkedin_url: str | None = Field(default=None, max_length=1024)
    github_url: str | None = Field(default=None, max_length=1024)
    portfolio_url: str | None = Field(default=None, max_length=1024)
    work_authorization: str | None = Field(default=None, max_length=120)
    requires_sponsorship: bool | None = None
    demographic_sharing_opt_in: bool = False
    years_of_experience: int | None = Field(default=None, ge=0, le=70)
    education_degree: str | None = Field(default=None, max_length=120)
    education_field: str | None = Field(default=None, max_length=120)
    education_school: str | None = Field(default=None, max_length=255)
    answers_json: str | None = None


class CandidateProfileCreate(CandidateProfileBase):
    pass


class CandidateProfileUpdate(CandidateProfileBase):
    pass


class CandidateProfileResponse(CandidateProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class AutomationScenarioBase(BaseModel):
    company: str = Field(default="*", max_length=255)
    page_signature: str = Field(default="*", max_length=255)
    field_key: str = Field(min_length=1, max_length=255)
    element_strategy_json: str
    action_type: str = Field(min_length=1, max_length=32)
    value_source: str = Field(min_length=1, max_length=64)
    static_value: str | None = None
    confidence: str = "HIGH"
    confidence_reason: str | None = None
    is_active: bool = True
    is_approved: bool = True


class AutomationScenarioCreate(AutomationScenarioBase):
    pass


class AutomationScenarioUpdate(BaseModel):
    element_strategy_json: str | None = None
    action_type: str | None = None
    value_source: str | None = None
    static_value: str | None = None
    confidence: str | None = None
    confidence_reason: str | None = None
    is_active: bool | None = None
    is_approved: bool | None = None


class AutomationScenarioResponse(AutomationScenarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    version: int
    times_used: int
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AutomationActionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    action_type: str
    action_source: str
    step_name: str | None = None
    selector_used: str | None = None
    value_used: str | None = None
    current_url: str | None = None
    page_title: str | None = None
    confidence: str
    confidence_reason: str | None = None
    result: str
    error_message: str | None = None
    screenshot_path: str | None = None
    created_at: datetime


class SelectedJobIdentitySchema(BaseModel):
    company: str
    exact_title: str
    job_url: str
    job_id: UUID | None = None
    requisition_id: str | None = None
    location: str | None = None
    source: str = "portal"


class AutomationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    job_id: UUID | None = None
    application_id: UUID | None = None
    company: str
    job_title: str
    job_url: str | None = None
    current_url: str | None = None
    page_title: str | None = None
    status: str
    current_step: str | None = None
    error_message: str | None = None
    requires_user_action: bool = False
    user_prompt: str | None = None
    user_prompt_context_json: str | None = None
    suggested_action_json: str | None = None
    user_response_json: str | None = None
    screenshot_path: str | None = None
    scenarios_used_count: int = 0
    selected_job_identity: SelectedJobIdentitySchema | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AutomationRunDetailResponse(AutomationRunResponse):
    action_logs: list[AutomationActionLogResponse] = []


class AutomationSettingUpdate(BaseModel):
    is_enabled: bool | None = None
    schedule_interval: str | None = Field(default=None, max_length=32)
    auto_submit: bool | None = None
    allowed_companies_json: str | None = None
    max_daily_applications: int | None = Field(default=None, ge=1, le=100)
    delay_between_actions_ms: int | None = Field(default=None, ge=100, le=5000)


class AutomationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    is_enabled: bool
    schedule_interval: str
    auto_submit: bool
    allowed_companies_json: str | None = None
    max_daily_applications: int
    delay_between_actions_ms: int
    created_at: datetime
    updated_at: datetime


class AutomationTriggerRequest(BaseModel):
    job_id: UUID | None = None
    job_url: str | None = None
    company: str | None = None
    job_title: str | None = None
    requisition_id: str | None = None
    location: str | None = None
    source: str = "manual"


class AutomationInterventionRequest(BaseModel):
    action: str = Field(pattern="^(approve|edit|reject|pause)$")
    value: str | None = None
    remember_scenario: bool = True


class JobMatchScoreRequest(BaseModel):
    target_role: str
    candidate_title: str
    candidate_description: str | None = None
    candidate_location: str | None = None
    candidate_skills: list[str] = []
    user_skills: list[str] = []
    user_location: str | None = None
    user_experience_years: int | None = None
    employment_type_pref: str | None = None


class JobMatchScoreResponse(BaseModel):
    match_score: float
    is_match: bool
    title_score: float
    skills_score: float
    location_score: float
    experience_score: float
    normalized_target_title: str
    normalized_job_title: str
    reasons: list[str] = []
    breakdown: dict[str, Any] = {}
    score_breakdown: dict[str, Any] = {}


class JobSearchConfigRequest(BaseModel):
    desired_job_title: str = Field(min_length=1, max_length=255)
    desired_location: str = Field(min_length=1, max_length=255)
    years_of_experience: int = Field(ge=0, le=50, default=0)
    platform_search_url: str = Field(min_length=5, max_length=2048)
    specific_company: str | None = Field(default=None, max_length=255)
    active_resume_id: UUID | None = None
    max_jobs_to_discover: int = Field(ge=1, le=50, default=10)
    min_match_score: float = Field(ge=0.0, le=100.0, default=50.0)
    skip_already_applied: bool = True
    schedule_interval: str = Field(default="manual", max_length=32)


class JobSearchConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    desired_job_title: str
    desired_location: str
    years_of_experience: int
    platform_search_url: str
    specific_company: str | None = None
    active_resume_id: UUID | None = None
    max_jobs_to_discover: int
    min_match_score: float = 50.0
    skip_already_applied: bool = True
    schedule_interval: str = "manual"
    is_active: bool
    last_searched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DiscoveredJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    config_id: UUID | None = None
    company: str
    exact_title: str
    job_url: str
    location: str | None = None
    requisition_id: str | None = None
    experience_raw: str | None = None
    platform: str
    raw_description: str | None = None
    match_score: float
    title_score: float
    skills_score: float
    location_score: float
    experience_score: float
    is_matched: bool
    match_reasons_json: str | None = None
    match_breakdown_json: str | None = None
    matched_skills_json: str | None = None
    missing_skills_json: str | None = None
    status: str
    automation_run_id: UUID | None = None
    discovered_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def matched_skills(self) -> list[str]:
        if not self.matched_skills_json:
            return []
        try:
            return json.loads(self.matched_skills_json)
        except Exception:
            return []

    @computed_field
    @property
    def missing_skills(self) -> list[str]:
        if not self.missing_skills_json:
            return []
        try:
            return json.loads(self.missing_skills_json)
        except Exception:
            return []


class JobDiscoveryTriggerRequest(BaseModel):
    config_id: UUID | None = None
    search_url: str | None = None
    max_results: int | None = Field(default=None, ge=1, le=50)
    min_match_score: float | None = Field(default=None, ge=0.0, le=100.0)
    skip_already_applied: bool | None = None


class JobDiscoveryResultResponse(BaseModel):
    total_discovered: int
    total_matched: int
    new_candidates_saved: int
    jobs: list[DiscoveredJobResponse] = []