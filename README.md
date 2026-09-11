# Traffic Analytics Dashboard

## Computer-Vision-Based Intersection Monitoring and Recorded Trajectory Analysis

**SVNIT Surat | Junction 67**

## Project Overview

Traffic intersections produce a large amount of visual information. A computer-vision pipeline can detect and follow road users, but raw detections and movement coordinates are difficult to inspect directly. This project adds an interactive analytics layer over recorded computer-vision output from Junction 67.

The application turns trajectory observations into a readable research dashboard. Users can compare road-user types, inspect activity over time, examine a particular frame, follow an individual road user, view movement paths, and replay the sequence.

This is a **recorded traffic analysis system**, not a live CCTV feed. Replay represents previously recorded computer-vision output.

```text
Recorded traffic/CV output
          |
          v
  trajectories67.csv
          |
          v
CSV validation and import
          |
          v
 PostgreSQL source of truth
          |
     +----+----+
     |         |
     v         v
 FastAPI   Playback cache
 REST      WebSocket replay
     +----+----+
          v
    React frontend
          |
 Dashboard and Analytics
```

## Objectives

- Visualize recorded traffic activity at Junction 67.
- Show road-user composition using real observations.
- Explore traffic activity across the recording timeline.
- Display recorded movement paths in video-coordinate space.
- Inspect the road users present at a selected frame.
- Follow an individual tracked road user.
- Examine detection confidence and tracking persistence.
- Provide real-time-style trajectory replay.
- Present results clearly to technical and non-technical users.

## Key Features

- Dashboard for a quick overview of the recorded scene.
- Analytics page for class, temporal, confidence, spatial, frame, and track analysis.
- Supplied map and heatmap image layers.
- Class-colored trajectory paths and circular object markers.
- Backend-driven KPI values and chart data.
- Frame selection by frame number or timestamp.
- Scrollable frame object table with selectable rows.
- Individual track lookup and recorded movement path.
- Confidence, duration, observation-length, density, and timeline views.
- WebSocket replay with play/pause toggle, stop, seek, 10-second skip controls, and adjustable speed.
- Speed slider from `0.1x` to `2x` with live updates and cancel.
- Fixed expandable/collapsible sidebar with Dashboard and Analytics navigation.
- PostgreSQL persistence and indexes for common lookups.

## System Architecture

```mermaid
flowchart LR
    A[Recorded CV output] --> B[trajectories67.csv]
    B --> C[CSV importer]
    C --> D[(PostgreSQL)]
    D --> E[FastAPI REST APIs]
    D --> F[Playback cache]
    F --> G[WebSocket /ws/traffic]
    E --> H[React frontend]
    G --> H
    H --> I[Dashboard]
    H --> J[Analytics]
```

### Layers

1. Existing recorded computer-vision output supplies detections and tracking data.
2. The importer validates required fields and inserts rows into PostgreSQL.
3. PostgreSQL stores the persistent trajectory source of truth.
4. FastAPI provides metadata, summaries, frames, tracks, and analytical aggregates.
5. The replay service loads frames into memory for frame-by-frame playback.
6. React presents the Dashboard and Analytics experiences.

## Data Flow

1. The existing computer-vision pipeline produces recorded detections and tracking output.
2. `trajectories67.csv` is checked for required columns and valid values.
3. Validated rows are stored in PostgreSQL.
4. FastAPI reads PostgreSQL for summaries, analytics, frames, and trajectories.
5. The backend builds an in-memory playback cache at startup.
6. React requests analytical data through REST APIs.
7. React connects to `/ws/traffic` for recorded replay frames.
8. The pages render returned data without running detection in the browser.

REST is used for request/response analysis and lookup operations. WebSocket is used for the ongoing frame-by-frame replay stream, avoiding a REST request for every playback frame.

## Provided Data

### `trajectories67.csv`

The project includes the trajectory data in the project root and under `backend/data/`. The importer checks `backend/data/trajectories67.csv` first when both locations are available.

| Measure | Value |
|---|---:|
| Detection observations | 20,731 |
| Track IDs | 1,251 |
| Frames | 1,000 (`0`-`999`) |
| Recording duration | 33.3 seconds |
| Approximate frame rate | 30 FPS |
| Video coordinate space | 1280 x 720 |

Expected class totals for the supplied dataset:

