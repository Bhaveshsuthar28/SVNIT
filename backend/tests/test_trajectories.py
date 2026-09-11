def test_existing_track(client, sample_track_id):
    response = client.get(f"/api/trajectories/{sample_track_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["track_id"] == sample_track_id
    assert payload["class"]
    assert payload["trajectory_points"] == len(payload["points"])
    assert payload["first_frame"] <= payload["last_frame"]
    assert "speed" not in payload
    assert "heading" not in payload
    assert "latest_position" in payload
    assert payload["points"][0]["frame"] <= payload["points"][-1]["frame"]


def test_non_existing_track(client):
    response = client.get("/api/trajectories/99999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Track ID 99999999 was not found."


def test_trajectories_filter_by_track(client, sample_track_id):
    response = client.get("/api/trajectories", params={"track_id": sample_track_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["track_id"] == sample_track_id
    assert payload["points"]


def test_frame_endpoint(client, metadata):
    frame = metadata["first_frame"]
    response = client.get(f"/api/frames/{frame}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["frame"] == frame
    assert payload["object_count"] == len(payload["objects"])
    if payload["objects"]:
        obj = payload["objects"][0]
        assert "track_id" in obj
        assert "class" in obj
        assert "cx" in obj
        assert "cy" in obj


def test_invalid_frame(client, metadata):
    response = client.get(f"/api/frames/{metadata['last_frame'] + 25}")
    assert response.status_code == 400
    assert "Frame must be between" in response.json()["detail"]


def test_invalid_confidence_filter(client):
    response = client.get("/api/trajectories", params={"min_confidence": 2})
    assert response.status_code == 400
    assert response.json()["detail"] == "Confidence threshold must be between 0 and 1."
