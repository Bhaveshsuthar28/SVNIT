import argparse
import ast
import json
import logging
import math
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import func, insert, select, text

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, engine
from app.models import TrajectoryRecord
from app.database import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("import_csv")

REQUIRED_COLUMNS = [
    "frame",
    "time_sec",
    "track_id",
    "grouped_class",
    "confidence",
    "bbox",
    "cx",
    "cy",
]
OPTIONAL_COLUMNS = [
    "source_class",
    "utm_easting",
    "utm_northing",
    "speed_kmh",
    "heading_angle",
]
VERIFICATION_TARGETS = {
    "records": 20731,
    "unique_tracks": 1251,
    "frames": 1000,
    "start_time": 0.0,
    "end_time": 33.3,
    "classes": {
        "Two-Wheeler": 7636,
        "CAR": 5120,
        "Three-Wheeler": 2922,
        "Pedestrian": 2767,
        "LCV": 1231,
        "BUS": 987,
        "HCV": 68,
    },
}


def find_csv_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"CSV file was not found: {path}")
        return path

    candidates = [
        Path(__file__).resolve().parent.parent / "data" / "trajectories67.csv",
        Path(__file__).resolve().parent.parent.parent / "trajectories67.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "trajectories67.csv was not found. Place it in backend/data/ or the project root."
    )


def to_null(value):
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def parse_bbox(value, row_number: int):
    value = to_null(value)
    if value is None:
        return None, None
    if isinstance(value, list):
        return value, None
    try:
        parsed = json.loads(value) if isinstance(value, str) and value.strip().startswith("[") else ast.literal_eval(value)
    except (ValueError, SyntaxError, json.JSONDecodeError):
        return None, f"Row {row_number}: bbox is malformed: {value!r}"
    if not isinstance(parsed, (list, tuple)) or len(parsed) != 4:
        return None, f"Row {row_number}: bbox must contain 4 numeric values."
    try:
        return [float(item) for item in parsed], None
    except (TypeError, ValueError):
        return None, f"Row {row_number}: bbox values must be numeric."


def validate_row(row, row_number: int) -> tuple[dict | None, str | None]:
    frame = to_null(row.get("frame"))
    time_sec = to_null(row.get("time_sec"))
    track_id = to_null(row.get("track_id"))
    grouped_class = to_null(row.get("grouped_class"))
    confidence = to_null(row.get("confidence"))
    cx = to_null(row.get("cx"))
    cy = to_null(row.get("cy"))

    if frame is None:
        return None, f"Row {row_number}: frame is required."
    try:
        frame = int(frame)
    except (TypeError, ValueError):
        return None, f"Row {row_number}: frame must be an integer."
    if frame < 0:
        return None, f"Row {row_number}: frame must be >= 0."

    if time_sec is None:
        return None, f"Row {row_number}: time_sec is required."
    try:
        time_sec = float(time_sec)
    except (TypeError, ValueError):
        return None, f"Row {row_number}: time_sec must be numeric."
    if time_sec < 0:
        return None, f"Row {row_number}: time_sec must be >= 0."

    if track_id is None:
        return None, f"Row {row_number}: track_id is required."
    try:
        track_id = int(track_id)
    except (TypeError, ValueError):
        return None, f"Row {row_number}: track_id must be an integer."
    if track_id < 0:
        return None, f"Row {row_number}: track_id must be >= 0."

    if grouped_class is None:
        return None, f"Row {row_number}: grouped_class is required."

    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return None, f"Row {row_number}: confidence must be numeric."
        if confidence < 0 or confidence > 1:
            return None, f"Row {row_number}: confidence must be between 0 and 1."

    if cx is not None:
        try:
            cx = float(cx)
        except (TypeError, ValueError):
            return None, f"Row {row_number}: cx must be numeric."
    if cy is not None:
        try:
            cy = float(cy)
        except (TypeError, ValueError):
            return None, f"Row {row_number}: cy must be numeric."

    bbox, bbox_error = parse_bbox(row.get("bbox"), row_number)
    if bbox_error:
        return None, bbox_error

    optional = {}
    for column in OPTIONAL_COLUMNS:
        value = to_null(row.get(column))
        if value is None:
            optional[column] = None
            continue
        if column == "source_class":
            optional[column] = str(value)
            continue
        try:
            optional[column] = float(value)
        except (TypeError, ValueError):
            return None, f"Row {row_number}: {column} must be numeric or empty."

    return {
        "frame": frame,
        "time_sec": time_sec,
        "track_id": track_id,
        "grouped_class": str(grouped_class),
        "source_class": optional["source_class"],
        "confidence": confidence,
        "bbox": bbox,
        "cx": cx,
        "cy": cy,
        "utm_easting": optional["utm_easting"],
        "utm_northing": optional["utm_northing"],
        "speed_kmh": optional["speed_kmh"],
        "heading_angle": optional["heading_angle"],
    }, None


