import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./services/api";
import { useTrafficSocket } from "./hooks/useTrafficSocket";

const palette = { CAR: "#37b7ff", "Two-Wheeler": "#f2b84b", "Three-Wheeler": "#b590ff", Pedestrian: "#ff7777", LCV: "#56d5a5", BUS: "#ff8e57", HCV: "#ea5ab6" };
const tabs = ["Combined", "Map", "Heatmap", "Trajectories"];
const fmt = new Intl.NumberFormat("en-IN");
const color = (name) => palette[name] || "#b8c5d6";

function useLoad() {
  const [data, setData] = useState({ loading: true, error: "" });
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.health(), api.metadata(), api.summary(), api.classes(), api.timeline(), api.confidence(), api.frame(0), api.trajectories({ limit: 80 })])
      .then(([health, metadata, summary, classes, timeline, confidence, frame, trajectories]) => !cancelled && setData({ health, metadata, summary, classes: classes.classes, timeline: timeline.timeline, confidence, frame, trajectories: trajectories.trajectories, loading: false, error: "" }))
      .catch((error) => !cancelled && setData({ loading: false, error: error.message }));
    return () => { cancelled = true; };
  }, []);
  return [data, setData];
}

function App() {
  const [data, setData] = useLoad();
  const [currentFrame, setCurrentFrame] = useState(null);
  const [tab, setTab] = useState("Combined");
  const [filters, setFilters] = useState({ grouped_class: "", track_id: "", min_confidence: 0 });
  const [layers, setLayers] = useState({ base: true, heatmap: true, trajectories: true, objects: true, heatmapOpacity: 0.55 });
  const [selected, setSelected] = useState(null);
  const [speed, setSpeed] = useState(1);
  const [playback, setPlayback] = useState("stopped");

  const acceptFrame = useCallback((frame) => {
    setCurrentFrame(frame);
    setPlayback("playing");
  }, []);
  const socket = useTrafficSocket(acceptFrame);
  const frame = currentFrame || data.frame;
  const metadata = data.metadata;
  const selectedFrame = frame?.frame ?? metadata?.first_frame ?? 0;

  const visibleObjects = useMemo(() => (frame?.objects || []).filter((object) =>
    (!filters.grouped_class || object.class === filters.grouped_class) &&
    (!filters.track_id || String(object.track_id) === filters.track_id) &&
    (object.confidence ?? 0) >= filters.min_confidence
  ), [frame, filters]);

  const visibleTrajectories = useMemo(() => (data.trajectories || []).filter((trajectory) =>
    (!filters.grouped_class || trajectory.class === filters.grouped_class) &&
    (!filters.track_id || String(trajectory.track_id) === filters.track_id)
  ), [data.trajectories, filters]);

  useEffect(() => {
    if (data.loading) return;
    const params = { limit: 80, grouped_class: filters.grouped_class || undefined, min_confidence: filters.min_confidence || undefined };
    api.trajectories(params).then((response) => setData((old) => ({ ...old, trajectories: response.trajectories || [] }))).catch(() => {});
    api.timeline({ grouped_class: filters.grouped_class || undefined }).then((response) => setData((old) => ({ ...old, timeline: response.timeline }))).catch(() => {});
  }, [filters.grouped_class, filters.min_confidence, data.loading, setData]);

  const selectTrack = async (trackId) => {
    try { setSelected(await api.track(trackId)); } catch (error) { setData((old) => ({ ...old, error: error.message })); }
  };
  const seek = (value) => { const target = Number(value); socket.send({ action: "seek", frame: target }); if (frame?.frame !== target) api.frame(target).then(setCurrentFrame).catch(() => {}); };
  const play = () => { socket.send({ action: playback === "paused" ? "resume" : "start" }); setPlayback("playing"); };
  const pause = () => { socket.send({ action: "pause" }); setPlayback("paused"); };
  const stop = () => { socket.send({ action: "stop" }); setPlayback("stopped"); };
  const updateSpeed = (value) => { const next = Number(value); setSpeed(next); socket.send({ action: "set_speed", speed: next }); };
  const reset = () => { setFilters({ grouped_class: "", track_id: "", min_confidence: 0 }); setSelected(null); seek(metadata?.first_frame || 0); };

  if (data.loading) return <div className="loading-screen">Loading real SVNIT trajectory data…</div>;
  if (data.error && !metadata) return <div className="loading-screen error"><h1>Backend unavailable</h1><p>{data.error}</p><p>Start FastAPI at http://localhost:8000 and refresh this page.</p></div>;

  const metrics = [
    ["Total objects", visibleObjects.length, `Frame ${selectedFrame}`, "#2563eb"],
    ...metadata.classes.filter((name) => name !== "HCV").map((name) => [name, visibleObjects.filter((object) => object.class === name).length, "Current frame", color(name)]),
  ];

  return <div className="app-shell min-h-screen bg-slate-950 text-slate-100 antialiased">
    <aside className="sidebar">
      <div className="brand-mark">S</div><div className="brand"><strong>SVNIT Surat</strong><span>Traffic Analytics</span></div>
      <nav><a className="active" href="#dashboard"><span>▦</span> Dashboard</a></nav>
      <div className="sidebar-foot"><span className={`dot ${socket.status === "connected" ? "online" : ""}`} /> {socket.status === "connected" ? "Replay connected" : socket.status}</div>
    </aside>
    <main id="dashboard" className="dashboard mx-auto w-full">
      <header><div><p className="eyebrow">SVNIT SURAT · JUNCTION 67</p><h1>Traffic Analytics Dashboard</h1><p className="subtitle">Intersection Monitoring and Recorded Trajectory Replay</p></div><div className="dataset-status"><b>SVNIT</b><span>Surat</span><small><span className="status-dot" /> Database connected · {metadata.dataset}</small></div></header>
      {data.error && <div className="notice">{data.error}</div>}
      <section className="metric-grid">{metrics.map(([label, value, note, accent]) => <article className="metric shadow-sm shadow-slate-950/30" key={label}><i className="metric-icon" style={{ color: accent, background: `${accent}1a` }}>●</i><span>{label}</span><strong>{fmt.format(value)}</strong><small>{note}</small></article>)}</section>
      <section className="workspace">
        <article className="view-card"><div className="card-title"><div><p className="eyebrow">INTERSECTION VIEW</p><h2>Junction 67 coordinate space</h2></div><div className="tabs">{tabs.map((name) => <button className={tab === name ? "selected" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div></div>
          <IntersectionView tab={tab} layers={layers} trajectories={visibleTrajectories} objects={visibleObjects} onSelect={selectTrack} />
          <div className="legend">{metadata.classes.map((name) => <span key={name}><i style={{ background: color(name) }} />{name}</span>)}</div>
        </article>
        <aside className="filters"><div className="card-title"><div><p className="eyebrow">DATA CONTROLS</p><h2>Filters</h2></div><button className="text-button" onClick={reset}>Reset</button></div>
          <label>Object type<select value={filters.grouped_class} onChange={(event) => setFilters({ ...filters, grouped_class: event.target.value })}><option value="">All source classes</option>{metadata.classes.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label>Track ID<input type="number" min="0" placeholder="e.g. 2756" value={filters.track_id} onChange={(event) => setFilters({ ...filters, track_id: event.target.value })} /></label>
          <label>Minimum confidence <b>{Number(filters.min_confidence).toFixed(2)}</b><input type="range" min="0" max="1" step="0.05" value={filters.min_confidence} onChange={(event) => setFilters({ ...filters, min_confidence: Number(event.target.value) })} /></label>
          <div className="source-note"><strong>Source data limits</strong><span>Speed, heading and UTM coordinates are not available in this dataset.</span></div>
          {tab === "Combined" && <div className="layer-controls"><p className="eyebrow">LAYERS</p>{[["base", "Base map"], ["heatmap", "Traffic heatmap"], ["trajectories", "Trajectories"], ["objects", "Vehicle positions"]].map(([key, label]) => <label className="check" key={key}><input type="checkbox" checked={layers[key]} onChange={() => setLayers({ ...layers, [key]: !layers[key] })} />{label}</label>)}<label>Heatmap opacity <b>{Math.round(layers.heatmapOpacity * 100)}%</b><input type="range" min="0" max="1" step="0.05" value={layers.heatmapOpacity} onChange={(event) => setLayers({ ...layers, heatmapOpacity: Number(event.target.value) })} /></label></div>}
        </aside>
      </section>
      <section className="lower-grid"><SelectedObject track={selected} onClear={() => setSelected(null)} /><Analytics classes={data.classes} timeline={data.timeline} confidence={data.confidence} /></section>
      <section className="playback"><div><p className="eyebrow">TRAJECTORY REPLAY</p><h2>Frame {selectedFrame} <span>· {frame?.time_sec?.toFixed(3) || "0.000"} s</span></h2></div><div className="controls"><button onClick={play} className="primary">▶ {playback === "paused" ? "Resume" : "Play"}</button><button onClick={pause}>Ⅱ Pause</button><button onClick={stop}>■ Stop</button><select value={speed} onChange={(event) => updateSpeed(event.target.value)}>{[0.25, 0.5, 1, 2, 4].map((item) => <option value={item} key={item}>{item}×</option>)}</select></div><input aria-label="Seek frame" type="range" min={metadata.first_frame} max={metadata.last_frame} value={selectedFrame} onChange={(event) => seek(event.target.value)} /><div className="range-labels"><span>0.0 s</span><span>{metadata.duration_seconds?.toFixed(1)} s · frame {metadata.last_frame}</span></div></section>
    </main>
  </div>;
}

function IntersectionView({ tab, layers, trajectories, objects, onSelect }) {
  const showBase = tab === "Map" || (tab === "Combined" && layers.base);
  const showPaths = tab === "Trajectories" || (tab === "Combined" && layers.trajectories);
  const showObjects = tab !== "Heatmap" && (tab !== "Combined" || layers.objects);
  const showHeatmap = tab === "Heatmap" || (tab === "Combined" && layers.heatmap);
  return <div className="canvas-wrap"><svg viewBox="0 0 1280 720" className="intersection" role="img" aria-label="Traffic trajectories in recorded video coordinates">
    <rect width="1280" height="720" className="canvas-bg" />
    {showBase && <image href="/assets/junction67-map.jpg" x="0" y="0" width="1280" height="720" preserveAspectRatio="none" opacity=".97" />}
    {showHeatmap && <image href="/assets/junction67-heatmap.jpg" x="0" y="0" width="1280" height="720" preserveAspectRatio="none" opacity={layers.heatmapOpacity} />}
    <text x="28" y="36" className="coordinate-label">RECORDED VIDEO COORDINATES · 1280 × 720</text>
    {showPaths && trajectories.map((trajectory) => { const points = trajectory.points.filter((point) => point.cx != null && point.cy != null).map((point) => `${point.cx},${point.cy}`).join(" "); return points && <polyline key={trajectory.track_id} points={points} fill="none" stroke={color(trajectory.class)} strokeWidth="3" opacity=".6" />; })}
    {showObjects && objects.map((object) => <g className="object" onClick={() => onSelect(object.track_id)} key={object.track_id}>{object.bbox && <rect x={object.bbox[0]} y={object.bbox[1]} width={object.bbox[2] - object.bbox[0]} height={object.bbox[3] - object.bbox[1]} stroke={color(object.class)} />}<circle cx={object.cx} cy={object.cy} r="5" fill={color(object.class)} /><text x={(object.cx || 0) + 8} y={(object.cy || 0) - 8}>{object.track_id}</text></g>)}
  </svg><p className="asset-overlay">Current objects and paths use live recorded CSV coordinates. Satellite layer is visual reference only.</p></div>;
}

function SelectedObject({ track, onClear }) {
  if (!track) return <article className="details empty"><p className="eyebrow">SELECTED OBJECT</p><h2>Select a current object</h2><p>Click a bounding box or current point to load its real trajectory and source-data details.</p></article>;
  const fields = [["Track ID", track.track_id], ["Class", track.class], ["Source class", track.source_class || "Not available in source data"], ["Confidence", track.confidence_statistics.mean ? `${(track.confidence_statistics.mean * 100).toFixed(1)}% mean` : "Not available in source data"], ["First / last seen", `${track.first_time_sec.toFixed(3)} s – ${track.last_time_sec.toFixed(3)} s`], ["Trajectory points", track.trajectory_points], ["Latest position", `(${track.latest_position.cx ?? "—"}, ${track.latest_position.cy ?? "—"})`], ["Speed / heading", "Not available in source data"]];
  return <article className="details"><div className="card-title"><div><p className="eyebrow">SELECTED OBJECT</p><h2>Track #{track.track_id}</h2></div><button className="text-button" onClick={onClear}>Clear</button></div><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></article>;
}

function Analytics({ classes, timeline, confidence }) {
  const maxClass = Math.max(...classes.map((item) => item.detection_records), 1);
  const points = timeline.map((item, index) => `${(index / Math.max(timeline.length - 1, 1)) * 100},${100 - (item.active_objects / Math.max(...timeline.map((point) => point.active_objects), 1)) * 90}`).join(" ");
  return <article className="analytics"><div className="card-title"><div><p className="eyebrow">DATASET ANALYTICS</p><h2>Detection records & activity</h2></div><span className="confidence">Confidence median {confidence.median?.toFixed(2) ?? "—"}</span></div><div className="charts"><div><h3>Detection records by class</h3>{classes.map((item) => <div className="bar-row" key={item.class_name}><span>{item.class_name}</span><div><i style={{ width: `${item.detection_records / maxClass * 100}%`, background: color(item.class_name) }} /></div><b>{fmt.format(item.detection_records)}</b></div>)}</div><div><h3>Active objects over time</h3><svg className="timeline-chart" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={points} fill="none" stroke="#45c9ad" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg><div className="chart-axis"><span>0.0 s</span><span>33.3 s</span></div><p className="chart-note">Actual active detection records per recorded frame.</p></div></div></article>;
}

export default App;
