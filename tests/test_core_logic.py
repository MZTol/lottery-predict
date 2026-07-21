import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import analyzer
import report


class CoreLogicTests(unittest.TestCase):
    def test_current_omission_uses_newest_draw_first(self):
        data = [
            {"period": "004", "numbers": ["02", "04"]},
            {"period": "003", "numbers": ["01", "03"]},
            {"period": "002", "numbers": ["02", "05"]},
            {"period": "001", "numbers": ["01", "04"]},
        ]

        self.assertEqual(
            report._compute_omission(data, "numbers", 5),
            [1, 0, 1, 0, 2],
        )

        cfg = {"total": 5, "pick": 2, "field": "numbers", "zones": 2}
        scores = analyzer.compute_omission_exponential(data, cfg)
        self.assertGreater(scores[4], scores[0])
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores[1], 0)
        self.assertEqual(scores[3], 0)

    def test_follow_scores_track_older_draw_to_newer_draw(self):
        data = [
            {"period": "004", "numbers": ["02"]},
            {"period": "003", "numbers": ["01"]},
            {"period": "002", "numbers": ["02"]},
            {"period": "001", "numbers": ["01"]},
        ]
        cfg = {"total": 3, "pick": 1, "field": "numbers", "zones": 1}

        scores = analyzer.compute_follow_scores(data, cfg)

        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores[2], 0)

    def test_backtest_training_data_is_older_than_target(self):
        data = [
            {"period": str(period), "numbers": ["01"]}
            for period in range(120, 99, -1)
        ]
        cfg = {"total": 3, "pick": 1, "field": "numbers", "zones": 1}
        captured = []

        def fake_dimensions(train, _cfg):
            captured.append([int(e["period"]) for e in train])
            return {name: [0.0] * _cfg["total"] for name in analyzer.DEFAULT_WEIGHTS}

        with patch("analyzer.compute_all_dimensions", side_effect=fake_dimensions):
            analyzer._backtest_window_dims(data, cfg, window=10, test_count=2)

        self.assertEqual(captured[0], list(range(119, 109, -1)))
        self.assertEqual(captured[1], list(range(118, 108, -1)))
        self.assertTrue(all(p < 120 for p in captured[0]))
        self.assertTrue(all(p < 119 for p in captured[1]))


if __name__ == "__main__":
    unittest.main()
