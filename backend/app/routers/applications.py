from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Application, Job, User
from ..schemas import APPLICATION_STATUSES, ApplicationCreate, ApplicationResponse, ApplicationUpdate

router = APIRouter(prefix="/api/applications", tags=["Applications"])


def owned_application(application_id: UUID, user_id: UUID, database: Session) -> Application:
    application = database.scalar(select(Application).where(Application.id == application_id, Application.user_id == user_id).options(joinedload(Application.job)))
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def owned_job(job_id: UUID, user_id: UUID, database: Session) -> Job:
    job = database.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def to_response(application: Application) -> ApplicationResponse:
    return ApplicationResponse.model_validate({
        **{
            field: getattr(application, field)
            for field in (
                "id",
                "job_id",
                "status",
                "application_date",
                "interview_date",
                "salary",
                "recruiter_name",
                "recruiter_email",
                "notes",
                "created_at",
                "updated_at",
                "automation_status",
                "last_automation_attempt",
            )
        },
        "company": application.job.company,
        "title": application.job.title,
        "location": application.job.location,
    })


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an application",
    description="Start tracking a user-owned job application. A user can track a job only once.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The job was not found or is not owned by the user."}, 409: {"description": "The user is already tracking this job."}},
)
def create_application(payload: ApplicationCreate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ApplicationResponse:
    owned_job(payload.job_id, current_user.id, database)
    if database.scalar(select(Application).where(Application.user_id == current_user.id, Application.job_id == payload.job_id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already tracking this job")
    application = Application(user_id=current_user.id, **payload.model_dump())
    database.add(application)
    database.commit()
    database.refresh(application)
    application.job = owned_job(application.job_id, current_user.id, database)
    return to_response(application)


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List applications",
    description="List the authenticated user's applications with optional search, status filtering, and sorting.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 422: {"description": "The status or sort query parameter is invalid."}},
)
def list_applications(search: str | None = Query(default=None, max_length=120), status_filter: str | None = Query(default=None, alias="status"), sort: str = Query(default="updated", pattern="^(updated|application_date|salary|company)$"), current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[ApplicationResponse]:
    query = select(Application).join(Application.job).where(Application.user_id == current_user.id).options(joinedload(Application.job))
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Job.title.ilike(term) | Job.company.ilike(term) | Application.notes.ilike(term))
    if status_filter:
        if status_filter not in APPLICATION_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown application status")
        query = query.where(Application.status == status_filter)
    sort_column = {"updated": Application.updated_at, "application_date": Application.application_date, "salary": Application.salary, "company": Job.company}[sort]
    query = query.order_by(sort_column.desc().nullslast(), Application.created_at.desc())
    return [to_response(application) for application in database.scalars(query).unique().all()]


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get an application",
    description="Return one application when it belongs to the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Application not found."}},
)
def get_application(application_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ApplicationResponse:
    return to_response(owned_application(application_id, current_user.id, database))


@router.put(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Update an application",
    description="Replace the editable fields of a user-owned application and optionally associate it with another user-owned job.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "The application or target job was not found."}, 409: {"description": "The user is already tracking the target job."}},
)
def update_application(application_id: UUID, payload: ApplicationUpdate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ApplicationResponse:
    application = owned_application(application_id, current_user.id, database)
    owned_job(payload.job_id, current_user.id, database)
    if database.scalar(select(Application).where(Application.user_id == current_user.id, Application.job_id == payload.job_id, Application.id != application.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already tracking this job")
    for field, value in payload.model_dump().items():
        setattr(application, field, value)
    database.commit()
    database.refresh(application)
    application.job = owned_job(application.job_id, current_user.id, database)
    return to_response(application)


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an application",
    description="Delete a user-owned application record.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Application not found."}},
)
def delete_application(application_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> None:
    application = owned_application(application_id, current_user.id, database)
    database.delete(application)
    database.commit()