| Road-user class | Recorded observations |
|---|---:|
| Two-Wheeler | 7,636 |
| CAR | 5,120 |
| Three-Wheeler | 2,922 |
| Pedestrian | 2,767 |
| LCV | 1,231 |
| BUS | 987 |
| HCV | 68 |

These are observation counts, not unique vehicle counts. One tracked road user can appear in many frames.

### CSV Fields

| Field | Meaning |
|---|---|
| `frame` | Video frame number |
| `time_sec` | Timestamp in seconds |
| `track_id` | Identifier used to follow an object across frames |
| `grouped_class` | Grouped road-user class |
| `source_class` | Original source class, when available |
| `confidence` | Detection confidence from the source pipeline |
| `bbox` | Source bounding box data |
| `cx` | Recorded image-space X coordinate |
| `cy` | Recorded image-space Y coordinate |
| `utm_easting` | Optional UTM coordinate; empty for this dataset |
| `utm_northing` | Optional UTM coordinate; empty for this dataset |
| `speed_kmh` | Optional speed measurement; empty for this dataset |
| `heading_angle` | Optional heading measurement; empty for this dataset |

The assignment references `annotated_junction67.mp4`, but no MP4 is currently present in this workspace. The frontend therefore uses the supplied map/heatmap PNG assets and recorded trajectory data for its visual frame representation.

## Dataset Limitations and Data Integrity

The supplied CSV does not contain populated measurements for `speed_kmh`, `heading_angle`, `utm_easting`, or `utm_northing`.

The application deliberately does not fabricate speed, heading, GPS/UTM positions, crash probability, collision probability, or numerical risk scores.

`cx` and `cy` are recorded image/video coordinates. Spatial charts and movement paths describe the 1280 x 720 recorded coordinate space, not geographic GPS analysis. The supplied heatmap is treated as a qualitative visual reference rather than a validated risk model.

## Database Design

PostgreSQL is the persistent source of truth. SQLAlchemy creates the `trajectory_records` table and indexes it for common frame, time, class, and track queries.

| Column | Purpose |
|---|---|
| `id` | Big integer primary key |
| `frame` | Integer video frame |
| `time_sec` | Double timestamp |
| `track_id` | Integer tracking identifier |
| `grouped_class` | String grouped class |
| `source_class` | Nullable original class |
| `confidence` | Nullable detection confidence |
| `bbox` | Nullable PostgreSQL JSONB bounding box |
| `cx`, `cy` | Nullable image-space coordinates |
| `utm_easting`, `utm_northing` | Nullable UTM fields |
| `speed_kmh` | Nullable speed field |
| `heading_angle` | Nullable heading field |
| `created_at` | Timezone-aware creation timestamp |

Indexes exist on `track_id`, `frame`, `time_sec`, `grouped_class`, `(frame, track_id)`, and `(grouped_class, frame)`.

PostgreSQL provides durable storage, structured filtering, SQL aggregation, and a reliable source for REST analytics and replay-cache initialization.

## Backend

The backend is a FastAPI application using SQLAlchemy, Pydantic, and the PostgreSQL `psycopg` driver. It provides database access, validation boundaries, analytical aggregation, frame retrieval, track retrieval, and replay.

### REST Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check service and database connectivity |
| `GET` | `/api/metadata` | Counts, classes, time range, FPS, and available fields |
| `GET` | `/api/summary` | Tracks, observations, current active objects, and common class |
| `GET` | `/api/analytics/classes` | Observation totals and observed track IDs by class |
| `GET` | `/api/analytics/timeline` | Active objects per frame with class/time filters |
| `GET` | `/api/analytics/confidence` | Confidence statistics for a threshold |
| `GET` | `/api/analytics/workspace` | Aggregate data for detailed charts and spatial analysis |
| `GET` | `/api/frames/{frame}` | Objects recorded in one frame |
| `GET` | `/api/trajectories` | Paginated filtered trajectory records |
| `GET` | `/api/trajectories/{track_id}` | One track's points, timing, position, and confidence |

Supported parameters include `grouped_class`, `track_id`, `start_frame`, `end_frame`, `start_time`, `end_time`, `min_confidence`, `limit`, and `offset`, depending on the endpoint.

## WebSocket Replay

Endpoint: `ws://localhost:8000/ws/traffic`

This is a replay of recorded data, not a live camera. Each client has independent playback state and can send:

