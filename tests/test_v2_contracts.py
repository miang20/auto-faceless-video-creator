import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.clip_finder import parse_section
from core.pipeline import _build_peak_moments, run_video_processing
from core.sequence_builder import build_sequence
from core import video_processor


class V2ContractTests(unittest.TestCase):
    def test_story_timestamps_accept_script_generator_contract(self):
        moments = _build_peak_moments([
            {
                "source_start": "12.25",
                "source_end": "16.75",
                "text": "payoff moment",
            },
            {"source_start": 5, "source_end": 5, "text": "invalid"},
            {"text": "missing timestamps"},
        ])
        self.assertEqual(len(moments), 1)
        self.assertEqual(moments[0]["start"], 12.25)
        self.assertEqual(moments[0]["end"], 16.75)
        self.assertEqual(moments[0]["text"], "payoff moment")

    def test_section_filename_timestamp_contract(self):
        parsed = parse_section("abc123__10_250__20_750.mp4")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["video_id"], "abc123")
        self.assertEqual(parsed["start"], 10.25)
        self.assertEqual(parsed["end"], 20.75)
        self.assertEqual(parsed["duration"], 10.5)

    def test_sequence_builder_accepts_candidate_report_shape(self):
        candidates = {
            "candidates": [
                {
                    "source_video_id": "source-a",
                    "start": 0,
                    "end": 4.5,
                    "duration": 4.5,
                    "local_path": "/tmp/a.mp4",
                    "local_start": 0,
                    "local_end": 4.5,
                    "final_score": 0.9,
                    "beat_id": "hook",
                    "beat_text": "opening hook",
                },
                {
                    "source_video_id": "source-b",
                    "start": 10,
                    "end": 15.5,
                    "duration": 5.5,
                    "local_path": "/tmp/b.mp4",
                    "local_start": 1,
                    "local_end": 6.5,
                    "final_score": 0.8,
                    "beat_id": "payoff",
                    "beat_text": "payoff",
                },
            ]
        }
        result = build_sequence(
            {"peak_moments": []},
            candidates,
            target_duration=10,
            editing_settings={"reaction_selection": True},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["clip_count"], 2)
        self.assertEqual(
            [item["local_path"] for item in result["sequence"]],
            ["/tmp/a.mp4", "/tmp/b.mp4"],
        )

    def test_renderer_preserves_local_section_path_and_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.mp4"
            section = root / "section.mp4"
            source.write_bytes(b"source")
            section.write_bytes(b"section")
            output_dir = root / "out"
            captured = {}

            def fake_process_video(**kwargs):
                captured.update(kwargs)
                Path(kwargs["output_path"]).write_bytes(b"rendered-mp4")
                return kwargs["output_path"]

            with patch("core.video_processor.process_video", side_effect=fake_process_video):
                result = run_video_processing(
                    video_path=source,
                    clip_analysis={
                        "sequence": [{
                            "local_path": str(section),
                            "local_start": 1.0,
                            "local_end": 2.5,
                            "start": 10.0,
                            "end": 20.0,
                            "duration": 1.5,
                            "text": "local clip caption",
                            "role": "HOOK",
                        }]
                    },
                    output_dir=output_dir,
                    duration=10,
                    caption_settings={"enabled": True},
                    editing_settings={"dynamic_zoom": False},
                )

            self.assertTrue(result["success"])
            timeline = captured["script"]["timeline"]
            self.assertEqual(timeline[0]["path"], str(section))
            self.assertEqual(timeline[0]["start"], 1.0)
            self.assertEqual(timeline[0]["end"], 2.5)
            self.assertEqual(timeline[0]["text"], "local clip caption")

    def test_silence_filter_uses_explicit_output_fps(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.mp4"
            output = Path(tmp) / "segment.mp4"
            source.write_bytes(b"placeholder")
            captured = {}

            def fake_run(command, timeout=None):
                captured["command"] = command
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(video_processor, "_probe_dimensions", return_value=(1920, 1080)), \
                 patch.object(video_processor, "_detect_internal_silence", return_value=[(0.2, 0.4)]), \
                 patch.object(video_processor, "_run_command", side_effect=fake_run):
                video_processor._render_single_segment(
                    input_path=str(source),
                    output_path=str(output),
                    clip={"path": str(source), "start": 0, "duration": 1},
                    output_width=1080,
                    output_height=1920,
                    fps=30,
                    editing_settings={
                        "remove_silence": True,
                        "dynamic_zoom": False,
                        "punch_in": False,
                        "smart_subject_tracking": False,
                        "audio_normalize": False,
                    },
                    caption_settings={"enabled": False},
                )

            command_text = " ".join(captured["command"])
            self.assertIn("setpts=N/(30*TB)", command_text)
            self.assertNotIn("FRAME_RATE*TB", command_text)


if __name__ == "__main__":
    unittest.main()
