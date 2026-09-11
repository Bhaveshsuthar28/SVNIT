from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from collections import defaultdict

from app.database import get_db
from app.models import TrajectoryRecord
from app.schemas import ClassDistribution, ConfidenceStatistics, TimelineResponse
from app.services.analytics_service import (
    get_class_distribution,
    get_confidence_statistics,
    get_timeline,
)

router = APIRouter()

@router.get("/analytics/workspace", response_model=None)
def analytics_workspace(db: Session = Depends(get_db)) -> dict:
    """Return one aggregate payload for the detailed research workspace."""
    records = db.execute(
        select(TrajectoryRecord).order_by(TrajectoryRecord.frame, TrajectoryRecord.id)
    ).scalars().all()
    if not records:
        return {"class_activity": [], "track_stats": [], "confidence_histogram": [], "density": [], "timeline_bands": [], "comparison": []}

    by_frame: dict[int, dict] = {}
    by_class_frame: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    tracks: dict[int, list[TrajectoryRecord]] = defaultdict(list)
    confidence_bins = [0] * 10
    density = [[0 for _ in range(16)] for _ in range(9)]
    for record in records:
        frame = by_frame.setdefault(record.frame, {"frame": record.frame, "time": record.time_sec, "detection_records": 0})
        frame["detection_records"] += 1
        by_class_frame[record.grouped_class][record.frame] += 1
        tracks[record.track_id].append(record)
        if record.confidence is not None:
            confidence_bins[min(9, max(0, int(record.confidence * 10)))] += 1
        if record.cx is not None and record.cy is not None:
            density[min(8, max(0, int(record.cy / 720 * 9)))][min(15, max(0, int(record.cx / 1280 * 16)))] += 1

    track_stats = []
    trajectory_flow = []
    for track_id, points in tracks.items():
        track_stats.append({
            "track_id": track_id,
            "duration": points[-1].time_sec - points[0].time_sec,
            "observations": len(points),
            "class_name": points[-1].grouped_class,
        })
        trajectory_flow.append({
            "track_id": track_id,
            "class_name": points[-1].grouped_class,
            "points": [
                {"frame": point.frame, "time": point.time_sec, "cx": point.cx, "cy": point.cy}
                for point in points
                if point.cx is not None and point.cy is not None
            ],
        })
    track_stats.sort(key=lambda item: item["track_id"])
    class_activity = []
    for frame in by_frame.values():
        row = dict(frame)
        for class_name, frames in by_class_frame.items():
            row[class_name] = frames.get(frame["frame"], 0)
        class_activity.append(row)
    timeline_bands = []
    for class_name, frame_counts in by_class_frame.items():
        frames = sorted(frame_counts)
        start = previous = frames[0]
        for current in frames[1:] + [None]:
            if current is None or current != previous + 1:
                timeline_bands.append({"class_name": class_name, "start_frame": start, "end_frame": previous, "start_time": by_frame[start]["time"], "end_time": by_frame[previous]["time"]})
                if current is not None:
                    start = current
            previous = current if current is not None and current != previous + 1 else previous
    confidence_values = [record.confidence for record in records if record.confidence is not None]
    comparison = []
    for class_name, frame_counts in by_class_frame.items():
        class_records = [record for record in records if record.grouped_class == class_name]
        class_confidence = [record.confidence for record in class_records if record.confidence is not None]
        comparison.append({"class_name": class_name, "detection_records": len(class_records), "track_ids_observed": len({record.track_id for record in class_records}), "average_confidence": sum(class_confidence) / len(class_confidence) if class_confidence else None})
    return {
        "detection_volume": list(by_frame.values()),
        "class_activity": class_activity,
        "track_stats": track_stats,
        "trajectory_flow": trajectory_flow,
        "confidence_histogram": [{"range": f"{index / 10:.1f}–{(index + 1) / 10:.1f}", "confidence": index / 10, "records": value} for index, value in enumerate(confidence_bins)],
        "density": [{"x": column, "y": row, "count": density[row][column]} for row in range(9) for column in range(16)],
        "timeline_bands": timeline_bands,
        "comparison": comparison,
        "track_summary": {"minimum_duration": min(item["duration"] for item in track_stats), "median_duration": sorted(item["duration"] for item in track_stats)[len(track_stats) // 2], "mean_duration": sum(item["duration"] for item in track_stats) / len(track_stats), "maximum_duration": max(item["duration"] for item in track_stats), "minimum_observations": min(item["observations"] for item in track_stats), "median_observations": sorted(item["observations"] for item in track_stats)[len(track_stats) // 2], "mean_observations": sum(item["observations"] for item in track_stats) / len(track_stats), "maximum_observations": max(item["observations"] for item in track_stats)},
        "confidence_count": len(confidence_values),
    }

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
