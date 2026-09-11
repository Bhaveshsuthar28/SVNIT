from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ClassDistribution, ConfidenceStatistics, TimelineResponse
from app.services.analytics_service import (
    get_class_distribution,
    get_confidence_statistics,
    get_timeline,
)

router = APIRouter()


@router.get("/analytics/classes", response_model=ClassDistribution)
def class_analytics(db: Session = Depends(get_db)) -> ClassDistribution:
    return get_class_distribution(db)


@router.get("/analytics/timeline", response_model=TimelineResponse)
def timeline(
    grouped_class: str | None = Query(default=None),
    start_time: float | None = Query(default=None, ge=0),
    end_time: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    if start_time is not None and end_time is not None and end_time < start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_time must be greater than or equal to start_time.",
        )
    return get_timeline(db, grouped_class=grouped_class, start_time=start_time, end_time=end_time)


@router.get("/analytics/confidence", response_model=ConfidenceStatistics)
def confidence(
    threshold: float = Query(default=0.3),
    db: Session = Depends(get_db),
) -> ConfidenceStatistics:
    if threshold < 0 or threshold > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confidence threshold must be between 0 and 1.",
        )
    return get_confidence_statistics(db, threshold=threshold)
