import shutil
import subprocess
from pathlib import Path

import pytest

from core.video_processor import build_video_report, process_video


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required for render smoke test")
def test_real_ffmpeg_render_captions_zoom_silence_and_audio(tmp_path):
    source = tmp_path / "synthetic_source.mp4"
    output = tmp_path / "final_smoke.mp4"

    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=2",
        "-af", "volume=enable='between(t\\,0.7\\,1.1)':volume=0",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(source),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)

    process_video(
        input_path=str(source),
        output_path=str(output),
        script={
            "target_duration": 2,
            "timeline": [{
                "path": str(source),
                "start": 0,
                "end": 2,
                "duration": 2,
                "text": "It's 100% perfect: wow, really?",
                "role": "HOOK",
            }],
        },
        target_duration=2,
        caption_settings={
            "enabled": True,
            "style": "Bold Viral",
            "font_size": 48,
            "text_color": "white",
            "highlight_color": "yellow",
            "position": "lower-third",
        },
        editing_settings={
            "make_vertical": True,
            "dynamic_zoom": True,
            "punch_in": True,
            "remove_silence": True,
            "normalize_audio": True,
            "audio_normalize": True,
            "crf": 23,
        },
    )

    assert output.is_file() and output.stat().st_size > 10_000
    report = build_video_report(str(output))
    assert report["width"] == 1080
    assert report["height"] == 1920
    assert report["duration"] < 1.95
    assert report["duration"] > 0.5

    # Confirm the active-word highlight is actually burned into rendered pixels,
    # rather than allowing a silent fallback to an uncaptioned video.
    frame = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", "0.15", "-i", str(output), "-frames:v", "1",
            "-vf", "crop=1080:420:0:1050",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ],
        check=True, capture_output=True, timeout=30,
    ).stdout
    yellow_pixels = sum(
        1 for i in range(0, len(frame) - 2, 3)
        if frame[i] > 150 and frame[i + 1] > 130 and frame[i + 2] < 120
    )
    assert yellow_pixels > 20, f"Expected yellow word-highlight pixels, found {yellow_pixels}"
