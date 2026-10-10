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
    assert any("enable='between(t\\," in item for item in filters)


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
