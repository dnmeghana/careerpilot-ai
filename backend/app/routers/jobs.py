from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Job, User
from ..schemas import JobCreate, JobResponse, JobUpdate

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def owned_job(job_id: UUID, user_id: UUID, database: Session) -> Job:
    job = database.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job",
    description="Save a job opportunity for the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def create_job(payload: JobCreate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> Job:
    job = Job(user_id=current_user.id, **payload.model_dump())
    database.add(job)
    database.commit()
    database.refresh(job)
    return job


@router.get(
    "",
    response_model=list[JobResponse],
    summary="List jobs",
    description="List job opportunities owned by the authenticated user, newest first.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def list_jobs(current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[Job]:
    return list(database.scalars(select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())).all())


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get a job",
    description="Return one job when it belongs to the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Job not found."}},
)
def get_job(job_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> Job:
    return owned_job(job_id, current_user.id, database)


@router.put(
    "/{job_id}",
    response_model=JobResponse,
    summary="Update a job",
    description="Replace the editable fields of a user-owned job opportunity.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Job not found."}},
)
def update_job(job_id: UUID, payload: JobUpdate, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> Job:
    job = owned_job(job_id, current_user.id, database)
    for field, value in payload.model_dump().items():
        setattr(job, field, value)
    database.commit()
    database.refresh(job)
    return job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job",
    description="Delete a user-owned job opportunity and its dependent applications.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Job not found."}},
)
def delete_job(job_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> None:
    job = owned_job(job_id, current_user.id, database)
    database.delete(job)
    database.commit()