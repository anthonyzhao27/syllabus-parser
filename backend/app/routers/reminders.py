from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.auth import AuthenticatedUser, get_current_user
from app.middleware.limiter import limiter
from app.models.schemas import ReminderRequest

router = APIRouter()


@router.post("/")
@limiter.limit("60/hour")
async def setup_reminders(
    request: Request,
    body: ReminderRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Set up SMS reminders for parsed events."""
    raise HTTPException(
        status_code=501,
        detail="SMS reminders not yet implemented",
    )
