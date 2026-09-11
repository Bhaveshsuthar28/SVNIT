# Traffic Analytics Dashboard — Backend

Backend for the Sardar Vallabhbhai National Institute of Technology (SVNIT), Surat traffic analytics assignment.

This service stores the provided computer-vision trajectory file `trajectories67.csv` in PostgreSQL and exposes it through FastAPI REST APIs and a WebSocket trajectory replay. The React frontend is built later against these APIs.

This is **not** a live CCTV connection. Playback is a real-time-style replay of the recorded SVNIT dataset.

## Architecture

```
SVNIT CV output
      |
      v
trajectories67.csv
      |
      v
CSV importer
      |
      v
PostgreSQL (source of truth)
      |
      +--------------------+
      |                    |
      v                    v
   REST APIs          In-memory frame cache
                           |
                           v
                     WebSocket replay
```

A later React app (typically `http://localhost:5173`) will consume both surfaces.

## Requirements

- Python 3.11+
- PostgreSQL 14+

Do not install Ultralytics or YOLO. This backend does not run detection and does not generate trajectories.

## PostgreSQL setup

1. Install PostgreSQL and start the service.
2. Create a login role and database (example):

```sql
CREATE ROLE traffic LOGIN PASSWORD 'password';
CREATE DATABASE traffic_analytics OWNER traffic;
GRANT ALL ON SCHEMA public TO traffic;
```

3. From `backend/`, copy environment configuration:

```
copy .env.example .env
```

On macOS/Linux:

```
cp .env.example .env
```

4. Set `DATABASE_URL` in `.env`. Do not commit `.env`.

Example:

```
DATABASE_URL=postgresql+psycopg://traffic:password@127.0.0.1:5432/traffic_analytics
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
```

Database name: `traffic_analytics`.

## Backend setup

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux activation:

```
source venv/bin/activate
```

## Database initialization

Tables and indexes are created with SQLAlchemy metadata (Alembic is not required for this assignment):

```
python scripts/init_db.py
```

This creates `trajectory_records` plus indexes on `track_id`, `frame`, `time_sec`, `grouped_class`, `(frame, track_id)`, and `(grouped_class, frame)`.

## CSV import

Place the real SVNIT file at `backend/data/trajectories67.csv` (a copy of the project-root file is fine).

```
python scripts/import_csv.py
```

If `trajectory_records` already has rows, the importer refuses to delete them. To replace the dataset, pass `--replace` (also accepted as `--reset`). That flag logs a warning and truncates existing trajectory data before inserting again.

Missing `utm_easting`, `utm_northing`, `speed_kmh`, and `heading_angle` values are stored as SQL `NULL`. The importer does not invent speed, heading, UTM, crash probability, or risk scores.

After import it prints live database statistics. Expected verification targets for this dataset (not hard-coded API values):

- 20,731 detection records
- 1,251 unique tracks
- 1,000 frames (0–999)
- 0.0–33.3 seconds
- Two-Wheeler 7,636; CAR 5,120; Three-Wheeler 2,922; Pedestrian 2,767; LCV 1,231; BUS 987; HCV 68

## Start server

From `backend/`:

```
uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

## REST API

All JSON APIs use the `/api` prefix. Values are calculated from PostgreSQL, not hard-coded.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | PostgreSQL connectivity check |
| GET | `/api/metadata` | Dataset name, counts, time range, FPS, available/unavailable fields |
| GET | `/api/summary` | Tracks, detection records, active objects, most frequent class |
| GET | `/api/analytics/classes` | Detection-record counts by `grouped_class` (optional unique tracks) |
| GET | `/api/analytics/timeline` | Active objects per frame |
| GET | `/api/analytics/confidence` | Confidence mean/median/min/max and count below threshold |
| GET | `/api/frames/{frame}` | All objects in one video frame (playback-friendly) |
| GET | `/api/trajectories` | Filtered trajectory points, paginated by track |
| GET | `/api/trajectories/{track_id}` | One track with duration, latest position, confidence stats |

### Query parameters

`GET /api/summary`

- `frame` — compute `active_objects` for that frame
- `time_sec` — resolve the nearest frame, then count active objects
- If omitted, the last frame in the dataset is used

`GET /api/trajectories`

- `track_id`, `grouped_class`
- `start_frame`, `end_frame`
- `start_time`, `end_time`
- `min_confidence`
- `limit` (default 25, max 200), `offset`

If `track_id` is provided, the response is a single trajectory object with ordered `points`. Otherwise the response is a paginated list.

`GET /api/analytics/timeline`

- `grouped_class`, `start_time`, `end_time`

`GET /api/analytics/confidence`

- `threshold` (default `0.3`, must be 0–1)

`GET /api/trajectories/{track_id}` does **not** return speed or heading. Those fields are unavailable in the supplied CSV.

### Example errors

```json
{ "detail": "Track ID 2756 was not found." }
```

```json
{ "detail": "Frame must be between 0 and 999." }
```

```json
{ "detail": "Confidence threshold must be between 0 and 1." }
```

HTTP 503 is returned when PostgreSQL is unavailable.

## WebSocket

`ws://localhost:8000/ws/traffic`

