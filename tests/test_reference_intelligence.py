from core.reference_intelligence import analyze_reference, plan_source_sections


def test_missing_reference_returns_safe_profile():
    profile = analyze_reference(None, "funny moments")
    assert profile["success"] is False
    assert profile["status"] == "not_provided"
    assert "funny" in profile["keywords"]


def test_source_sections_sample_full_duration():
    windows = plan_source_sections({"duration": 120}, max_sections=3, section_seconds=8)
    assert len(windows) == 3
    assert windows[0] == (0.0, 8.0)
    assert windows[-1][1] == 120.0
    assert windows[-1][0] > 30.0
    assert all(end > start for start, end in windows)


def test_short_source_does_not_request_out_of_bounds_windows():
    windows = plan_source_sections({"duration": 5.5}, max_sections=3, section_seconds=8)
    assert windows == [(0.0, 5.5)]


def test_unknown_duration_uses_single_conservative_window():
    windows = plan_source_sections({"url": "https://example.invalid/video"}, max_sections=3)
    assert windows == [(0.0, 8.0)]
