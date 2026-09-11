const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, params) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== "" && value !== undefined && value !== null) url.searchParams.set(key, value);
  });
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  baseUrl: API_BASE_URL,
  health: () => request("/api/health"),
  metadata: () => request("/api/metadata"),
  summary: (frame) => request("/api/summary", frame === undefined ? undefined : { frame }),
  classes: () => request("/api/analytics/classes"),
  timeline: (params) => request("/api/analytics/timeline", params),
  confidence: (threshold) => request("/api/analytics/confidence", threshold === undefined ? undefined : { threshold }),
  workspace: () => request("/api/analytics/workspace"),
  frame: (frame) => request(`/api/frames/${frame}`),
  trajectories: (params) => request("/api/trajectories", params),
  track: (trackId) => request(`/api/trajectories/${trackId}`),
};

export function websocketUrl() {
  return `${API_BASE_URL.replace(/^http/, "ws")}/ws/traffic`;
}
