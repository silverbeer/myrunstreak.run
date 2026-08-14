"""/import/activity — import one run from an uploaded activity file (SB-99).

Synchronous by design: a single GPX/TCX/JSON parses in milliseconds, so it
answers in the request rather than behind a job. Bulk zip import (SB-419) is
the one that needs a background job.

The upload is scoped to the authenticated user throughout — the source row, the
run and the track are all written under their user_id, never a caller-supplied one.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from backend.auth import authenticate_request
from backend.cache import invalidate_user
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from src.shared.geo import simplify_and_encode
from src.shared.importers import (
    ALLOWED_EXTENSIONS,
    DEFAULT_TIMEZONE,
    MAX_UPLOAD_BYTES,
    ActivityParseError,
    FileTooLargeError,
    UnsupportedFileError,
    parse_activity_file,
)
from src.shared.supabase_client import get_supabase_client
from src.shared.supabase_ops import RunsRepository, UsersRepository, activity_to_run_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["import"])

# The source_type imported runs are filed under (see the 20260814000000
# migration). One row per user, created on their first upload.
IMPORT_SOURCE_TYPE = "import"
IMPORT_SOURCE_LABEL = "file-import"

_READ_CHUNK = 64 * 1024

# Finer than the 6 m default used when caching a synced run's shape (SB-309).
# That default is tuned for the territory heatmap, and a synced run can always
# re-fetch its full track from SmashRun. An imported run cannot: this polyline
# is the only copy of its geometry, and it feeds the detail map too (SB-622).
# On a 3.2 km run this is the difference between 12 points and 62 — 215 bytes
# instead of 54, for a route that reads as a run rather than a polygon.
IMPORT_TRACK_TOLERANCE_M = 1.0


async def _read_capped(upload: UploadFile) -> bytes:
    """Read the upload, refusing anything over the cap.

    Read in chunks and stop at the first byte past the limit, so an oversized
    file costs one chunk of memory rather than its full size.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_READ_CHUNK):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise FileTooLargeError(f"File is larger than the {limit_mb} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/activity")
async def import_activity(
    user_id: UUID = Depends(authenticate_request),
    file: UploadFile = File(...),
    timezone: str = Form(DEFAULT_TIMEZONE),
) -> dict[str, Any]:
    """Import a single activity file (GPX, TCX or SmashRun JSON).

    Idempotent: re-uploading a file that is already imported reports
    ``status: "duplicate"`` and touches nothing.

    Returns:
        {status: imported|duplicate, activity_id, run_id, distance_km,
         duration_seconds, start_date_time_local, has_track}
    """
    filename = file.filename or ""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file name supplied, so the format can't be determined.",
        )

    try:
        content = await _read_capped(file)
        parsed = parse_activity_file(filename, content, timezone=timezone)
    except UnsupportedFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except ActivityParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    activity = parsed.activity
    supabase = get_supabase_client()
    runs_repo = RunsRepository(supabase)
    users_repo = UsersRepository(supabase)

    existing = runs_repo.get_run_by_activity_id(user_id, activity.activity_id)
    if existing:
        # Already imported. Reported as a normal outcome, not an error — a
        # re-upload is a reasonable thing for someone to do, and the UI needs
        # to say "already imported" rather than show a failure (SB-418).
        return {
            "status": "duplicate",
            "activity_id": activity.activity_id,
            "run_id": existing["id"],
            "distance_km": float(existing["distance_km"]),
            "duration_seconds": float(existing["duration_seconds"]),
            "start_date_time_local": existing["start_date_time_local"],
            "has_track": bool(existing.get("has_gps_data")),
        }

    source_id = users_repo.get_or_create_source(
        user_id, IMPORT_SOURCE_TYPE, source_username=IMPORT_SOURCE_LABEL
    )

    run_dict = activity_to_run_dict(activity, user_id, source_id)
    # Record the zone the timestamps were read into, so a later re-derivation
    # of the local date doesn't have to guess what import assumed.
    run_dict["timezone"] = timezone
    run = runs_repo.upsert_run(user_id, source_id, run_dict)
    run_id = UUID(run["id"])

    stored_track = False
    if parsed.has_track:
        polyline, point_count = simplify_and_encode(
            parsed.latitudes, parsed.longitudes, tolerance_m=IMPORT_TRACK_TOLERANCE_M
        )
        if polyline:
            runs_repo.upsert_track(run_id, polyline, point_count)
            stored_track = True

    # Streak and totals are read from the aggregation row, which stays frozen
    # until recalculated — the same call the SmashRun sync makes after upserting.
    try:
        runs_repo.recalculate_user_stats(user_id, timezone=timezone)
    except Exception as exc:  # noqa: BLE001 - stats refresh must not fail the import
        logger.warning(f"recalculate_user_stats failed after import for {user_id}: {exc}")

    await invalidate_user(user_id)

    logger.info(f"Imported {filename} for user {user_id} as run {run_id}")
    return {
        "status": "imported",
        "activity_id": activity.activity_id,
        "run_id": str(run_id),
        "distance_km": round(activity.distance, 3),
        "duration_seconds": round(activity.duration, 2),
        "start_date_time_local": activity.start_date_time_local.isoformat(),
        "has_track": stored_track,
    }


@router.get("/formats")
async def import_formats(
    _user_id: UUID = Depends(authenticate_request),
) -> dict[str, Any]:
    """What the importer accepts — so the UI states one set of limits, not its own copy."""
    return {
        "extensions": list(ALLOWED_EXTENSIONS),
        "max_bytes": MAX_UPLOAD_BYTES,
        "default_timezone": DEFAULT_TIMEZONE,
    }
