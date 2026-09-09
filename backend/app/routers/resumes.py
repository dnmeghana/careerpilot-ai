from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pypdf.errors import PdfReadError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import Resume, User
from ..schemas import ResumeResponse
from ..services.resume_parser import extract_text_from_pdf

router = APIRouter(prefix="/api/resumes", tags=["Resumes"])


def to_response(resume: Resume) -> ResumeResponse:
    text = resume.extracted_text or ""
    return ResumeResponse.model_validate({
        "id": resume.id,
        "filename": resume.filename,
        "created_at": resume.created_at,
        "updated_at": resume.updated_at,
        "is_active": resume.is_active,
        "extracted_text": text,
        "extracted_text_preview": text[:280],
    })


def owned_resume(resume_id: UUID, user_id: UUID, database: Session) -> Resume:
    resume = database.scalar(select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id))
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a resume",
    description="Upload a PDF resume up to the configured size limit, extract its text, and make it the user's active resume.",
    responses={
        400: {"description": "The file is not a readable PDF."},
        401: {"description": "Authentication token is missing or invalid."},
        413: {"description": "The uploaded file exceeds the configured size limit."},
        415: {"description": "The uploaded file is not a PDF."},
    },
)
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ResumeResponse:
    settings = get_settings()
    filename = Path(file.filename or "resume.pdf").name
    if file.content_type != "application/pdf" or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files are accepted")

    max_bytes = settings.resume_max_size_mb * 1024 * 1024
    content = bytearray()
    while len(content) <= max_bytes:
        chunk = await file.read(min(1024 * 1024, max_bytes + 1 - len(content)))
        if not chunk:
            break
        content.extend(chunk)
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Resume must be {settings.resume_max_size_mb} MB or smaller")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is not a valid PDF")
    try:
        extracted_text = extract_text_from_pdf(bytes(content))
    except (PdfReadError, ValueError, OSError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The PDF could not be read") from error

    upload_dir = Path(settings.resume_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{current_user.id}_{uuid4()}.pdf"
    stored_path.write_bytes(content)
    database.execute(update(Resume).where(Resume.user_id == current_user.id).values(is_active=False))
    resume = Resume(user_id=current_user.id, filename=filename, file_path=str(stored_path), extracted_text=extracted_text, is_active=True)
    database.add(resume)
    try:
        database.commit()
    except Exception:
        database.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    database.refresh(resume)
    return to_response(resume)


@router.get(
    "",
    response_model=list[ResumeResponse],
    summary="List resumes",
    description="List all resumes owned by the authenticated user, newest first.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def list_resumes(current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[ResumeResponse]:
    resumes = database.scalars(select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc())).all()
    return [to_response(resume) for resume in resumes]


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get a resume",
    description="Return one resume when it belongs to the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Resume not found."}},
)
def get_resume(resume_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ResumeResponse:
    return to_response(owned_resume(resume_id, current_user.id, database))


@router.put(
    "/{resume_id}/active",
    response_model=ResumeResponse,
    summary="Set the active resume",
    description="Make a user-owned resume active and deactivate the user's other resumes.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Resume not found."}},
)
def set_active_resume(resume_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> ResumeResponse:
    resume = owned_resume(resume_id, current_user.id, database)
    database.execute(update(Resume).where(Resume.user_id == current_user.id).values(is_active=False))
    resume.is_active = True
    database.commit()
    database.refresh(resume)
    return to_response(resume)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resume",
    description="Delete a user-owned resume and its stored PDF file.",
    responses={401: {"description": "Authentication token is missing or invalid."}, 404: {"description": "Resume not found."}},
)
def delete_resume(resume_id: UUID, current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> None:
    resume = owned_resume(resume_id, current_user.id, database)
    Path(resume.file_path).unlink(missing_ok=True)
    database.delete(resume)
    database.commit()
