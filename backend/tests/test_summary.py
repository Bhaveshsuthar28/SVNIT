def test_metadata_dynamic_counts(client, metadata):
    assert metadata["dataset"] == "trajectories67.csv"
    assert metadata["total_records"] > 0
    assert metadata["unique_tracks"] > 0
    assert metadata["frames"] > 0
    assert metadata["start_time_sec"] is not None
    assert metadata["end_time_sec"] is not None
    assert metadata["duration_seconds"] == pytest_approx_duration(metadata)
    assert "cx" in metadata["available"]
    assert "cy" in metadata["available"]
    for field in ("utm_easting", "utm_northing", "speed_kmh", "heading_angle"):
        assert field in metadata["unavailable"]
    assert "Two-Wheeler" in metadata["classes"] or len(metadata["classes"]) > 0


def pytest_approx_duration(metadata):
    start = metadata["start_time_sec"]
    end = metadata["end_time_sec"]
    duration = metadata["duration_seconds"]
    assert abs(duration - (end - start)) < 1e-6
    return duration
