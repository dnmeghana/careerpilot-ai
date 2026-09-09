from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers.auth import router as auth_router
from .routers.applications import router as applications_router
from .routers.analysis import router as analysis_router
from .routers.assistant import router as assistant_router
from .routers.dashboard import router as dashboard_router
from .routers.jobs import router as jobs_router
from .routers.interviews import router as interviews_router
from .routers.mock_interviews import router as mock_interviews_router
from .routers.resumes import router as resumes_router
from .schemas import HealthResponse

OPENAPI_TAGS = [
    {"name": "Authentication", "description": "Register accounts and obtain access tokens."},
    {"name": "Users", "description": "Authenticated user profile information."},
    {"name": "Resumes", "description": "Upload and manage resumes owned by the authenticated user."},
    {"name": "Jobs", "description": "Track job opportunities owned by the authenticated user."},
    {"name": "Applications", "description": "Track application status and recruiter details for saved jobs."},
    {"name": "Analysis", "description": "Compare a user-owned resume with a user-owned job."},
    {"name": "Skills", "description": "Review skill gaps and recommended learning areas."},
    {"name": "Interviews", "description": "Generate and manage interview preparation plans."},
    {"name": "Mock Interviews", "description": "Run practice interviews and submit answers for evaluation."},
    {"name": "AI Assistant", "description": "Ask career questions using the authenticated user's workspace context."},
    {"name": "Analytics", "description": "View application, interview, and skill-gap dashboard metrics."},
    {"name": "Health", "description": "Service availability checks."},
]

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for CareerPilot. Protected endpoints require a bearer access token.",
    openapi_tags=OPENAPI_TAGS,
)
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(analysis_router)
app.include_router(assistant_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(interviews_router)
app.include_router(mock_interviews_router)
app.include_router(resumes_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get(
    "/api/health",
    tags=["Health"],
    summary="Check API availability",
    description="Returns a lightweight response when the API process is available. This endpoint does not require authentication.",
    response_model=HealthResponse,
    status_code=200,
)
def health_check() -> HealthResponse:
    return {"status": "ok", "service": settings.app_name}
