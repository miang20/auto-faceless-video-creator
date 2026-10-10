import unittest

from core.pipeline import _build_peak_moments


class PeakMomentContractTests(unittest.TestCase):
    def test_accepts_script_generator_source_timestamps(self):
        result = _build_peak_moments([
            {
                "source_start": 2.5,
                "source_end": 7.0,
                "text": "Perfect timing",
                "role": "HOOK",
            }
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["start"], 2.5)
        self.assertEqual(result[0]["end"], 7.0)
        self.assertEqual(result[0]["text"], "Perfect timing")

    def test_accepts_legacy_clip_timestamps(self):
        result = _build_peak_moments([
            {"start": "1", "end": "4", "caption": "Whoa"}
        ])
        self.assertEqual(result, [
            {"index": 1, "text": "Whoa", "start": 1.0, "end": 4.0}
        ])

    def test_skips_invalid_or_zero_length_beats(self):
        result = _build_peak_moments([
            {"source_start": 5, "source_end": 5, "text": "empty"},
            {"source_start": "bad", "source_end": 8},
            None,
            {"start": 1, "end": 3, "beat_text": "Valid"},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Valid")


if __name__ == "__main__":
    unittest.main()
