from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Double, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TrajectoryRecord(Base):
    __tablename__ = "trajectory_records"
    __table_args__ = (
        Index("ix_trajectory_records_track_id", "track_id"),
        Index("ix_trajectory_records_frame", "frame"),
        Index("ix_trajectory_records_time_sec", "time_sec"),
        Index("ix_trajectory_records_grouped_class", "grouped_class"),
        Index("ix_trajectory_records_frame_track_id", "frame", "track_id"),
        Index("ix_trajectory_records_grouped_class_frame", "grouped_class", "frame"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    frame: Mapped[int] = mapped_column(Integer, nullable=False)
    time_sec: Mapped[float] = mapped_column(Double, nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    grouped_class: Mapped[str] = mapped_column(String, nullable=False)
    source_class: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cx: Mapped[float | None] = mapped_column(Double, nullable=True)
    cy: Mapped[float | None] = mapped_column(Double, nullable=True)
    utm_easting: Mapped[float | None] = mapped_column(Double, nullable=True)
    utm_northing: Mapped[float | None] = mapped_column(Double, nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Double, nullable=True)
    heading_angle: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
