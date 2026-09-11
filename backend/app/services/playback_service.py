from __future__ import annotations

import asyncio
import bisect
import logging
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from app.schemas import FrameObject, WebSocketFrame

logger = logging.getLogger(__name__)

ALLOWED_SPEEDS = {0.25, 0.5, 1.0, 2.0, 4.0}


@dataclass
class CachedObject:
    track_id: int
    class_name: str
    confidence: float | None
    cx: float | None
    cy: float | None
    bbox: list | None


@dataclass
class CachedFrame:
    frame: int
    time_sec: float | None
    objects: list[CachedObject] = field(default_factory=list)

    @property
    def class_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter(obj.class_name for obj in self.objects)
        return dict(counts)


class PlaybackCache:
    def __init__(self) -> None:
        self.frames: dict[int, CachedFrame] = {}
        self.ordered_frames: list[int] = []
        self.min_frame: int | None = None
        self.max_frame: int | None = None
        self.loaded = False

    def clear(self) -> None:
        self.frames.clear()
        self.ordered_frames = []
        self.min_frame = None
        self.max_frame = None
        self.loaded = False

    def load(self, records) -> None:
        grouped: dict[int, list] = defaultdict(list)
        times: dict[int, float] = {}
        for record in records:
            grouped[record.frame].append(
                CachedObject(
                    track_id=record.track_id,
                    class_name=record.grouped_class,
                    confidence=record.confidence,
                    cx=record.cx,
                    cy=record.cy,
                    bbox=record.bbox,
                )
            )
            times[record.frame] = record.time_sec

        self.frames = {
            frame: CachedFrame(frame=frame, time_sec=times.get(frame), objects=objects)
            for frame, objects in grouped.items()
        }
        self.ordered_frames = sorted(self.frames)
        self.min_frame = self.ordered_frames[0] if self.ordered_frames else None
        self.max_frame = self.ordered_frames[-1] if self.ordered_frames else None
        self.loaded = True
        logger.info(
            "Playback cache loaded: %s frames, %s records",
            len(self.ordered_frames),
            sum(len(frame.objects) for frame in self.frames.values()),
        )

    def get_frame(self, frame: int) -> CachedFrame | None:
        return self.frames.get(frame)

    def next_frame(self, frame: int) -> int | None:
        next_index = bisect.bisect_right(self.ordered_frames, frame)
        if next_index >= len(self.ordered_frames):
            return None
        return self.ordered_frames[next_index]

    def estimated_fps(self) -> float:
        if self.min_frame is None or self.max_frame is None or self.max_frame == self.min_frame:
            return 30.0
        start = self.frames[self.min_frame].time_sec or 0.0
        end = self.frames[self.max_frame].time_sec or 0.0
        duration = end - start
        if duration <= 0:
            return 30.0
        return (len(self.ordered_frames) - 1) / duration


playback_cache = PlaybackCache()


def build_websocket_frame(cached: CachedFrame) -> dict:
    payload = WebSocketFrame(
        type="frame",
        frame=cached.frame,
        time_sec=cached.time_sec,
        active_objects=len(cached.objects),
        class_counts=cached.class_counts,
        objects=[
            FrameObject(
                track_id=obj.track_id,
                class_name=obj.class_name,
                confidence=obj.confidence,
                cx=obj.cx,
                cy=obj.cy,
                bbox=obj.bbox,
            )
            for obj in cached.objects
        ],
    )
    return payload.model_dump(by_alias=True)