```json
{ "action": "start" }
{ "action": "pause" }
{ "action": "resume" }
{ "action": "stop" }
{ "action": "seek", "frame": 500 }
{ "action": "set_speed", "speed": 1 }
```

The frontend uses REST for analytical queries and WebSocket for frame-by-frame replay. Each frame message contains the current frame, timestamp, active-object count, class counts, and objects in that frame.

## Frontend

The frontend is a React + Vite application using:

- React for the interactive UI.
- Vite for development and production builds.
- Recharts for interactive bar and line charts with tooltips.
- Lucide React for navigation, playback, KPI, and control icons.
- `src/services/api.js` for REST requests.
- `src/hooks/useTrafficSocket.js` for managed WebSocket connection and reconnect behavior.

The application has exactly two primary experiences.

### Dashboard

The Dashboard answers: **What is happening at Junction 67?**

It includes overall summary metrics, current road users, Map/Heatmap/Trajectories/Combined modes, class-consistent colors, layer controls, selected road-user information, activity over time, and embedded trajectory replay.

### Analytics

Analytics answers: **How are road users distributed, observed, and moving in this recording?**

It includes key findings, road-user composition, traffic activity, detection volume, class activity, confidence distribution, observed track duration, trajectory observation length, video-coordinate density, movement paths, class observation periods, frame analysis, track analysis, dataset information, and source limitations.

Technical terms remain available where useful, but the interface also uses plain explanations such as road users, recorded observations, movement paths, and how long objects were visible.

## User Interface and Accessibility

The interface uses a light research-dashboard design with white panels, subtle borders, strong contrast, Outfit typography loaded through Google Fonts, and one consistent class-color mapping.

The sidebar is fixed to the viewport, smoothly transitions between expanded and collapsed states, shows only Dashboard and Analytics, and uses Lucide icons with tooltips in its collapsed state.

Charts use labels, legends, hover tooltips, and readable values so color is not the only way to understand a result. Tables support scrolling, row hover feedback, and keyboard focus where rows can be selected.

## Technical Approach

### Why PostgreSQL?

The trajectory data is structured and queried by frame, time, class, and track. PostgreSQL provides persistence and SQL aggregation rather than requiring the browser to hold the entire dataset.

### Why FastAPI?

FastAPI provides a small typed API layer suitable for REST analytics, validation, database access, and WebSocket integration.

### Why WebSocket?

Playback is a stream of changing frame state. The WebSocket sends each current frame from an in-memory cache and avoids REST polling for every playback step.

### Why React?

React supports interactive views, filters, frame and track selection, chart updates, responsive layout, and shared state for both pages.

### Why reuse the provided CV output?

This project focuses on analytics and visualization over the supplied recorded output. It does not retrain or rerun the detection pipeline.

## Why the Frontend Does Not Run YOLO

The supplied trajectory file is already the output of a computer-vision detection and tracking process. The frontend is responsible for visualization, filtering, analytics, interaction, and replay. It does not perform browser-side detection and does not include Ultralytics or YOLO.

## Project Structure

```text
SVNIT/
├── README.md
├── trajectories67.csv
├── anaylis.ipynb
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── main.py
│   ├── data/trajectories67.csv
│   ├── scripts/init_db.py
│   ├── scripts/import_csv.py
│   ├── tests/
│   ├── requirements.txt
│   ├── pytest.ini
│   └── README.md
└── frontend/
    ├── public/assets/
    │   ├── junction67-map.png
    │   └── junction67-heatmap.png
    ├── src/
    │   ├── hooks/useTrafficSocket.js
    │   ├── services/api.js
    │   ├── App.jsx
    │   ├── main.jsx
    │   └── styles.css
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    └── index.html
```

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, JavaScript, Vite |
| Charts | Recharts |
| Icons | Lucide React |
| Backend | FastAPI, Python |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Schemas | Pydantic |
| Driver | psycopg |
| Analysis transport | REST |
| Replay transport | WebSocket |
| Source data | CSV |
| Import processing | pandas and Python validation |
| Tests | pytest and FastAPI test client |

## Installation and Setup

### Prerequisites

- Python 3.11 or newer.
- PostgreSQL 14 or newer.
- Node.js and npm.

### Database Setup

Create a PostgreSQL role and database. Use a local password and do not commit it:

