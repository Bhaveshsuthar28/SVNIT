def test_class_distribution(client, metadata):
    response = client.get("/api/analytics/classes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["classes"]
    total = sum(item["detection_records"] for item in payload["classes"])
    assert total == metadata["total_records"]
    assert all("detection_records" in item for item in payload["classes"])
    assert all("vehicles" not in item for item in payload["classes"])


def test_timeline(client, metadata):
    response = client.get("/api/analytics/timeline")
    assert response.status_code == 200
    timeline = response.json()["timeline"]
    assert len(timeline) == metadata["frames"]
    assert timeline[0]["frame"] == metadata["first_frame"]
    assert "active_objects" in timeline[0]


def test_timeline_class_filter(client):
    response = client.get("/api/analytics/timeline", params={"grouped_class": "CAR"})
    assert response.status_code == 200
    timeline = response.json()["timeline"]
    assert all(point["active_objects"] >= 1 for point in timeline)


def test_confidence_statistics(client):
    response = client.get("/api/analytics/confidence", params={"threshold": 0.3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] > 0
    assert payload["minimum"] <= payload["maximum"]
    assert 0 <= payload["count_below_threshold"] <= payload["count"]
    assert payload["threshold"] == 0.3


def test_confidence_invalid_threshold(client):
    response = client.get("/api/analytics/confidence", params={"threshold": 1.5})
    assert response.status_code == 400
    assert response.json()["detail"] == "Confidence threshold must be between 0 and 1."