class PlaybackSession:
    def __init__(self, cache: PlaybackCache | None = None) -> None:
        self.cache = cache or playback_cache
        self.state = "stopped"
        self.frame = self.cache.min_frame or 0
        self.speed = 1.0
        self._task: asyncio.Task | None = None
        self._send = None
        self._lock = asyncio.Lock()

    async def attach(self, send) -> None:
        self._send = send

    async def handle_command(self, message: dict) -> dict:
        action = str(message.get("action", "")).lower()
        if action == "start":
            return await self.start()
        if action == "pause":
            return await self.pause()
        if action == "resume":
            return await self.resume()
        if action == "stop":
            return await self.stop()
        if action == "seek":
            if "frame" not in message:
                return {"type": "error", "detail": "Seek requires a frame value."}
            frame = self._parse_frame(message["frame"])
            if frame is None:
                return {"type": "error", "detail": "Seek frame must be an integer."}
            return await self.seek(frame)
        if action == "set_speed":
            if "speed" not in message:
                return {"type": "error", "detail": "set_speed requires a speed value."}
            speed = self._parse_speed(message["speed"])
            if speed is None:
                return {"type": "error", "detail": "Playback speed must be numeric."}
            return await self.set_speed(speed)
        return {
            "type": "error",
            "detail": "Unsupported action. Use start, pause, resume, stop, seek, or set_speed.",
        }

    async def start(self) -> dict:
        async with self._lock:
            self.frame = self.cache.min_frame or 0
            self.state = "playing"
            self._ensure_task()
        await self._emit_current_frame()
        return self._status("Playback started.")

    async def pause(self) -> dict:
        async with self._lock:
            self.state = "paused"
        return self._status("Playback paused.")

    async def resume(self) -> dict:
        async with self._lock:
            if self.state == "stopped":
                self.frame = self.cache.min_frame or 0
            self.state = "playing"
            self._ensure_task()
        await self._emit_current_frame()
        return self._status("Playback resumed.")

    async def stop(self) -> dict:
        async with self._lock:
            self.state = "stopped"
            self.frame = self.cache.min_frame or 0
        await self._emit_current_frame()
        return self._status("Playback stopped.")

    async def seek(self, frame: int) -> dict:
        if self.cache.min_frame is None or self.cache.max_frame is None:
            return {"type": "error", "detail": "Playback cache is empty."}
        if frame < self.cache.min_frame or frame > self.cache.max_frame:
            return {
                "type": "error",
                "detail": (
                    f"Frame must be between {self.cache.min_frame} and {self.cache.max_frame}."
                ),
            }
        if self.cache.get_frame(frame) is None:
            return {"type": "error", "detail": f"Frame {frame} is not available in the playback cache."}
        async with self._lock:
            self.frame = frame
        await self._emit_current_frame()
        return self._status(f"Seeked to frame {frame}.")

    async def set_speed(self, speed: float) -> dict:
        if speed not in ALLOWED_SPEEDS:
            allowed = ", ".join(str(value) for value in sorted(ALLOWED_SPEEDS))
            return {"type": "error", "detail": f"Speed must be one of: {allowed}."}
        async with self._lock:
            self.speed = speed
        return self._status(f"Playback speed set to {speed}x.")

    async def close(self) -> None:
        async with self._lock:
            self.state = "stopped"
            task = self._task
            self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _ensure_task(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="playback-loop")

    async def _run_loop(self) -> None:
        fps = self.cache.estimated_fps()
        interval = 1.0 / fps if fps > 0 else 1.0 / 30.0
        next_tick = time.monotonic()
        try:
            while True:
                async with self._lock:
                    state = self.state
                    speed = self.speed
                    current_frame = self.frame
                if state != "playing":
                    await asyncio.sleep(0.02)
                    next_tick = time.monotonic()
                    continue

                next_frame = self.cache.next_frame(current_frame)
                if next_frame is None:
                    async with self._lock:
                        self.state = "stopped"
                    if self._send is not None:
                        await self._send(self._status("Playback reached the last frame."))
                    return

                next_tick += interval / speed
                delay = next_tick - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    next_tick = time.monotonic()

                async with self._lock:
                    if self.state != "playing":
                        continue
                    # Recalculate after the wait so a concurrent seek cannot
                    # be overwritten by a next frame chosen before the wait.
                    next_frame = self.cache.next_frame(self.frame)
                    if next_frame is None:
                        self.state = "stopped"
                        reached_end = True
                    else:
                        self.frame = next_frame
                        reached_end = False
                if reached_end:
                    if self._send is not None:
                        await self._send(self._status("Playback reached the last frame."))
                    return
                await self._emit_current_frame()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Playback loop failed")

    async def _emit_current_frame(self) -> None:
        cached = self.cache.get_frame(self.frame)
        if cached is None or self._send is None:
            return
        await self._send(build_websocket_frame(cached))

    def _status(self, message: str) -> dict:
        return {
            "type": "status",
            "state": self.state,
            "frame": self.frame,
            "speed": self.speed,
            "message": message,
        }

    @staticmethod
    def _parse_frame(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, float) and not value.is_integer():
            return None
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_speed(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            speed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return speed if math.isfinite(speed) else None
