from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TrajectoryRecord
from app.schemas import (
    FrameObject,
    FrameResponse,
    TrackDetails,
    TrajectoryListResponse,
    TrajectoryPoint,
    TrajectoryResponse,
)


def get_frame_bounds(db: Session) -> tuple[int | None, int | None]:
    row = db.execute(
        select(func.min(TrajectoryRecord.frame), func.max(TrajectoryRecord.frame))
    ).one()
    return row[0], row[1]


def get_time_bounds(db: Session) -> tuple[float | None, float | None]:
    row = db.execute(
        select(func.min(TrajectoryRecord.time_sec), func.max(TrajectoryRecord.time_sec))
    ).one()
    return row[0], row[1]


def resolve_frame_for_time(db: Session, time_sec: float) -> int | None:
    row = db.execute(
        select(TrajectoryRecord.frame)
        .order_by(func.abs(TrajectoryRecord.time_sec - time_sec))
        .limit(1)
    ).first()
    return None if row is None else int(row[0])


def get_frame(db: Session, frame: int) -> FrameResponse | None:
    records = db.execute(
        select(TrajectoryRecord)
        .where(TrajectoryRecord.frame == frame)
        .order_by(TrajectoryRecord.track_id)
    ).scalars().all()
    if not records:
        exists = db.execute(
            select(func.count()).select_from(TrajectoryRecord)
        ).scalar_one()
        if exists == 0:
            return None
        min_frame, max_frame = get_frame_bounds(db)
        if min_frame is None or frame < min_frame or frame > max_frame:
            return None
        return FrameResponse(frame=frame, time_sec=None, object_count=0, objects=[])

    objects = [
        FrameObject(
            track_id=record.track_id,
            class_name=record.grouped_class,
            confidence=record.confidence,
            cx=record.cx,
            cy=record.cy,
            bbox=record.bbox,
        )
        for record in records
    ]
    return FrameResponse(
        frame=frame,
        time_sec=records[0].time_sec,
        object_count=len(objects),
        objects=objects,
    )


def list_trajectories(
    db: Session,
    *,
    track_id: int | None = None,
    grouped_class: str | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TrajectoryListResponse | TrajectoryResponse:
    filters = _trajectory_filters(
        track_id=track_id,
        grouped_class=grouped_class,
        start_frame=start_frame,
        end_frame=end_frame,
        start_time=start_time,
        end_time=end_time,
        min_confidence=min_confidence,
    )

    if track_id is not None:
        query = select(TrajectoryRecord)
        if filters:
            query = query.where(*filters)
        records = db.execute(
            query.order_by(TrajectoryRecord.frame, TrajectoryRecord.id)
        ).scalars().all()
        if not records:
            return TrajectoryListResponse(total=0, limit=limit, offset=offset, trajectories=[])
        return _to_trajectory_response(records)

    track_query = select(TrajectoryRecord.track_id)
    if filters:
        track_query = track_query.where(*filters)
    track_subquery = track_query.group_by(TrajectoryRecord.track_id).order_by(TrajectoryRecord.track_id)
    total = db.execute(
        select(func.count()).select_from(track_subquery.subquery())
    ).scalar_one()
    track_ids = db.execute(track_subquery.offset(offset).limit(limit)).scalars().all()
    if not track_ids:
        return TrajectoryListResponse(total=total, limit=limit, offset=offset, trajectories=[])

    points_query = select(TrajectoryRecord)
    point_filters = list(filters)
    point_filters.append(TrajectoryRecord.track_id.in_(track_ids))
    records = db.execute(
        points_query.where(*point_filters).order_by(
            TrajectoryRecord.track_id, TrajectoryRecord.frame, TrajectoryRecord.id
        )
    ).scalars().all()

    grouped: dict[int, list[TrajectoryRecord]] = {}
    for record in records:
        grouped.setdefault(record.track_id, []).append(record)

    trajectories = [_to_trajectory_response(grouped[tid]) for tid in track_ids if tid in grouped]
    return TrajectoryListResponse(
        total=total,
        limit=limit,
        offset=offset,
        trajectories=trajectories,
    )


def get_track_details(db: Session, track_id: int) -> TrackDetails | None:
    records = db.execute(
        select(TrajectoryRecord)
        .where(TrajectoryRecord.track_id == track_id)
        .order_by(TrajectoryRecord.frame, TrajectoryRecord.id)
    ).scalars().all()
    if not records:
        return None

    confidences = [r.confidence for r in records if r.confidence is not None]
    latest = records[-1]
    points = [_to_point(record) for record in records]
    return TrackDetails(
        track_id=track_id,
        class_name=latest.grouped_class,
        source_class=latest.source_class,
        trajectory_points=len(records),
        first_frame=records[0].frame,
        last_frame=latest.frame,
        first_time_sec=records[0].time_sec,
        last_time_sec=latest.time_sec,
        duration_seconds=latest.time_sec - records[0].time_sec,
        latest_position={
            "frame": latest.frame,
            "time_sec": latest.time_sec,
            "cx": latest.cx,
            "cy": latest.cy,
        },
        confidence_statistics={
            "mean": (sum(confidences) / len(confidences)) if confidences else None,
            "minimum": min(confidences) if confidences else None,
            "maximum": max(confidences) if confidences else None,
            "count": len(confidences),
        },
        points=points,
    )


def load_all_records_for_cache(db: Session) -> list[TrajectoryRecord]:
    return db.execute(
        select(TrajectoryRecord).order_by(TrajectoryRecord.frame, TrajectoryRecord.track_id)
    ).scalars().all()


def _trajectory_filters(
    *,
    track_id: int | None,
    grouped_class: str | None,
    start_frame: int | None,
    end_frame: int | None,
    start_time: float | None,
    end_time: float | None,
    min_confidence: float | None,
) -> list:
    filters = []
    if track_id is not None:
        filters.append(TrajectoryRecord.track_id == track_id)
    if grouped_class is not None:
        filters.append(TrajectoryRecord.grouped_class == grouped_class)
    if start_frame is not None:
        filters.append(TrajectoryRecord.frame >= start_frame)
    if end_frame is not None:
        filters.append(TrajectoryRecord.frame <= end_frame)
    if start_time is not None:
        filters.append(TrajectoryRecord.time_sec >= start_time)
    if end_time is not None:
        filters.append(TrajectoryRecord.time_sec <= end_time)
    if min_confidence is not None:
        filters.append(TrajectoryRecord.confidence >= min_confidence)
    return filters


def _to_point(record: TrajectoryRecord) -> TrajectoryPoint:
    return TrajectoryPoint(
        frame=record.frame,
        time_sec=record.time_sec,
        cx=record.cx,
        cy=record.cy,
        confidence=record.confidence,
    )


def _to_trajectory_response(records: list[TrajectoryRecord]) -> TrajectoryResponse:
    latest = records[-1]
    return TrajectoryResponse(
        track_id=latest.track_id,
        class_name=latest.grouped_class,
        points=[_to_point(record) for record in records],
    )
