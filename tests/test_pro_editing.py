import unittest

from core.pro_editing import HOOK_STYLES, build_hook_overlay, build_retention_plan


class ProEditingTests(unittest.TestCase):
    def test_hook_style_catalog_has_twelve_or_more_choices(self):
        self.assertGreaterEqual(len(HOOK_STYLES), 12)
        self.assertEqual(len(HOOK_STYLES), len(set(HOOK_STYLES)))

    def test_hook_overlay_is_short_and_nonempty(self):
        for style in HOOK_STYLES:
            text = build_hook_overlay(style, "basketball moment", "The crowd could not believe it")
            self.assertTrue(text)
            self.assertLessEqual(len(text), 60)

    def test_retention_plan_tracks_actual_beats(self):
        plan = build_retention_plan([
            {"role": "HOOK", "text": "Wait for it", "target_screen_duration": 2},
            {"role": "PAYOFF", "text": "The ball goes in", "target_screen_duration": 4},
        ], 10)
        self.assertEqual(len(plan["beats"]), 2)
        self.assertEqual(plan["beats"][0]["role"], "HOOK")
        self.assertIn("never fabricated", plan["rules"][1])

    def test_dynamic_captions_do_not_double_draw_active_words(self):
        import tempfile
        from core.video_processor import _dynamic_caption_filters

        with tempfile.TemporaryDirectory() as directory:
            filters = _dynamic_caption_filters(
                "One two three four five six",
                3.0,
                {"enabled": True, "style": "Bold Viral"},
                textfile_dir=directory,
            )
        # Two 3-word phrase groups should create two drawtext filters, not
        # a phrase plus one overlay per active word.
        self.assertEqual(len(filters), 2)
        self.assertTrue(all("drawtext=" in item for item in filters))

    def test_dynamic_captions_can_be_disabled(self):
        from core.video_processor import _dynamic_caption_filters
        self.assertEqual(
            _dynamic_caption_filters("one two", 1.0, {"enabled": False}),
            [],
        )

    def test_empty_timeline_still_returns_valid_plan(self):
        plan = build_retention_plan([], 30)
        self.assertEqual(plan["beats"], [])
        self.assertEqual(plan["target_duration_seconds"], 30.0)


if __name__ == "__main__":
    unittest.main()
