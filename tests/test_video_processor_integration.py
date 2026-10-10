import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.video_processor import process_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class CaptionRenderIntegrationTests(unittest.TestCase):
    def test_captioned_vertical_render_with_punctuation_and_percent(self):
        with tempfile.TemporaryDirectory(prefix="v2-render-test-") as temp:
            root = Path(temp)
            source = root / "source.mp4"
            output = root / "final.mp4"

            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(source),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=90,
            )

            result = process_video(
                input_path=str(source),
                output_path=str(output),
                script={
                    "target_duration": 2.5,
                    "timeline": [{
                        "path": str(source),
                        "start": 0,
                        "end": 2.5,
                        "duration": 2.5,
                        "text": "Wait, what?! 100% real.",
                        "role": "HOOK",
                    }],
                },
                target_duration=2.5,
                caption_settings={
                    "enabled": True,
                    "style": "Bold Viral",
                    "font_size": 48,
                    "position": "lower-third",
                    "text_color": "white",
                    "highlight_color": "yellow",
                    "stroke": True,
                    "shadow": True,
                    "box": False,
                },
                editing_settings={
                    "dynamic_zoom": False,
                    "punch_in": False,
                    "remove_silence": False,
                    "audio_normalize": False,
                    "smart_subject_tracking": False,
                    "crf": 28,
                },
            )

            self.assertTrue(Path(result).is_file())
            self.assertGreater(Path(result).stat().st_size, 10_000)
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=s=x:p=0", str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(probe.stdout.strip(), "1080x1920")


if __name__ == "__main__":
    unittest.main()