def verify_import(session) -> dict:
    total = session.execute(select(func.count()).select_from(TrajectoryRecord)).scalar_one()
    tracks = session.execute(select(func.count(func.distinct(TrajectoryRecord.track_id)))).scalar_one()
    frames = session.execute(select(func.count(func.distinct(TrajectoryRecord.frame)))).scalar_one()
    time_bounds = session.execute(
        select(func.min(TrajectoryRecord.time_sec), func.max(TrajectoryRecord.time_sec))
    ).one()
    class_rows = session.execute(
        select(TrajectoryRecord.grouped_class, func.count())
        .group_by(TrajectoryRecord.grouped_class)
        .order_by(func.count().desc())
    ).all()
    null_speed = session.execute(
        select(func.count()).select_from(TrajectoryRecord).where(TrajectoryRecord.speed_kmh.is_(None))
    ).scalar_one()
    null_heading = session.execute(
        select(func.count()).select_from(TrajectoryRecord).where(TrajectoryRecord.heading_angle.is_(None))
    ).scalar_one()
    null_utm_e = session.execute(
        select(func.count()).select_from(TrajectoryRecord).where(TrajectoryRecord.utm_easting.is_(None))
    ).scalar_one()
    null_utm_n = session.execute(
        select(func.count()).select_from(TrajectoryRecord).where(TrajectoryRecord.utm_northing.is_(None))
    ).scalar_one()
    return {
        "records": total,
        "unique_tracks": tracks,
        "frames": frames,
        "start_time": time_bounds[0],
        "end_time": time_bounds[1],
        "classes": {name: count for name, count in class_rows},
        "null_speed_kmh": null_speed,
        "null_heading_angle": null_heading,
        "null_utm_easting": null_utm_e,
        "null_utm_northing": null_utm_n,
    }


def print_verification(stats: dict) -> None:
    logger.info("Imported records: %s (target %s)", stats["records"], VERIFICATION_TARGETS["records"])
    logger.info("Unique tracks: %s (target %s)", stats["unique_tracks"], VERIFICATION_TARGETS["unique_tracks"])
    logger.info("Frames: %s (target %s)", stats["frames"], VERIFICATION_TARGETS["frames"])
    logger.info(
        "Time range: %s–%s (target %s–%s)",
        stats["start_time"],
        stats["end_time"],
        VERIFICATION_TARGETS["start_time"],
        VERIFICATION_TARGETS["end_time"],
    )
    logger.info("Detection records by class:")
    for name, target in VERIFICATION_TARGETS["classes"].items():
        actual = stats["classes"].get(name, 0)
        logger.info("  %s: %s (target %s)", name, actual, target)
    logger.info(
        "NULL preservation — speed_kmh=%s heading_angle=%s utm_easting=%s utm_northing=%s",
        stats["null_speed_kmh"],
        stats["null_heading_angle"],
        stats["null_utm_easting"],
        stats["null_utm_northing"],
    )


def import_csv(csv_path: Path, replace: bool) -> None:
    logger.info("Reading %s", csv_path)
    df = pd.read_csv(csv_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    invalid_rows: list[str] = []
    records: list[dict] = []
    for index, row in df.iterrows():
        payload, error = validate_row(row, row_number=int(index) + 2)
        if error:
            invalid_rows.append(error)
            continue
        records.append(payload)

    if invalid_rows:
        preview = "\n".join(invalid_rows[:20])
        logger.error("Found %s invalid rows. First issues:\n%s", len(invalid_rows), preview)
        if len(invalid_rows) > 50:
            raise ValueError(
                f"{len(invalid_rows)} invalid rows were found. Import aborted to avoid corrupting the dataset."
            )
        raise ValueError(f"{len(invalid_rows)} invalid rows were found. Import aborted.")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        existing = session.execute(select(func.count()).select_from(TrajectoryRecord)).scalar_one()
        if existing and not replace:
            raise SystemExit(
                f"trajectory_records already contains {existing} rows. "
                "Re-run with --replace to delete existing trajectory data and import again."
            )
        if existing and replace:
            logger.warning(
                "REPLACE requested: deleting %s existing trajectory_records before import.",
                existing,
            )
            session.execute(text("TRUNCATE TABLE trajectory_records RESTART IDENTITY"))
            session.commit()

        logger.info("Inserting %s validated records into PostgreSQL.", len(records))
        batch_size = 1000
        for start in range(0, len(records), batch_size):
            session.execute(insert(TrajectoryRecord), records[start : start + batch_size])
        session.commit()
        stats = verify_import(session)
        print_verification(stats)
        logger.info("CSV import completed.")
    except Exception:
        session.rollback()
        logger.exception("CSV import failed")
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import SVNIT trajectories67.csv into PostgreSQL.")
    parser.add_argument("--csv", dest="csv_path", help="Path to trajectories67.csv")
    parser.add_argument(
        "--replace",
        "--reset",
        dest="replace",
        action="store_true",
        help="Delete existing trajectory_records before importing. This is not silent: a warning is logged.",
    )
    args = parser.parse_args()
    csv_path = find_csv_path(args.csv_path)
    import_csv(csv_path, replace=args.replace)


if __name__ == "__main__":
    main()