```sql
CREATE ROLE traffic LOGIN PASSWORD 'your-local-password';
CREATE DATABASE traffic_analytics OWNER traffic;
GRANT ALL ON SCHEMA public TO traffic;
```

### Backend Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `DATABASE_URL` in `backend/.env`:

```text
DATABASE_URL=postgresql+psycopg://traffic:your-local-password@127.0.0.1:5432/traffic_analytics
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

Create tables and indexes:

```powershell
python scripts/init_db.py
```

Import and verify the trajectory data:

```powershell
python scripts/import_csv.py
```

To replace an existing import:

```powershell
python scripts/import_csv.py --replace
```

Start FastAPI:

```powershell
uvicorn app.main:app --reload
```

Backend URLs:

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

### Frontend Setup

In a second terminal:

```powershell
cd frontend
npm install
```

Optional `frontend/.env`:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Start Vite:

```powershell
npm run dev
```

Open http://localhost:5173.

Create a production build:

```powershell
npm run build
```

## Environment Variables

### Backend

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `APP_ENV` | Application environment label |
| `CORS_ORIGINS` | Allowed browser origins |
| `LOG_LEVEL` | Backend logging level |

### Frontend

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | FastAPI base URL; defaults to `http://localhost:8000` |

Never commit `.env` files or real passwords.

## Data Validation and Import Safety

The importer requires the core fields, checks non-negative frame and track IDs, checks non-negative timestamps, validates confidence values between `0` and `1`, parses four-value numeric bounding boxes, parses optional numeric fields, rejects malformed rows, refuses to overwrite existing data without `--replace`, preserves missing optional measurements as SQL `NULL`, and prints post-import counts and class totals.

## Testing

The backend tests cover health, metadata, summary, class and timeline analytics, confidence statistics, frame and trajectory retrieval, invalid parameters, and WebSocket replay behavior.

From `backend/` with PostgreSQL configured and data imported:

```powershell
pytest
```

The frontend production build is checked with:

```powershell
cd frontend
npm run build
```

## User-Friendly Analytics

The Analytics page separates simple explanation from technical detail. It uses phrases such as “Road User Composition,” “Traffic Activity,” “Where Traffic Is Concentrated,” “Movement Paths,” “Detection Quality,” and “What was happening at this moment?” while retaining frame IDs, track IDs, confidence values, coordinates, and detailed tables for reviewers who need them.

## Results and Interpretation

Within the supplied recording, the application can show which classes contribute the most observations, when visible road-user activity rises or falls, how class activity changes, where recorded image-space positions are concentrated, how long tracked road users remain visible, what was present at a selected frame, how an individual track moved, and how confidence is distributed.

These results describe the supplied Junction 67 recording. They do not claim long-term traffic behavior, city-wide conditions, live monitoring, or validated collision risk.

## Screenshots

### Dashboard

![Traffic Analytics Dashboard](docs/images/dashboard.png)

### Analytics Overview

![Traffic Analytics Overview](docs/images/analytics-overview.png)

### Analytics Detailed Analysis

![Traffic Analytics Detailed Analysis](docs/images/analytics-analysis.png)

## Limitations

- The dataset is a short recorded sequence of approximately 33.3 seconds.
- Results describe one recording rather than long-term traffic patterns.
- Speed and heading measurements are unavailable.
- UTM/GPS coordinates are unavailable.
- Spatial results use recorded image/video coordinates.
- No validated crash labels or collision-risk model is included.
- The application does not ingest live camera footage.
- The annotated MP4 is not currently present in this workspace.

## Future Work

Possible future extensions, not current features, include live CCTV ingestion, longer and multi-day datasets, calibrated geographic mapping, validated speed and heading estimation, traffic-signal integration, historical comparison, anomaly detection, multi-junction comparison, and a validated collision-risk model with appropriate labels.

## Conclusion

This project provides an end-to-end analytics and visualization layer over recorded computer-vision traffic output. It combines CSV validation, PostgreSQL persistence, FastAPI REST services, WebSocket replay, and React visualization to create an interactive research environment for Junction 67.

The system keeps the analytical experience understandable while preserving technical accuracy: observations remain distinct from track IDs, image coordinates remain distinct from geographic coordinates, and unavailable measurements are never fabricated.

## Project Information

- **Project**: Traffic Analytics Dashboard
- **Institution**: SVNIT Surat
- **Location**: Junction 67
- **Author**: [Your Name]
