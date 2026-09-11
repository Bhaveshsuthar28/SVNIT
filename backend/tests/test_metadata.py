def test_metadata_dynamic_counts(client, metadata):
    assert metadata["dataset"] == "trajectories67.csv"
    assert metadata["total_records"] > 0
    assert metadata["unique_tracks"] > 0
    assert metadata["frames"] > 0
    start = metadata["start_time_sec"]
    end = metadata["end_time_sec"]
    assert start is not None
    assert end is not None
    assert abs(metadata["duration_seconds"] - (end - start)) < 1e-6
    assert "cx" in metadata["available"]
    assert "cy" in metadata["available"]
    for field in ("utm_easting", "utm_northing", "speed_kmh", "heading_angle"):
        assert field in metadata["unavailable"]
    assert metadata["classes"]
