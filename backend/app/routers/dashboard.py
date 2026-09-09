from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import DashboardResponse
from ..services.dashboard import get_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["Analytics"])


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Get career dashboard analytics",
    description="Returns application totals, upcoming interviews, highest-priority skill gaps, and recent activity for the authenticated user.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def dashboard(current_user: User = Depends(get_current_user), database: Session = Depends(get_db)) -> DashboardResponse:
    return get_dashboard(current_user.id, database)