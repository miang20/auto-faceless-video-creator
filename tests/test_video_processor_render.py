import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.video_processor import process_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class VideoProcessorRenderTests(unittest.TestCase):
    def test_captioned_vertical_render_produces_valid_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.mp4"
            output = root / "final.mp4"

            generated = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "1.5",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(source),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)

            result = process_video(
                input_path=str(source),
                output_path=str(output),
                script={
                    "target_duration": 1.5,
                    "timeline": [{
                        "path": str(source),
                        "start": 0,
                        "end": 1.5,
                        "duration": 1.5,
                        "text": "V2 CAPTION RENDER TEST",
                    }],
                },
                target_duration=1.5,
                caption_settings={
                    "enabled": True,
                    "font": "DejaVuSans-Bold",
                    "font_size": 32,
                    "position": "lower-third",
                    "text_color": "white",
                    "highlight_color": "yellow",
                    "stroke": True,
                    "shadow": True,
                },
                editing_settings={
                    "dynamic_zoom": False,
                    "punch_in": False,
                    "smart_subject_tracking": False,
                    "remove_silence": False,
                    "audio_normalize": False,
                    "crf": 23,
                },
            )

            self.assertEqual(result, str(output))
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 1000)

            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "stream=codec_type,width,height,r_frame_rate",
                    "-show_entries", "format=duration",
                    "-of", "json", str(output),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            metadata = json.loads(probe.stdout)
            video_stream = next(
                stream for stream in metadata["streams"]
                if stream.get("codec_type") == "video"
            )
            self.assertEqual(video_stream["width"], 1080)
            self.assertEqual(video_stream["height"], 1920)
            self.assertTrue(any(
                stream.get("codec_type") == "audio"
                for stream in metadata["streams"]
            ))
            self.assertGreater(float(metadata["format"]["duration"]), 0.5)


if __name__ == "__main__":
    unittest.main()
