# SVNIT Traffic Analytics Dashboard — Frontend

React + Vite + Tailwind CSS single-page dashboard for the SVNIT Traffic Analytics backend.

## Start

1. Start the FastAPI backend at `http://localhost:8000`.
2. From this directory, install and run the frontend:

```powershell
npm install
npm run dev
```

Open `http://localhost:5173`.

## Configuration

Copy `.env.example` to `.env` to point at another backend:

```text
VITE_API_BASE_URL=http://localhost:8000
```

The dashboard uses FastAPI REST endpoints for metadata, summary, charts and selected-track details, and one managed WebSocket connection for recorded trajectory replay. It does not include mock traffic data or client-side detection.

No map, heatmap, or annotated-video asset was supplied in this workspace. The coordinate visualizer therefore clearly identifies itself as the real `1280 × 720` video-coordinate view, rather than pretending it is a geographic map or generated heatmap.
