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

# Supabase storage list() returns at most this many objects per call, so we
# page through with an explicit limit/offset until a short page comes back.
_LIST_PAGE_SIZE = 100


def _collect_object_paths(bucket, prefix: str) -> list[str]:
    """Recursively collect every object path under ``prefix``.

    Supabase storage ``list`` returns at most ~100 entries per call and never
    descends into nested "folders", so we paginate each prefix and recurse into
    any entry that looks like a folder (no file ``id``).
    """
    paths: list[str] = []
    offset = 0

    while True:
        page = (
            bucket.list(
                prefix,
                {"limit": _LIST_PAGE_SIZE, "offset": offset},
            )
            or []
        )

        for entry in page:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue

            child = f"{prefix}/{name}" if prefix else name

            # A real object has an ``id``; folder placeholders do not. Recurse
            # into folders so deeply nested files are not orphaned.
            if entry.get("id"):
                paths.append(child)
            else:
                paths.extend(_collect_object_paths(bucket, child))

        if len(page) < _LIST_PAGE_SIZE:
            break
        offset += _LIST_PAGE_SIZE

    return paths


def _remove_storage_objects_sync(user_id: str, access_token: str) -> None:
    """Delete every object under the user's storage prefix.

    Raises on failure so the caller can abort auth-user deletion and leave the
    operation safely retryable instead of orphaning PII-bearing files.
    """
    client = get_authenticated_client(access_token)
    bucket = client.storage.from_(BUCKET_NAME)

    paths = _collect_object_paths(bucket, user_id)
    if paths:
        bucket.remove(paths)

    # Verify the prefix is actually empty before reporting success. Some
    # failure modes (partial removes, silent errors) leave objects behind.
    remaining = _collect_object_paths(bucket, user_id)
    if remaining:
        raise RuntimeError(
            f"{len(remaining)} storage object(s) remain under " f"{user_id} after purge"
        )


def _delete_auth_user_sync(user_id: str) -> None:
    client = get_service_role_client()
    client.auth.admin.delete_user(user_id)


@router.delete("/", status_code=204)
@limiter.limit("5/hour")
async def delete_account(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Delete the caller's account, storage objects, and cascaded DB rows.

    Storage objects are purged first. If that fails we abort *before* deleting
    the auth user, so the caller can retry instead of leaving permanently
    orphaned files that contain user PII.
    """
    try:
        await run_in_threadpool(
            _remove_storage_objects_sync, user.id, user.access_token
        )
    except Exception as exc:
        logger.exception(
            "Storage cleanup failed during account deletion for user=%s; "
            "aborting before auth-user deletion",
            user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Account deletion failed while clearing your files. "
            "Please try again.",
        ) from exc

    try:
        await run_in_threadpool(_delete_auth_user_sync, user.id)
    except Exception as exc:
        logger.exception("Failed to delete auth user %s", user.id)
        raise HTTPException(
            status_code=500,
            detail="Account deletion failed. Please try again.",
        ) from exc

    return Response(status_code=204)
