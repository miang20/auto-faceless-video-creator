from core.sequence_builder import build_sequence
from core.video_processor import _build_video_filter, _dynamic_caption_filters


def test_dynamic_captions_are_timed_and_word_highlighted():
    filters = _dynamic_caption_filters(
        "Wait what just happened",
        4.0,
        {
            "enabled": True,
            "font_size": 58,
            "position": "lower-third",
            "text_color": "white",
            "highlight_color": "yellow",
        },
    )
    assert filters
    assert any("fontcolor=yellow" in item for item in filters)
    # Commas in the enable expression must be escaped for FFmpeg filtergraph parsing.
    assert any("enable='gte(t\\," in item for item in filters)


def test_caption_toggle_disables_dynamic_text():
    assert _dynamic_caption_filters(
        "Wait what just happened",
        4.0,
        {"enabled": False},
    ) == []


def test_video_filter_contains_dynamic_zoom_and_captions():
    graph = _build_video_filter(
        1920,
        1080,
        1080,
        1920,
        3.5,
        {"dynamic_zoom": True, "punch_in": True},
        {"enabled": True, "font_size": 58},
        caption_text="That was perfect timing",
    )
    assert "zoompan=" in graph
    assert "drawtext=" in graph


def test_sequence_builder_respects_duration_and_carries_local_ranges():
    candidates = []
    for index in range(4):
        candidates.append({
            "beat_id": f"beat_{index}",
            "source_video_id": f"source_{index}",
            "source_url": f"https://youtube.com/watch?v=source_{index}",
            "source_title": f"Relevant moment {index}",
            "local_path": f"downloads/sections/source_{index}.mp4",
            "local_start": 1.0,
            "local_end": 4.5,
            "start": index * 10,
            "end": index * 10 + 10,
            "duration": 3.5,
            "final_score": 0.8 - index * 0.05,
            "semantic_score": 0.7,
            "source_score": 0.6,
            "reaction_score": 0.4 if index == 1 else 0.0,
        })
    result = build_sequence(
        {"content": {"topic": "perfect timing"}},
        {"candidates": candidates},
        target_duration=10,
        editing_settings={
            "reaction_selection": True,
            "contextual_broll": True,
            "visual_change_rhythm": True,
        },
    )
    assert result["success"]
    assert result["sequence"]
    assert result["estimated_duration"] <= 10
    assert all(item["local_end"] > item["local_start"] for item in result["sequence"])

def test_caption_textfiles_preserve_punctuation_without_inline_text(tmp_path):
    from pathlib import Path

    filters = _dynamic_caption_filters(
        "It's 100% perfect: wow, really?",
        2.0,
        {"enabled": True, "font_size": 48},
        textfile_dir=str(tmp_path),
    )
    assert filters
    assert all("textfile=" in item for item in filters)
    assert all("text='" not in item for item in filters)
    saved = [p.read_text(encoding="utf-8") for p in Path(tmp_path).glob("caption_*.txt")]
    assert "It's" in saved
    assert "100%" in saved
    assert "really?" in saved

def test_pipeline_builds_story_blueprint_from_clip_analysis():
    from core.pipeline import run_script_generation

    script = run_script_generation(
        topic="perfect timing",
        research={
            "sources": [{
                "url": "https://youtube.com/watch?v=example",
                "title": "Perfect timing moment",
            }],
        },
        clip_analysis={
            "clips": [{
                "start": 1.0,
                "end": 4.0,
                "duration": 3.0,
                "text": "Wait what just happened",
                "score": 0.95,
                "role": "HOOK",
            }],
        },
        target_duration=10,
        caption_settings={"enabled": True},
        editing_settings={"dynamic_zoom": True},
    )
    assert script["timeline"]
    assert script["story_structure"]
    assert script["visual_editing_plan"]["dynamic_zoom"] is True
    assert script["context_sources"][0]["title"] == "Perfect timing moment"

def test_subject_tracking_builds_time_aware_crop_expression():
    from core.video_processor import _subject_crop_expression, _vertical_crop_filter

    track = [(0.0, 0.0), (0.5, 120.0), (1.0, 260.0)]
    expression = _subject_crop_expression(track)
    assert "if(lt(t\\,0.500)" in expression
    assert "260.00" in expression
    graph = _vertical_crop_filter(1920, 1080, 1080, 1920, subject_track=track)
    assert "crop=1080:1920:x='" in graph
    assert "if(lt(t\\,0.500)" in graph

def test_source_analysis_accepts_research_list(monkeypatch):
    import core.pipeline as pipeline

    captured = {}

    def fake_report(topic, sources, reference_url=None):
        captured["topic"] = topic
        captured["sources"] = sources
        captured["reference_url"] = reference_url
        return {"success": True, "sources": sources, "source_count": len(sources)}

    monkeypatch.setattr(pipeline, "build_analysis_report", fake_report)
    source = {"url": "https://youtube.com/watch?v=example", "video_id": "example"}
    report = pipeline.run_source_analysis(
        topic="perfect timing",
        research=[source],
        reference_url=source["url"],
    )
    assert report["success"] is True
    assert captured["sources"] == [source]
    assert report["source_count"] == 1
