from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SummaryResponse
from app.services.analytics_service import get_summary
from app.services.trajectory_service import get_frame_bounds

router = APIRouter()


@router.get("/summary", response_model=SummaryResponse)
def summary(
    frame: int | None = Query(default=None, ge=0),
    time_sec: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> SummaryResponse:
    min_frame, max_frame = get_frame_bounds(db)
    if frame is not None and min_frame is not None and max_frame is not None:
        if frame < min_frame or frame > max_frame:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Frame must be between {min_frame} and {max_frame}.",
            )
    return get_summary(db, frame=frame, time_sec=time_sec)
