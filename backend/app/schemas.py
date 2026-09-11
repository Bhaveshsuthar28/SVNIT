from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str


class MetadataResponse(BaseModel):
    dataset: str
    total_records: int
    unique_tracks: int
    frames: int
    first_frame: int | None = None
    last_frame: int | None = None
    start_time_sec: float | None = None
    end_time_sec: float | None = None
    duration_seconds: float | None = None
    fps: int | None = None
    classes: list[str]
    available: list[str]
    unavailable: list[str]


class SummaryResponse(BaseModel):
    total_tracks: int
    detection_records: int
    active_objects: int
    time_span_seconds: float | None = None
    most_frequent_class: str | None = None
    frame: int | None = None
    time_sec: float | None = None


class ClassCount(BaseModel):
    class_name: str
    detection_records: int
    unique_tracks: int | None = None


class ClassDistribution(BaseModel):
    classes: list[ClassCount]


class TrajectoryPoint(BaseModel):
    frame: int
    time_sec: float
    cx: float | None = None
    cy: float | None = None
    confidence: float | None = None


class TrajectoryResponse(BaseModel):
    track_id: int
    class_name: str = Field(serialization_alias="class")
    points: list[TrajectoryPoint]

    model_config = {"populate_by_name": True}


class TrajectoryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    trajectories: list[TrajectoryResponse]


class Position(BaseModel):
    frame: int
    time_sec: float
    cx: float | None = None
    cy: float | None = None


class ConfidenceSummary(BaseModel):
    mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    count: int = 0


class TrackDetails(BaseModel):
    track_id: int
    class_name: str = Field(serialization_alias="class")
    source_class: str | None = None
    trajectory_points: int
    first_frame: int
    last_frame: int
    first_time_sec: float
    last_time_sec: float
    duration_seconds: float
    latest_position: Position
    confidence_statistics: ConfidenceSummary
    points: list[TrajectoryPoint]

    model_config = {"populate_by_name": True}


class FrameObject(BaseModel):
    track_id: int
    class_name: str = Field(serialization_alias="class")
    confidence: float | None = None
    cx: float | None = None
    cy: float | None = None
    bbox: list[Any] | None = None

    model_config = {"populate_by_name": True}


class FrameResponse(BaseModel):
    frame: int
    time_sec: float | None = None
    object_count: int
    objects: list[FrameObject]


class TimelinePoint(BaseModel):
    frame: int
    time_sec: float | None = None
    active_objects: int


class TimelineResponse(BaseModel):
    timeline: list[TimelinePoint]


class ConfidenceStatistics(BaseModel):
    mean: float | None = None
    median: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    count: int
    count_below_threshold: int
    threshold: float


class WebSocketFrameObject(FrameObject):
    pass


class WebSocketFrame(BaseModel):
    type: str = "frame"
    frame: int
    time_sec: float | None = None
    active_objects: int
    class_counts: dict[str, int]
    objects: list[FrameObject]


class PlaybackStatus(BaseModel):
    type: str = "status"
    state: str
    frame: int
    speed: float
    message: str | None = None


class ErrorResponse(BaseModel):
    detail: str