This endpoint streams **trajectory replay** of the recorded dataset. It is not live CCTV.

Each client has independent playback state (frame, pause, speed). The in-memory frame cache is shared.

Commands (JSON text frames):

```json
{ "action": "start" }
{ "action": "pause" }
{ "action": "resume" }
{ "action": "stop" }
{ "action": "seek", "frame": 500 }
{ "action": "set_speed", "speed": 2 }
```

Allowed speeds: `0.25`, `0.5`, `1`, `2`, `4`.

At 1x, 1,000 frames over 33.3 seconds are paced with a monotonic clock so processing overhead does not accumulate as extra delay. Seek jumps to `frames[n]` immediately and does not replay earlier frames.

Each `type: "frame"` message contains only that frame’s objects plus `active_objects` and `class_counts`.

## Dataset

Source of truth: `trajectories67.csv`

Columns:

| Column | Meaning | In this file |
| --- | --- | --- |
| `frame` | Video frame number | Present (0–999) |
| `time_sec` | Timestamp in seconds | Present (0.0–33.3) |
| `track_id` | Object identity across frames | Present (including id `0`) |
| `grouped_class` | Grouped category | Present |
| `source_class` | Original class label | Present |
| `confidence` | Detector confidence, **not** crash probability | Present |
| `bbox` | Bounding box `[x1, y1, x2, y2]` | Present |
| `cx`, `cy` | Box center (primary visualization coordinates) | Present |
| `utm_easting` | UTM | Missing → NULL |
| `utm_northing` | UTM | Missing → NULL |
| `speed_kmh` | Speed | Missing → NULL |
| `heading_angle` | Heading | Missing → NULL |

Grouped classes include: `CAR`, `Two-Wheeler`, `Three-Wheeler`, `Pedestrian`, `LCV`, `BUS`, `HCV`.

## Data statistics

There are about **20,731 detection records** and about **1,251 unique tracks**.

**20,731 records ≠ 20,731 vehicles.** One tracked object appears in many frames. Use `unique_tracks` for object counts and `detection_records` for row counts.

Duration is 33.3 seconds at approximately 30 FPS.

## Missing data

Unavailable in PostgreSQL (all NULL for this CSV):

- `speed_kmh`
- `heading_angle`
- `utm_easting`
- `utm_northing`

`GET /api/metadata` reports these under `unavailable` by counting non-null values dynamically.

## Real-time replay

The WebSocket performs real-time-style replay of the recorded SVNIT CV output. Call it “Real-Time Replay” or “Trajectory Replay” in a UI — not “Live CCTV”.

## Performance

PostgreSQL remains the persistent source of truth. REST endpoints filter and aggregate in SQL and use indexes. List endpoints are paginated.

On startup the backend loads frame payloads into an in-memory cache (`frames[frame_number]`) so WebSocket playback does not run a PostgreSQL query at 30 FPS. The cache is rebuilt when the process starts (re-run the server after a CSV re-import).

## Static assets

Optional files in `backend/assets/` are served under `/assets`. Trajectory APIs do not depend on a map, heatmap, or video file.

## CORS

Origins come from `CORS_ORIGINS` (comma-separated). Development default: `http://localhost:5173`.

## Testing

From `backend/` with PostgreSQL running and the CSV imported:

```
pytest
```

Tests cover health, metadata, summary, class/timeline/confidence analytics, trajectories, frames, invalid parameters, and WebSocket start/pause/resume/seek/speed.

## Logging

Startup, database engine creation, CSV import counts, WebSocket connect/disconnect, and API/database errors are logged. Database passwords are not logged.
