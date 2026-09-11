from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import FrameResponse, TrackDetails, TrajectoryListResponse, TrajectoryResponse
from app.services.trajectory_service import (
    get_frame,
    get_frame_bounds,
    get_track_details,
    list_trajectories,
)

router = APIRouter()


@router.get("/frames/{frame}", response_model=FrameResponse)
def read_frame(frame: int, db: Session = Depends(get_db)) -> FrameResponse:
    min_frame, max_frame = get_frame_bounds(db)
    if min_frame is None or max_frame is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No trajectory records are available.",
        )
    if frame < min_frame or frame > max_frame:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Frame must be between {min_frame} and {max_frame}.",
        )
    payload = get_frame(db, frame)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame {frame} was not found.",
        )
    return payload


@router.get("/trajectories", response_model=None)
def read_trajectories(
    track_id: int | None = Query(default=None),
    grouped_class: str | None = Query(default=None),
    start_frame: int | None = Query(default=None, ge=0),
    end_frame: int | None = Query(default=None, ge=0),
    start_time: float | None = Query(default=None, ge=0),
    end_time: float | None = Query(default=None, ge=0),
    min_confidence: float | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> TrajectoryListResponse | TrajectoryResponse:
    if min_confidence is not None and (min_confidence < 0 or min_confidence > 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confidence threshold must be between 0 and 1.",
        )
    if start_frame is not None and end_frame is not None and end_frame < start_frame:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_frame must be greater than or equal to start_frame.",
        )
    if start_time is not None and end_time is not None and end_time < start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be greater than or equal to start_time.",
        )
    result = list_trajectories(
        db,
        track_id=track_id,
        grouped_class=grouped_class,
        start_frame=start_frame,
        end_frame=end_frame,
        start_time=start_time,
        end_time=end_time,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )
    if track_id is not None and isinstance(result, TrajectoryListResponse) and result.total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track ID {track_id} was not found.",
        )
    return result


@router.get("/trajectories/{track_id}", response_model=TrackDetails)
def read_track(track_id: int, db: Session = Depends(get_db)) -> TrackDetails:
    details = get_track_details(db, track_id)
    if details is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track ID {track_id} was not found.",
        )
    return details
