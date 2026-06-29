"""Self-serve account deletion."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.middleware.auth import AuthenticatedUser, get_current_user
from app.middleware.limiter import limiter
from app.models.db import get_authenticated_client, get_service_role_client

logger = logging.getLogger(__name__)

router = APIRouter()

BUCKET_NAME = "syllabi"


def _remove_storage_objects_sync(user_id: str, access_token: str) -> None:
    """Delete every object under the user's storage prefix. Best-effort."""
    client = get_authenticated_client(access_token)
    bucket = client.storage.from_(BUCKET_NAME)

    listing = bucket.list(user_id) or []
    paths: list[str] = []
    for entry in listing:
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str) and name:
            paths.append(f"{user_id}/{name}")

    if paths:
        bucket.remove(paths)


def _delete_auth_user_sync(user_id: str) -> None:
    client = get_service_role_client()
    client.auth.admin.delete_user(user_id)


@router.delete("/", status_code=204)
@limiter.limit("5/hour")
async def delete_account(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Delete the caller's account, storage objects, and cascaded DB rows."""
    try:
        await run_in_threadpool(
            _remove_storage_objects_sync, user.id, user.access_token
        )
    except Exception:
        logger.warning(
            "Storage cleanup failed during account deletion for user=%s",
            user.id,
            exc_info=True,
        )

    try:
        await run_in_threadpool(_delete_auth_user_sync, user.id)
    except Exception as exc:
        logger.exception("Failed to delete auth user %s", user.id)
        raise HTTPException(
            status_code=500, detail="Account deletion failed. Please try again."
        ) from exc

    return Response(status_code=204)
