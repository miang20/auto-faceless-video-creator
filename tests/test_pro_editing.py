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

    def test_empty_timeline_still_returns_valid_plan(self):
        plan = build_retention_plan([], 30)
        self.assertEqual(plan["beats"], [])
        self.assertEqual(plan["target_duration_seconds"], 30.0)


if __name__ == "__main__":
    unittest.main()
