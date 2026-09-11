import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./services/api";
import { useTrafficSocket } from "./hooks/useTrafficSocket";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, BarChart3, Bike, BusFront, CarFront, ChevronLeft, ChevronRight, Clock3, Database, FastForward, Grid2X2, Pause, PersonStanding, Play, Radar, Rewind, Square, Truck, X } from "lucide-react";

const palette = { CAR: "#1769e0", "Two-Wheeler": "#d97706", "Three-Wheeler": "#7c3aed", Pedestrian: "#dc2626", LCV: "#059669", BUS: "#db2777", HCV: "#0891b2" };
const tabs = ["Map", "Heatmap", "Trajectories", "Combined"];
const fmt = new Intl.NumberFormat("en-IN");
const color = (name) => palette[name] || "#b8c5d6";
const classIcon = { CAR: CarFront, "Two-Wheeler": Bike, "Three-Wheeler": Bike, Pedestrian: PersonStanding, LCV: Truck, BUS: BusFront, HCV: Truck };
function histogram(rows, key, width) {
  if (!rows.length) return [];
  const maximum = Math.max(...rows.map((row) => row[key]));
  const bins = Math.max(1, Math.ceil((maximum + 0.0001) / width));
  return Array.from({ length: bins }, (_, index) => ({ range: `${(index * width).toFixed(index ? 0 : 1)}–${((index + 1) * width).toFixed(index ? 0 : 1)}`, count: rows.filter((row) => row[key] >= index * width && row[key] < (index + 1) * width).length }));
}

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
  const [filters, setFilters] = useState({ grouped_class: "", track_id: "", min_confidence: 0, start_time: "", end_time: "" });
  const [layers, setLayers] = useState({ base: true, heatmap: true, trajectories: true, objects: true, heatmapOpacity: 0.55 });
  const [selected, setSelected] = useState(null);
  const [speed, setSpeed] = useState(1);
  const [playback, setPlayback] = useState("stopped");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [page, setPage] = useState("dashboard");

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
    const params = { limit: 80, grouped_class: filters.grouped_class || undefined, min_confidence: filters.min_confidence || undefined, start_time: filters.start_time || undefined, end_time: filters.end_time || undefined };
    api.trajectories(params).then((response) => setData((old) => ({ ...old, trajectories: response.trajectories || [] }))).catch(() => {});
    api.timeline({ grouped_class: filters.grouped_class || undefined, start_time: filters.start_time || undefined, end_time: filters.end_time || undefined }).then((response) => setData((old) => ({ ...old, timeline: response.timeline }))).catch(() => {});
  }, [filters.grouped_class, filters.min_confidence, filters.start_time, filters.end_time, data.loading, setData]);

  const selectTrack = async (trackId) => {
    try { setSelected(await api.track(trackId)); } catch (error) { setData((old) => ({ ...old, error: error.message })); }
  };
  const seek = (value) => { const target = Number(value); socket.send({ action: "seek", frame: target }); if (frame?.frame !== target) api.frame(target).then(setCurrentFrame).catch(() => {}); };
  const play = () => { socket.send({ action: playback === "paused" ? "resume" : "start" }); setPlayback("playing"); };
  const pause = () => { socket.send({ action: "pause" }); setPlayback("paused"); };
  const stop = () => { socket.send({ action: "stop" }); setPlayback("stopped"); };
  const updateSpeed = (value) => { const next = Number(value); setSpeed(next); socket.send({ action: "set_speed", speed: next }); };
  const seekSeconds = (offset) => {
    const currentTime = frame?.time_sec ?? 0;
    const target = Math.max(0, Math.min(metadata.duration_seconds || 0, currentTime + offset));
    const nearest = (data.timeline || []).reduce((best, point) => Math.abs(point.time_sec - target) < Math.abs(best.time_sec - target) ? point : best, data.timeline[0]);
    if (nearest) seek(nearest.frame);
  };
  const reset = () => { setFilters({ grouped_class: "", track_id: "", min_confidence: 0, start_time: "", end_time: "" }); setSelected(null); seek(metadata?.first_frame || 0); };

  if (data.loading) return <div className="loading-screen">Loading real SVNIT trajectory data…</div>;
  if (data.error && !metadata) return <div className="loading-screen error"><h1>Backend unavailable</h1><p>{data.error}</p><p>Start FastAPI at http://localhost:8000 and refresh this page.</p></div>;

  const metrics = [
    ["Tracked road users", data.summary.total_tracks, "Unique tracking IDs observed", "#2563eb", CarFront],
    ["Recorded observations", data.summary.detection_records, "Road-user observations across frames", "#13a8c7", Database],
    ["Road users in current frame", frame?.active_objects ?? frame?.object_count ?? 0, `Frame ${selectedFrame}`, "#2d9b75", Radar],
    ["Recording duration", `${data.summary.time_span_seconds?.toFixed(1) ?? "—"} s`, "Recorded traffic sequence", "#e18b2f", Clock3],
    ["Most common road user", data.summary.most_frequent_class || "—", "Based on recorded observations", "#735fd0", classIcon[data.summary.most_frequent_class] || CarFront],
  ];

  return <div className={`app-shell ${sidebarOpen ? "sidebar-open" : "sidebar-collapsed"}`}>
    <aside className="sidebar">
      <div className="sidebar-header"><div className="brand-mark"><Activity size={25} strokeWidth={2.4} /></div><div className="brand"><strong>SVNIT Surat</strong><span>Traffic Analytics</span></div><button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}>{sidebarOpen ? <ChevronLeft size={15} /> : <ChevronRight size={15} />}</button></div>
      <nav aria-label="Primary navigation"><button className={page === "dashboard" ? "active" : ""} onClick={() => setPage("dashboard")} title="Dashboard"><Grid2X2 size={17} /><b>Dashboard</b></button><button className={page === "analytics" ? "active" : ""} onClick={() => setPage("analytics")} title="Analytics"><BarChart3 size={17} /><b>Analytics</b></button></nav>
      <div className="sidebar-foot"><span className={`dot ${socket.status === "connected" ? "online" : ""}`} /><b>{socket.status === "connected" ? "Replay connected" : socket.status}</b></div>
    </aside>
    <main id={page} className="dashboard mx-auto w-full">
      {page === "analytics" ? <AnalyticsPage data={data} metadata={metadata} onSelectTrack={selectTrack} /> : <>
      <header><div><p className="eyebrow">SVNIT SURAT · JUNCTION 67</p><h1>Traffic Analytics Dashboard</h1><p className="subtitle">Intersection Monitoring and Recorded Trajectory Replay</p></div><div className="dataset-status"><b>SVNIT</b><span>Surat</span><small><span className="status-dot" /> Database connected · {metadata.dataset}</small></div></header>
      {data.error && <div className="notice">{data.error}</div>}
      <section className="metric-grid">{metrics.map(([label, value, note, accent, Icon]) => <article className="metric" key={label}><i className="metric-icon" style={{ color: accent, background: `${accent}1a` }}><Icon size={17} strokeWidth={2.2} /></i><span>{label}</span><strong>{typeof value === "number" ? fmt.format(value) : value}</strong><small>{note}</small></article>)}</section>
        <section className="workspace">
        <article className="view-card"><div className="card-title"><div><p className="eyebrow">INTERSECTION VIEW</p><h2>Junction 67 coordinate space</h2></div><div className="tabs">{tabs.map((name) => <button className={tab === name ? "selected" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}</div></div>
          <IntersectionView tab={tab} layers={layers} trajectories={visibleTrajectories} objects={visibleObjects} selected={selected} onSelect={selectTrack} playback={playback} speed={speed} selectedFrame={selectedFrame} time={frame?.time_sec} duration={metadata.duration_seconds} minFrame={metadata.first_frame} maxFrame={metadata.last_frame} onPlay={play} onPause={pause} onStop={stop} onSeek={seek} onSeekSeconds={seekSeconds} onSpeed={updateSpeed} />
          <div className="legend">{metadata.classes.map((name) => <span key={name}><i style={{ background: color(name) }} />{name}</span>)}</div>
        </article>
        <aside className="filters"><div className="card-title"><div><p className="eyebrow">DATA CONTROLS</p><h2>Filters</h2></div><button className="text-button" onClick={reset}>Reset</button></div>
          <label>Object type<select value={filters.grouped_class} onChange={(event) => setFilters({ ...filters, grouped_class: event.target.value })}><option value="">All source classes</option>{metadata.classes.map((name) => <option key={name}>{name}</option>)}</select></label>
          <label>Track ID<input type="number" min="0" placeholder="e.g. 2756" value={filters.track_id} onChange={(event) => setFilters({ ...filters, track_id: event.target.value })} /></label>
          <div className="time-range"><span>Time range (seconds)</span><div><input type="number" min="0" max={metadata.end_time_sec} step="0.1" placeholder="From" value={filters.start_time} onChange={(event) => setFilters({ ...filters, start_time: event.target.value })} /><input type="number" min="0" max={metadata.end_time_sec} step="0.1" placeholder="To" value={filters.end_time} onChange={(event) => setFilters({ ...filters, end_time: event.target.value })} /></div></div>
          <label>Minimum confidence <b>{Number(filters.min_confidence).toFixed(2)}</b><input type="range" min="0" max="1" step="0.05" value={filters.min_confidence} onChange={(event) => setFilters({ ...filters, min_confidence: Number(event.target.value) })} /></label>
          <div className="source-note"><strong>Source data limits</strong><span>Speed, heading and UTM coordinates are not available in this dataset.</span></div>
          <div className="layer-controls"><p className="eyebrow">LAYERS</p>{[["base", "Base map"], ["heatmap", "Traffic heatmap"], ["trajectories", "Trajectories"], ["objects", "Vehicle positions"]].map(([key, label]) => <label className="check" key={key}><input type="checkbox" checked={layers[key]} onChange={() => setLayers({ ...layers, [key]: !layers[key] })} />{label}</label>)}<label>Heatmap opacity <b>{Math.round(layers.heatmapOpacity * 100)}%</b><input type="range" min="0" max="1" step="0.05" value={layers.heatmapOpacity} onChange={(event) => setLayers({ ...layers, heatmapOpacity: Number(event.target.value) })} /></label></div>
        </aside>
      </section>
      <section className="lower-grid"><SelectedObject track={selected} onClear={() => setSelected(null)} /><Analytics classes={data.classes} timeline={data.timeline} confidence={data.confidence} duration={metadata.duration_seconds} /></section>
      </>}
    </main>
  </div>;
}

function AnalyticsPage({ data, metadata }) {
  const [frameNumber, setFrameNumber] = useState(metadata.first_frame || 0);
  const [frameData, setFrameData] = useState(data.frame);
  const [frameTime, setFrameTime] = useState(data.frame?.time_sec ?? metadata.start_time_sec ?? 0);
  const [frameError, setFrameError] = useState("");
  const [trackQuery, setTrackQuery] = useState("");
  const [track, setTrack] = useState(null);
  const [trackError, setTrackError] = useState("");
  const [selectedClass, setSelectedClass] = useState("");
  const [filterDraft, setFilterDraft] = useState({ className: "", trackId: "", startTime: "", endTime: "", startFrame: "", endFrame: "", minConfidence: "" });
  const [filters, setFilters] = useState({ className: "", trackId: "", startTime: "", endTime: "", startFrame: "", endFrame: "", minConfidence: "" });
  const [analyticsConfidence, setAnalyticsConfidence] = useState(data.confidence);

  const loadFrame = async (value) => {
    const target = Number(value);
    if (!Number.isInteger(target) || target < metadata.first_frame || target > metadata.last_frame) { setFrameError(`Frame must be between ${metadata.first_frame} and ${metadata.last_frame}.`); return; }
    try { setFrameError(""); setFrameNumber(target); const nextFrame = await api.frame(target); setFrameData(nextFrame); setFrameTime(nextFrame.time_sec ?? 0); } catch (error) { setFrameError(error.message); }
  };
  const loadTime = (value) => {
    const target = Number(value);
    const startTime = metadata.start_time_sec || 0;
    const endTime = metadata.end_time_sec ?? metadata.duration_seconds ?? 0;
    if (!Number.isFinite(target) || target < startTime || target > endTime) { setFrameError(`Time must be between ${startTime.toFixed(1)} and ${endTime.toFixed(1)} seconds.`); return; }
    if (!data.timeline.length) { setFrameError("No timeline data is available for timestamp lookup."); return; }
    const nearest = data.timeline.reduce((best, point) => Math.abs((point.time_sec || 0) - target) < Math.abs((best.time_sec || 0) - target) ? point : best, data.timeline[0]);
    if (nearest) loadFrame(nearest.frame);
  };
  const loadTrack = async (value = trackQuery) => {
    if (typeof value === "object") value = trackQuery;
    if (!value) return;
    try { setTrackError(""); setTrack(await api.track(Number(value))); } catch (error) { setTrack(null); setTrackError(typeof error.message === "string" ? error.message : "Unable to load this road user."); }
  };
  const applyFilters = async () => {
    setFilters(filterDraft);
    if (filterDraft.minConfidence !== "") {
      try { setAnalyticsConfidence(await api.confidence(Number(filterDraft.minConfidence))); } catch (error) { setFrameError(error.message); }
    } else setAnalyticsConfidence(data.confidence);
  };
  const classRows = selectedClass ? data.classes.filter((item) => item.class_name === selectedClass) : data.classes;
  const timeline = data.timeline.filter((item) => (!filters.className || (data.workspace?.class_activity || []).some((row) => row.frame === item.frame && row[filters.className] > 0)) && (filters.startTime === "" || item.time_sec >= Number(filters.startTime)) && (filters.endTime === "" || item.time_sec <= Number(filters.endTime)) && (filters.startFrame === "" || item.frame >= Number(filters.startFrame)) && (filters.endFrame === "" || item.frame <= Number(filters.endFrame))).map((item) => ({ ...item, time: Number(item.time_sec?.toFixed(2) || 0) }));
  const workspace = data.workspace || {};
  const classActivity = workspace.class_activity || [];
  const durationRows = histogram(workspace.track_stats || [], "duration", 2);
  const observationRows = histogram(workspace.track_stats || [], "observations", 20);
  const trajectory = track?.points?.filter((point) => point.cx != null && point.cy != null).map((point) => ({ ...point, position: `${point.cx}, ${point.cy}` })) || [];

  return <>
    <header><div><p className="eyebrow">SVNIT SURAT · JUNCTION 67</p><h1>Traffic Analytics</h1><p className="subtitle">Detailed Analysis of Recorded Junction 67 Trajectories</p></div><div className="dataset-status"><b>SVNIT</b><span>Surat</span><small><span className="status-dot" /> Database connected</small></div></header>
    <section className="analytics-filter-bar"><div><p className="eyebrow">ANALYSIS FILTERS</p><h2>Focus the recorded dataset</h2></div><label>Object class<select value={filterDraft.className} onChange={(event) => setFilterDraft({ ...filterDraft, className: event.target.value })}><option value="">All classes</option>{metadata.classes.map((name) => <option key={name}>{name}</option>)}</select></label><label>Track ID<input type="number" min="0" value={filterDraft.trackId} onChange={(event) => setFilterDraft({ ...filterDraft, trackId: event.target.value })} /></label><label>Time from<input type="number" min="0" max={metadata.end_time_sec} step="0.1" value={filterDraft.startTime} onChange={(event) => setFilterDraft({ ...filterDraft, startTime: event.target.value })} /></label><label>Time to<input type="number" min="0" max={metadata.end_time_sec} step="0.1" value={filterDraft.endTime} onChange={(event) => setFilterDraft({ ...filterDraft, endTime: event.target.value })} /></label><label>Frame from<input type="number" min={metadata.first_frame} max={metadata.last_frame} value={filterDraft.startFrame} onChange={(event) => setFilterDraft({ ...filterDraft, startFrame: event.target.value })} /></label><label>Frame to<input type="number" min={metadata.first_frame} max={metadata.last_frame} value={filterDraft.endFrame} onChange={(event) => setFilterDraft({ ...filterDraft, endFrame: event.target.value })} /></label><label>Min confidence<input type="number" min="0" max="1" step="0.05" value={filterDraft.minConfidence} onChange={(event) => setFilterDraft({ ...filterDraft, minConfidence: event.target.value })} /></label><div className="filter-actions"><button className="primary-small" onClick={applyFilters}>Apply</button><button className="filter-reset" onClick={() => { const empty = { className: "", trackId: "", startTime: "", endTime: "", startFrame: "", endFrame: "", minConfidence: "" }; setFilterDraft(empty); setFilters(empty); setAnalyticsConfidence(data.confidence); setSelectedClass(""); }}>Reset</button></div></section>
    <section className="analytics-kpis">{[["Detection records", metadata.total_records, Database, "#0891b2"], ["Track IDs", metadata.unique_tracks, CarFront, "#1769e0"], ["Frames", metadata.frames, Grid2X2, "#7c3aed"], ["Duration", `${metadata.duration_seconds?.toFixed(1) ?? "—"} s`, Clock3, "#d97706"], ["Average confidence", `${((data.confidence.mean || 0) * 100).toFixed(1)}%`, Radar, "#059669"], ["Most frequent class", data.summary.most_frequent_class || "—", classIcon[data.summary.most_frequent_class] || CarFront, "#db2777"]].map(([label, value, Icon, accent]) => <article className="metric" key={label}><i className="metric-icon" style={{ color: accent, background: `${accent}1a` }}><Icon size={21} strokeWidth={2.2} /></i><span>{label}</span><strong>{typeof value === "number" ? fmt.format(value) : value}</strong><small>Actual dataset value</small></article>)}</section>
    <KeyFindings classes={data.classes} timeline={data.timeline} confidence={data.confidence} duration={metadata.duration_seconds} />
    <section className="analytics-grid two-up">
      <article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">CLASS ANALYSIS</p><h2>Detection Records by Class</h2></div><span className="panel-note">Click a class to filter</span></div><div className="rechart-box class-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={classRows} layout="vertical" margin={{ left: 12, right: 24, top: 4, bottom: 4 }} onClick={(event) => event?.activePayload?.[0] && setSelectedClass(event.activePayload[0].payload.class_name)}><CartesianGrid stroke="#dce4ee" horizontal={false} /><XAxis type="number" tick={{ fontSize: 11, fill: "#40536b" }} /><YAxis type="category" dataKey="class_name" width={92} tick={{ fontSize: 11, fill: "#26364c" }} /><Tooltip formatter={(value) => [fmt.format(value), "Detection records"]} /><Bar dataKey="detection_records" radius={[0, 4, 4, 0]}>{classRows.map((item) => <Cell key={item.class_name} fill={color(item.class_name)} />)}</Bar></BarChart></ResponsiveContainer></div>{selectedClass && <button className="text-button" onClick={() => setSelectedClass("")}>Clear class filter: {selectedClass}</button>}</article>
      <article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">TRAFFIC ACTIVITY</p><h2>Active Objects Over Time</h2></div><span className="panel-note">Recorded frames</span></div><div className="rechart-box"><ResponsiveContainer width="100%" height="100%"><LineChart data={timeline} margin={{ left: 0, right: 12, top: 8, bottom: 4 }}><CartesianGrid stroke="#edf1f5" /><XAxis dataKey="time" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 10, fill: "#74859a" }} tickFormatter={(value) => `${value}s`} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#74859a" }} /><Tooltip labelFormatter={(value) => `Time ${value}s`} formatter={(value) => [value, "Active objects"]} /><Line type="linear" dataKey="active_objects" stroke="#2f76e7" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div></article>
    </section>
    <section className="analytics-panel frame-section"><div className="card-title"><div><p className="eyebrow">FRAME ANALYSIS</p><h2>What was happening at this moment?</h2><p className="section-explanation">Review the road users visible in one recorded video frame. Select a row to follow that road user.</p></div><div className="inline-controls"><label>Frame <input type="number" min={metadata.first_frame} max={metadata.last_frame} value={frameNumber} onChange={(event) => setFrameNumber(event.target.value)} onBlur={(event) => loadFrame(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadFrame(event.target.value)} /></label><label>Timestamp (seconds) <input type="number" min={metadata.start_time_sec || 0} max={metadata.end_time_sec || metadata.duration_seconds} step="0.1" value={frameTime} onChange={(event) => setFrameTime(event.target.value)} onBlur={(event) => loadTime(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadTime(event.target.value)} /></label><button className="primary-small" onClick={() => loadFrame(frameNumber)}>Load frame</button><button className="primary-small" onClick={() => loadTime(frameTime)}>Load time</button></div></div><div className="frame-moment"><strong>Frame {frameData?.frame ?? "—"}</strong><span>{frameData?.time_sec?.toFixed(2) || "—"} seconds</span><b>{frameData?.object_count ?? frameData?.objects?.length ?? 0} road users visible</b></div>{frameError && <p className="inline-error">{frameError}</p>}<div className="frame-layout"><FramePreview frame={frameData} /><div className="table-wrap"><table><caption>Detected road users. Select a row to see its recorded movement.</caption><thead><tr><th>ID</th><th>Type</th><th>Detection confidence</th><th>Position X</th><th>Position Y</th></tr></thead><tbody>{(frameData?.objects || []).map((object) => <tr tabIndex="0" key={object.track_id} onClick={() => { setTrackQuery(String(object.track_id)); loadTrack(String(object.track_id)); }} onKeyDown={(event) => event.key === "Enter" && loadTrack(String(object.track_id))}><td>#{object.track_id}</td><td>{object.class}</td><td>{object.confidence == null ? "Not available" : object.confidence.toFixed(2)}</td><td>{object.cx ?? "—"}</td><td>{object.cy ?? "—"}</td></tr>)}</tbody></table>{!frameData?.objects?.length && <p className="empty-copy">No road users were recorded at this moment.</p>}</div></div></section>
    <section className="analytics-grid two-up"><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">TRACK ANALYSIS</p><h2>Inspect an Individual Track</h2></div><div className="inline-controls"><input aria-label="Track ID" placeholder="Track ID" value={trackQuery} onChange={(event) => setTrackQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadTrack()} /><button className="primary-small" onClick={loadTrack}>Search</button></div></div>{trackError && <p className="inline-error">{trackError}</p>}{track ? <dl className="track-facts">{[["Track ID", track.track_id], ["Class", track.class], ["Source class", track.source_class || "Not available"], ["Trajectory points", track.trajectory_points], ["First seen", `${track.first_time_sec.toFixed(2)} s`], ["Last seen", `${track.last_time_sec.toFixed(2)} s`], ["Duration", `${track.duration_seconds.toFixed(2)} s`], ["Mean confidence", track.confidence_statistics.mean == null ? "—" : track.confidence_statistics.mean.toFixed(2)], ["Last position", `(${track.latest_position.cx ?? "—"}, ${track.latest_position.cy ?? "—"})`]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl> : <p className="empty-copy">Search a track ID or click an object in the frame table.</p>}</article><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">SELECTED TRACK TRAJECTORY</p><h2>{track ? `Track #${track.track_id}` : "Recorded video coordinate space"}</h2></div><span className="panel-note">1280 × 720</span></div>{track ? <div className="rechart-box trajectory-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={trajectory} margin={{ left: 8, right: 12, top: 8, bottom: 8 }}><CartesianGrid stroke="#edf1f5" /><XAxis dataKey="cx" type="number" domain={[0, 1280]} tick={{ fontSize: 10, fill: "#74859a" }} /><YAxis dataKey="cy" type="number" domain={[720, 0]} tick={{ fontSize: 10, fill: "#74859a" }} /><Tooltip formatter={(value, name) => [value, name === "cx" ? "X" : "Y"]} /><Line dataKey="cy" stroke="#2f76e7" dot={false} strokeWidth={2} /></LineChart></ResponsiveContainer></div> : <p className="empty-copy">Select a track to render its complete cx / cy path.</p>}</article></section>
    <section className="analytics-grid three-up"><article className="analytics-panel"><p className="eyebrow">CONFIDENCE ANALYSIS</p><h2>Detection quality</h2><div className="confidence-grid">{[["Mean", data.confidence.mean], ["Median", data.confidence.median], ["Minimum", data.confidence.minimum], ["Maximum", data.confidence.maximum]].map(([label, value]) => <div key={label}><strong>{value == null ? "—" : value.toFixed(2)}</strong><span>{label}</span></div>)}</div><p className="panel-note">{fmt.format(data.confidence.count_below_threshold)} records below {data.confidence.threshold.toFixed(2)} threshold.</p></article><article className="analytics-panel"><p className="eyebrow">DATASET INFORMATION</p><h2>Recorded source</h2><dl className="compact-facts">{[["Dataset", metadata.dataset], ["Frames", fmt.format(metadata.frames)], ["Records", fmt.format(metadata.total_records)], ["Track IDs", fmt.format(metadata.unique_tracks)], ["Time range", `0–${metadata.duration_seconds?.toFixed(1)} s`], ["Video", "1280 × 720"], ["FPS", metadata.fps || "—"]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></article><article className="analytics-panel limitation-panel"><p className="eyebrow">SOURCE DATA LIMITATIONS</p><h2>Interpretation boundary</h2><p>Speed, heading and UTM coordinates are not available in the provided trajectory dataset.</p><p className="panel-note">Do not interpret this source as providing measured speed, heading, crash probability, collision probability, or numerical risk scores. The supplied heatmap is a visual reference only.</p></article></section>
  </>;
}

function KeyFindings({ classes, timeline, confidence, duration }) {
  const topClass = [...classes].sort((left, right) => right.detection_records - left.detection_records)[0];
  const peak = timeline.reduce((best, point) => point.active_objects > best.active_objects ? point : best, timeline[0]);
  const findings = [];
  if (topClass) findings.push(`${topClass.class_name} account for the largest share of recorded observations in this recording.`);
  if (peak?.time_sec != null) findings.push(`The highest number of visible road users occurred around ${peak.time_sec.toFixed(1)} seconds into the recording.`);
  if (confidence?.median != null) findings.push(`Half of the recorded observations have a detection confidence of ${confidence.median.toFixed(2)} or higher.`);
  if (duration != null) findings.push(`This analysis covers a ${duration.toFixed(1)}-second recorded traffic sequence at Junction 67.`);
  return <section className="key-findings"><div><p className="eyebrow">KEY FINDINGS</p><h2>What stands out in this recording?</h2><p className="section-explanation">Short observations calculated from the recorded data.</p></div><div className="finding-list">{findings.slice(0, 4).map((finding, index) => <p key={index}>{finding}</p>)}</div></section>;
}

function AnalyticsChart({ title, eyebrow, data, xKey, dataKey, color: stroke, label }) {
  return <article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div><span className="panel-note">{label}</span></div><div className="rechart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ left: 0, right: 12, top: 8, bottom: 4 }}><CartesianGrid stroke="#dce4ee" /><XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "#40536b" }} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#40536b" }} /><Tooltip formatter={(value) => [fmt.format(value), label]} /><Bar dataKey={dataKey} fill={stroke} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></article>;
}

function DetailedAnalytics({ workspace, metadata, classes, timeline, durationRows, observationRows, activeClass, confidence }) {
  const maxDensity = Math.max(...(workspace.density || []).map((item) => item.count), 1);
  const visibleClasses = activeClass ? classes.filter((name) => name === activeClass) : classes;
  const visibleFlow = (workspace.trajectory_flow || []).filter((item) => !activeClass || item.class_name === activeClass);
  return <>
    <section className="analytics-grid two-up"><AnalyticsChart title="Detection Records Over Time" eyebrow="DETECTION VOLUME" data={workspace.detection_volume || []} xKey="time" dataKey="detection_records" color="#0891b2" label="Detection records" /><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">CLASS ACTIVITY</p><h2>Class Activity Over Time</h2></div><span className="panel-note">Recorded detections per frame</span></div><div className="rechart-box"><ResponsiveContainer width="100%" height="100%"><LineChart data={workspace.class_activity || []}><CartesianGrid stroke="#dce4ee" /><XAxis dataKey="time" tick={{ fontSize: 10, fill: "#40536b" }} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#40536b" }} /><Tooltip /><>{classes.map((name) => <Line key={name} dataKey={name} name={name} stroke={color(name)} strokeWidth={2} dot={false} />)}</></LineChart></ResponsiveContainer></div></article></section>
    <section className="analytics-grid two-up"><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">DETECTION QUALITY</p><h2>Confidence Distribution</h2></div><span className="panel-note">Detection records</span></div><div className="rechart-box"><ResponsiveContainer width="100%" height="100%"><BarChart data={workspace.confidence_histogram || []}><CartesianGrid stroke="#dce4ee" /><XAxis dataKey="range" tick={{ fontSize: 10, fill: "#40536b" }} /><YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#40536b" }} /><Tooltip formatter={(value) => [fmt.format(value), "Records"]} /><Bar dataKey="records" fill="#059669" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></article><AnalyticsChart title="Observed Track Duration Distribution" eyebrow="TRACKING ANALYSIS" data={durationRows} xKey="range" dataKey="count" color="#7c3aed" label="Tracks" /></section>
    <section className="analytics-grid two-up"><AnalyticsChart title="Trajectory Observation Length" eyebrow="TRACKING PERSISTENCE" data={observationRows} xKey="range" dataKey="count" color="#d97706" label="Tracks" /><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">SPATIAL ANALYSIS</p><h2>Traffic Density</h2></div><span className="panel-note">Recorded Video Coordinate Space · 1280 × 720</span></div><div className="density-grid">{(workspace.density || []).map((cell) => <i key={`${cell.x}-${cell.y}`} title={`${cell.count} records`} style={{ opacity: .15 + cell.count / maxDensity * .85 }} />)}</div></article></section>
    <section className="analytics-panel comparison-panel"><div className="card-title"><div><p className="eyebrow">CLASS COMPARISON</p><h2>Detection Records and Track IDs Observed Under Class</h2></div></div><div className="table-wrap"><table><thead><tr><th>Class</th><th>Detection records</th><th>Track IDs observed under class</th><th>Average confidence</th></tr></thead><tbody>{(workspace.comparison || []).map((item) => <tr key={item.class_name}><td><i className="table-color" style={{ background: color(item.class_name) }} />{item.class_name}</td><td>{fmt.format(item.detection_records)}</td><td>{fmt.format(item.track_ids_observed)}</td><td>{item.average_confidence == null ? "—" : item.average_confidence.toFixed(2)}</td></tr>)}</tbody></table></div></section>
    <DetailedAnalyticsExtras workspace={workspace} metadata={metadata} classes={classes} activeClass={activeClass} />
  </>;
}

function DetailedAnalyticsExtras({ workspace, metadata, classes, activeClass }) {
  const flow = (workspace.trajectory_flow || []).filter((item) => !activeClass || item.class_name === activeClass).slice(0, 120);
  const bands = (workspace.timeline_bands || []).filter((item) => !activeClass || item.class_name === activeClass);
  const maxDensity = Math.max(...(workspace.density || []).map((item) => item.count), 1);
  return <>
    <section className="analytics-grid two-up"><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">SPATIAL ANALYSIS</p><h2>Traffic Density</h2></div><span className="panel-note">Recorded Video Coordinate Space · 1280 × 720</span></div><div className="density-grid">{(workspace.density || []).map((cell) => <i key={`${cell.x}-${cell.y}`} title={`${cell.count} records`} style={{ opacity: .12 + cell.count / maxDensity * .88 }} />)}</div></article><article className="analytics-panel"><div className="card-title"><div><p className="eyebrow">TRAJECTORY FLOW</p><h2>Recorded Image-Coordinate Movement</h2></div><span className="panel-note">{flow.length} paths shown</span></div><div className="flow-canvas"><svg viewBox="0 0 1280 720" role="img" aria-label="Trajectory flow in recorded video coordinates"><image href="/assets/junction67-map.png" width="1280" height="720" opacity=".72" />{flow.map((item) => { const points = item.points.map((point) => `${point.cx},${point.cy}`).join(" "); return points && <polyline key={item.track_id} points={points} fill="none" stroke={color(item.class_name)} strokeWidth="2" opacity=".7" />; })}</svg></div></article></section>
    <section className="analytics-panel comparison-panel"><div className="card-title"><div><p className="eyebrow">DETECTED OBJECTS TIMELINE</p><h2>Class observation periods</h2></div><span className="panel-note">Actual frame intervals · {metadata.duration_seconds?.toFixed(1)} s</span></div><div className="timeline-bands">{bands.map((band) => <div className="timeline-band" key={`${band.class_name}-${band.start_frame}`}><b>{band.class_name}</b><i style={{ left: `${band.start_time / (metadata.duration_seconds || 1) * 100}%`, width: `${Math.max(.5, (band.end_time - band.start_time) / (metadata.duration_seconds || 1) * 100)}%`, background: color(band.class_name) }} /></div>)}</div></section>
  </>;
}

function FramePreview({ frame }) {
  return <div className="frame-preview"><svg viewBox="0 0 1280 720" role="img" aria-label={`Recorded frame ${frame?.frame ?? ""}`}><image href="/assets/junction67-map.png" width="1280" height="720" preserveAspectRatio="none" opacity=".8" />{frame?.objects?.map((object) => object.cx != null && object.cy != null && <circle key={object.track_id} className="frame-object-dot" cx={object.cx} cy={object.cy} r="13" fill={color(object.class)} />)}</svg><span className="frame-preview-badge">Loaded frame {frame?.frame ?? "—"} · {frame?.time_sec?.toFixed(2) || "—"} s</span></div>;
}

function IntersectionView({ tab, layers, trajectories, objects, selected, onSelect, playback, speed, selectedFrame, time, duration, minFrame, maxFrame, onPlay, onPause, onStop, onSeek, onSeekSeconds, onSpeed }) {
  const [speedOpen, setSpeedOpen] = useState(false);
  const [draftSpeed, setDraftSpeed] = useState(speed);
  const [speedStart, setSpeedStart] = useState(speed);
  const showBase = layers.base && (tab === "Map" || tab === "Heatmap" || tab === "Combined");
  const showPaths = layers.trajectories && (tab === "Trajectories" || tab === "Combined");
  const showObjects = layers.objects && tab !== "Heatmap" && (tab === "Map" || tab === "Trajectories" || tab === "Combined");
  const showHeatmap = layers.heatmap && (tab === "Heatmap" || tab === "Combined");
  return <div className="canvas-wrap"><svg viewBox="0 0 1280 720" className="intersection" role="img" aria-label="Traffic trajectories in recorded video coordinates">
    <rect width="1280" height="720" className="canvas-bg" />
    {(showBase || showHeatmap) && <image href="/assets/junction67-map.png" x="0" y="0" width="1280" height="720" preserveAspectRatio="none" opacity={showBase ? ".97" : ".35"} />}
    {showHeatmap && <image href="/assets/junction67-heatmap.png" x="0" y="0" width="1280" height="720" preserveAspectRatio="none" opacity={layers.heatmapOpacity} />}
    <text x="28" y="36" className="coordinate-label">RECORDED VIDEO COORDINATES · 1280 × 720</text>
    {showPaths && trajectories.map((trajectory) => { const points = trajectory.points.filter((point) => point.cx != null && point.cy != null).map((point) => `${point.cx},${point.cy}`).join(" "); return points && <polyline key={trajectory.track_id} points={points} fill="none" stroke={color(trajectory.class)} strokeWidth="3" opacity=".6" />; })}
    {showObjects && objects.map((object) => <g className="object" onClick={() => onSelect(object.track_id)} key={object.track_id}><circle className="object-dot" cx={object.cx} cy={object.cy} r="6" fill={color(object.class)} /><text x={(object.cx || 0) + 10} y={(object.cy || 0) - 10}>{object.track_id}</text></g>)}
  </svg>{selected && <div className="frame-object-card"><span>Selected vehicle</span><strong>Track #{selected.track_id}</strong><b>{selected.class}</b><small>Confidence {selected.confidence_statistics.mean == null ? "—" : `${(selected.confidence_statistics.mean * 100).toFixed(1)}%`}</small><small>Position ({selected.latest_position.cx ?? "—"}, {selected.latest_position.cy ?? "—"})</small></div>}<p className="asset-overlay">Recorded video coordinates · 1280 × 720</p><div className="frame-playback"><div className="frame-playback-title"><span>Trajectory Replay</span><b>Frame {selectedFrame}</b><small>{time?.toFixed(2) || "0.00"} s</small></div><div className="frame-playback-actions"><button onClick={() => onSeekSeconds(-10)} title="Back 10 seconds" aria-label="Back 10 seconds"><Rewind size={17} /></button><button onClick={playback === "playing" ? onPause : onPlay} className="play-control" title={playback === "playing" ? "Pause replay" : "Play replay"} aria-label={playback === "playing" ? "Pause replay" : "Play replay"}>{playback === "playing" ? <Pause size={18} /> : <Play size={18} />}</button><button onClick={onStop} title="Stop replay" aria-label="Stop replay"><Square size={15} /></button><button onClick={() => onSeekSeconds(10)} title="Forward 10 seconds" aria-label="Forward 10 seconds"><FastForward size={17} /></button><div className="speed-control"><button className="speed-button" onClick={() => { setDraftSpeed(speed); setSpeedStart(speed); setSpeedOpen(!speedOpen); }} aria-expanded={speedOpen} aria-label="Playback speed">{speed}×</button>{speedOpen && <div className="speed-popover"><strong>Playback speed</strong><output>{Number(draftSpeed).toFixed(2)}×</output><input aria-label="Playback speed slider" type="range" min="0.1" max="2" step="0.05" value={draftSpeed} onChange={(event) => { const nextSpeed = Number(event.target.value); setDraftSpeed(nextSpeed); onSpeed(nextSpeed); }} /><div className="speed-scale"><span>0.1×</span><span>2×</span></div><div className="speed-actions"><button className="speed-close" onClick={() => { onSpeed(speedStart); setDraftSpeed(speedStart); setSpeedOpen(false); }} title="Cancel speed change" aria-label="Cancel speed change"><X size={16} /></button></div></div>}</div></div><input aria-label="Seek replay frame" type="range" min={minFrame} max={maxFrame} value={selectedFrame} onChange={(event) => onSeek(event.target.value)} /><span className="frame-playback-duration">{duration?.toFixed(1) || "0.0"} s</span></div></div>;
}

function SelectedObject({ track, onClear }) {
  if (!track) return <article className="details empty"><p className="eyebrow">SELECTED OBJECT</p><h2>Select a current object</h2><p>Click a bounding box or current point to load its real trajectory and source-data details.</p></article>;
  const fields = [["Track ID", track.track_id], ["Class", track.class], ["Source class", track.source_class || "Not available in source data"], ["Confidence", track.confidence_statistics.mean ? `${(track.confidence_statistics.mean * 100).toFixed(1)}% mean` : "Not available in source data"], ["First / last seen", `${track.first_time_sec.toFixed(3)} s – ${track.last_time_sec.toFixed(3)} s`], ["Trajectory points", track.trajectory_points], ["Latest position", `(${track.latest_position.cx ?? "—"}, ${track.latest_position.cy ?? "—"})`], ["Speed / heading", "Not available in source data"]];
  return <article className="details"><div className="card-title"><div><p className="eyebrow">SELECTED OBJECT</p><h2>Track #{track.track_id}</h2></div><button className="text-button" onClick={onClear}>Clear</button></div><dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></article>;
}

function Analytics({ classes, timeline, confidence, duration }) {
  const maxClass = Math.max(...classes.map((item) => item.detection_records), 1);
  const points = timeline.map((item, index) => `${(index / Math.max(timeline.length - 1, 1)) * 100},${100 - (item.active_objects / Math.max(...timeline.map((point) => point.active_objects), 1)) * 90}`).join(" ");
  return <article className="analytics"><div className="card-title"><div><p className="eyebrow">DATASET ANALYTICS</p><h2>Detection records & activity</h2></div><span className="confidence">Confidence median {confidence.median?.toFixed(2) ?? "—"}</span></div><div className="charts"><div><h3>Detection records by class</h3>{classes.map((item) => <div className="bar-row" key={item.class_name}><span>{item.class_name}</span><div><i style={{ width: `${item.detection_records / maxClass * 100}%`, background: color(item.class_name) }} /></div><b>{fmt.format(item.detection_records)}</b></div>)}</div><div><h3>Active objects over time</h3><svg className="timeline-chart" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={points} fill="none" stroke="#45c9ad" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg><div className="chart-axis"><span>0.0 s</span><span>{duration?.toFixed(1) ?? "—"} s</span></div><p className="chart-note">Actual active detection records per recorded frame.</p></div></div></article>;
}

export default App;
