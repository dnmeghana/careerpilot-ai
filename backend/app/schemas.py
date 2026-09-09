from datetime import date, datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator


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