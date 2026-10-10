import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.clip_analyzer import _select_non_overlapping
from core.pipeline import run_video_processing
from core.script_generator import generate_script


class StoryPipelineContractTests(unittest.TestCase):
    def test_story_keeps_hook_first_instead_of_source_chronology(self):
        clips = [
            {"start": 20, "end": 24, "duration": 4, "text": "the payoff", "score": 0.9, "hook_score": 1.0, "story_role": "HOOK"},
            {"start": 0, "end": 4, "duration": 4, "text": "the setup", "score": 0.7, "hook_score": 0.1, "story_role": "SETUP"},
            {"start": 5, "end": 9, "duration": 4, "text": "things escalate", "score": 0.8, "hook_score": 0.2, "story_role": "ESCALATION"},
            {"start": 10, "end": 14, "duration": 4, "text": "big reaction", "score": 0.85, "hook_score": 0.3, "story_role": "REACTION"},
            {"start": 15, "end": 19, "duration": 4, "text": "final payoff", "score": 0.88, "hook_score": 0.4, "story_role": "PAYOFF"},
        ]
        result = generate_script(clips, target_duration=30)
        roles = [item["role"] for item in result["timeline"]]
        self.assertEqual(roles[:5], ["HOOK", "SETUP", "ESCALATION", "REACTION", "PAYOFF"])
        self.assertAlmostEqual(sum(item["target_screen_duration"] for item in result["timeline"]), 30.0, places=1)

    def test_clip_selection_never_keeps_overlapping_windows(self):
        candidates = [
            {"start": 10, "end": 20, "score": 0.9},
            {"start": 12, "end": 22, "score": 0.8},
            {"start": 0, "end": 5, "score": 0.7},
        ]
        selected = _select_non_overlapping(candidates, max_clips=3)
        self.assertEqual(len(selected), 2)
        self.assertTrue(any(item["start"] == 10 for item in selected))
        self.assertTrue(any(item["start"] == 0 for item in selected))

    def test_renderer_adapter_allows_nonchronological_story_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            source.write_bytes(b"placeholder")
            output_dir = root / "output"

            def fake_process_video(input_path, output_path, **kwargs):
                Path(output_path).write_bytes(b"rendered")
                return output_path

            sequence = [
                {"start": 20, "end": 25, "text": "hook"},
                {"start": 0, "end": 5, "text": "setup"},
            ]
            with patch("core.video_processor.process_video", side_effect=fake_process_video):
                result = run_video_processing(
                    video_path=source,
                    clip_analysis={"sequence": sequence},
                    output_dir=output_dir,
                    duration=10,
                    caption_settings={"enabled": False},
                    editing_settings={"audio_normalize": False},
                )
            self.assertTrue(result["success"])
            self.assertEqual(result["selected_clips"], 2)
            self.assertTrue(Path(result["output_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
