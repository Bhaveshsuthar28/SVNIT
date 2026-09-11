import json

from app.services.playback_service import ALLOWED_SPEEDS


def _send(ws, payload: dict) -> None:
    ws.send_text(json.dumps(payload))


def _recv_until(ws, message_type: str, timeout: float = 5.0) -> dict:
    while True:
        message = ws.receive_json()
        if message.get("type") == message_type:
            return message


def test_websocket_connection(client):
    with client.websocket_connect("/ws/traffic") as ws:
        status = ws.receive_json()
        assert status["type"] == "status"
        assert status["state"] == "stopped"
        assert status["cache_loaded"] is True


def test_websocket_start_pause_resume(client, metadata):
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        _send(ws, {"action": "start"})
        frame = _recv_until(ws, "frame")
        assert frame["frame"] == metadata["first_frame"]
        assert "objects" in frame
        assert frame["active_objects"] == len(frame["objects"])
        assert "class_counts" in frame
        status = _recv_until(ws, "status")
        assert status["state"] == "playing"

        _send(ws, {"action": "pause"})
        paused = _recv_until(ws, "status")
        assert paused["state"] == "paused"
        paused_frame = paused["frame"]

        _send(ws, {"action": "resume"})
        resumed_frame = _recv_until(ws, "frame")
        resumed_status = _recv_until(ws, "status")
        assert resumed_status["state"] == "playing"
        assert resumed_frame["frame"] == paused_frame


def test_websocket_seek(client, metadata):
    target = min(metadata["first_frame"] + 10, metadata["last_frame"])
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        _send(ws, {"action": "seek", "frame": target})
        frame = _recv_until(ws, "frame")
        status = _recv_until(ws, "status")
        assert frame["frame"] == target
        assert status["frame"] == target


def test_websocket_set_speed(client):
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        _send(ws, {"action": "set_speed", "speed": 2})
        status = ws.receive_json()
        assert status["type"] == "status"
        assert status["speed"] == 2
        _send(ws, {"action": "set_speed", "speed": 3})
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "Speed must be one of" in error["detail"]
        assert 2.0 in ALLOWED_SPEEDS


def test_websocket_rejects_malformed_command_values(client):
    with client.websocket_connect("/ws/traffic") as ws:
        ws.receive_json()
        _send(ws, {"action": "seek", "frame": "not-a-frame"})
        assert ws.receive_json() == {"type": "error", "detail": "Seek frame must be an integer."}

        _send(ws, {"action": "set_speed", "speed": "fast"})
        assert ws.receive_json() == {"type": "error", "detail": "Playback speed must be numeric."}
