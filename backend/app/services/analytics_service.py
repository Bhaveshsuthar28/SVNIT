from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import TrajectoryRecord
from app.schemas import (
    ClassCount,
    ClassDistribution,
    ConfidenceStatistics,
    MetadataResponse,
    SummaryResponse,
    TimelinePoint,
    TimelineResponse,
)
from app.services.trajectory_service import get_frame_bounds, get_time_bounds, resolve_frame_for_time

AVAILABLE_SOURCE_FIELDS = [
    "frame",
    "time_sec",
    "track_id",
    "grouped_class",
    "source_class",
    "confidence",
    "bbox",
    "cx",
    "cy",
    "utm_easting",
    "utm_northing",
    "speed_kmh",
    "heading_angle",
]


def get_metadata(db: Session) -> MetadataResponse:
    settings = get_settings()
    total_records = db.execute(select(func.count()).select_from(TrajectoryRecord)).scalar_one()
    unique_tracks = db.execute(select(func.count(func.distinct(TrajectoryRecord.track_id)))).scalar_one()
    first_frame, last_frame = get_frame_bounds(db)
    start_time, end_time = get_time_bounds(db)
    frames = 0
    if first_frame is not None and last_frame is not None:
        frames = db.execute(select(func.count(func.distinct(TrajectoryRecord.frame)))).scalar_one()

    duration = None
    fps = None
    if start_time is not None and end_time is not None:
        duration = end_time - start_time
        if duration > 0 and frames > 1:
            fps = int(round((frames - 1) / duration))

    classes = db.execute(
        select(TrajectoryRecord.grouped_class)
        .distinct()
        .order_by(TrajectoryRecord.grouped_class)
    ).scalars().all()

    available: list[str] = []
    unavailable: list[str] = []
    for field in AVAILABLE_SOURCE_FIELDS:
        column = getattr(TrajectoryRecord, field)
        non_null = db.execute(
            select(func.count()).select_from(TrajectoryRecord).where(column.is_not(None))
        ).scalar_one()
        if non_null > 0:
            available.append(field)
        else:
            unavailable.append(field)

    return MetadataResponse(
        dataset=settings.dataset_name,
        total_records=total_records,
        unique_tracks=unique_tracks,
        frames=frames,
        first_frame=first_frame,
        last_frame=last_frame,
        start_time_sec=start_time,
        end_time_sec=end_time,
        duration_seconds=duration,
        fps=fps,
        classes=list(classes),
        available=available,
        unavailable=unavailable,
    )


def get_summary(
    db: Session,
    frame: int | None = None,
    time_sec: float | None = None,
) -> SummaryResponse:
    total_tracks = db.execute(select(func.count(func.distinct(TrajectoryRecord.track_id)))).scalar_one()
    detection_records = db.execute(select(func.count()).select_from(TrajectoryRecord)).scalar_one()
    start_time, end_time = get_time_bounds(db)
    time_span = (end_time - start_time) if start_time is not None and end_time is not None else None

    most_frequent = db.execute(
        select(TrajectoryRecord.grouped_class, func.count().label("cnt"))
        .group_by(TrajectoryRecord.grouped_class)
        .order_by(func.count().desc())
        .limit(1)
    ).first()

    selected_frame = frame
    selected_time = None
    if selected_frame is None and time_sec is not None:
        selected_frame = resolve_frame_for_time(db, time_sec)
    if selected_frame is None:
        _, selected_frame = get_frame_bounds(db)

    active_objects = 0
    if selected_frame is not None:
        active_objects = db.execute(
            select(func.count()).select_from(TrajectoryRecord).where(TrajectoryRecord.frame == selected_frame)
        ).scalar_one()
        time_row = db.execute(
            select(TrajectoryRecord.time_sec).where(TrajectoryRecord.frame == selected_frame).limit(1)
        ).first()
        if time_row is not None:
            selected_time = time_row[0]

    return SummaryResponse(
        total_tracks=total_tracks,
        detection_records=detection_records,
        active_objects=active_objects,
        time_span_seconds=time_span,
        most_frequent_class=most_frequent[0] if most_frequent else None,
        frame=selected_frame,
        time_sec=selected_time,
    )


def get_class_distribution(db: Session) -> ClassDistribution:
    rows = db.execute(
        select(
            TrajectoryRecord.grouped_class,
            func.count().label("detection_records"),
            func.count(func.distinct(TrajectoryRecord.track_id)).label("unique_tracks"),
        )
        .group_by(TrajectoryRecord.grouped_class)
        .order_by(func.count().desc())
    ).all()
    return ClassDistribution(
        classes=[
            ClassCount(
                class_name=row.grouped_class,
                detection_records=row.detection_records,
                unique_tracks=row.unique_tracks,
            )
            for row in rows
        ]
    )


def get_timeline(
    db: Session,
    grouped_class: str | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
) -> TimelineResponse:
    query = select(
        TrajectoryRecord.frame,
        func.min(TrajectoryRecord.time_sec).label("time_sec"),
        func.count().label("active_objects"),
    )
    if grouped_class is not None:
        query = query.where(TrajectoryRecord.grouped_class == grouped_class)
    if start_time is not None:
        query = query.where(TrajectoryRecord.time_sec >= start_time)
    if end_time is not None:
        query = query.where(TrajectoryRecord.time_sec <= end_time)
    query = query.group_by(TrajectoryRecord.frame).order_by(TrajectoryRecord.frame)
    rows = db.execute(query).all()
    return TimelineResponse(
        timeline=[
            TimelinePoint(frame=row.frame, time_sec=row.time_sec, active_objects=row.active_objects)
            for row in rows
        ]
    )


def get_confidence_statistics(db: Session, threshold: float) -> ConfidenceStatistics:
    stats = db.execute(
        select(
            func.avg(TrajectoryRecord.confidence),
            func.percentile_cont(0.5).within_group(TrajectoryRecord.confidence),
            func.min(TrajectoryRecord.confidence),
            func.max(TrajectoryRecord.confidence),
            func.count(TrajectoryRecord.confidence),
            func.count().filter(TrajectoryRecord.confidence < threshold),
        ).select_from(TrajectoryRecord)
    ).one()
    return ConfidenceStatistics(
        mean=float(stats[0]) if stats[0] is not None else None,
        median=float(stats[1]) if stats[1] is not None else None,
        minimum=float(stats[2]) if stats[2] is not None else None,
        maximum=float(stats[3]) if stats[3] is not None else None,
        count=int(stats[4] or 0),
        count_below_threshold=int(stats[5] or 0),
        threshold=threshold,
    )
