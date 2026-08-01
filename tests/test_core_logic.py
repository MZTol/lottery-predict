import os
import sys
import tempfile
import unittest
from collections import Counter
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import analyzer
import prediction_store
import report
import review_report


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

    def test_saved_prediction_can_be_evaluated_against_actual_draw(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            areas = [(
                "前区",
                "front",
                {
                    "hot": ["01", "02", "03", "04", "05"],
                    "cold": ["06", "07", "08", "09", "10"],
                    "kill_a": ["11", "12", "13", "14", "15"],
                    "kill_b": ["16", "17", "18", "19", "20"],
                    "kill_c": ["21", "22", "23", "24", "25"],
                },
                Counter({1: 5, 2: 4, 3: 3, 4: 2, 5: 1}),
                {"total": 35, "pick": 5},
            )]

            prediction_store.save_prediction("dlt", 123, 123, areas, filename=filename)
            evaluation = prediction_store.evaluate_prediction(
                "dlt",
                {"period": "123", "front": ["01", "03", "05", "07", "09"]},
                filename=filename,
            )

        self.assertEqual(evaluation["period"], "123")
        self.assertEqual(evaluation["areas"][0]["actual"], [1, 3, 5, 7, 9])
        hot = next(c for c in evaluation["areas"][0]["comparisons"] if c["name"] == "hot")
        self.assertEqual(hot["hits"], [1, 3, 5])
        self.assertEqual(hot["misses"], [2, 4])
        self.assertEqual(hot["uncovered"], [7, 9])
        rec = next(c for c in evaluation["areas"][0]["comparisons"] if c["name"] == "recommendation")
        self.assertEqual(rec["predicted"], [1, 2, 3, 4, 5])

    def test_prediction_history_comparison_lists_recent_draw_differences(self):
        data = [
            {"period": "004", "numbers": ["01", "03", "05"]},
            {"period": "003", "numbers": ["02", "04", "06"]},
        ]
        predictions = {
            "hot": ["01", "02", "03"],
            "cold": ["04", "05", "06"],
            "kill_a": ["07", "08", "09"],
            "kill_b": ["01", "04", "07"],
            "kill_c": ["02", "05", "08"],
        }
        counter = Counter({1: 5, 2: 4, 3: 3})

        html = report._prediction_history_comparison(
            data, "numbers", predictions, counter, pick=3, periods=2
        )

        self.assertIn("004", html)
        self.assertIn("003", html)
        self.assertIn("热门重号", html)
        self.assertIn("综合命中", html)
        self.assertIn("开奖未覆盖", html)
        self.assertIn("综合未出现", html)
        self.assertIn("01", html)
        self.assertIn("05", html)

    def test_review_report_compares_saved_predictions_to_random_baseline(self):
        store = {
            "dlt": {
                "123": {
                    "period": "123",
                    "generated_at": "2026-01-01 18:00:00",
                    "areas": {
                        "front": {
                            "label": "前区",
                            "field": "front",
                            "total": 35,
                            "predictions": {
                                "hot": ["01", "02", "03", "04", "05"],
                                "kill_a": ["06", "07", "08", "09", "10"],
                            },
                            "recommendation": ["01", "02", "03", "04", "05"],
                        }
                    },
                }
            }
        }
        history = [
            {"period": "123", "front": ["01", "03", "05", "07", "09"], "back": ["01", "02"]},
        ]

        review = review_report.build_review("dlt", prediction_store=store, history=history)

        self.assertEqual(len(review["rows"]), 3)
        hot = next(row for row in review["rows"] if row["group"] == "hot")
        self.assertEqual(hot["hit_count"], 3)
        self.assertAlmostEqual(hot["expected"], 5 * 5 / 35)
        self.assertGreater(hot["delta"], 0)

        summary = review["summaries"][("前区", "recommendation")]
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["better"], 1)

        html = review_report.render_review_html(review)
        self.assertIn("大乐透 历史复盘", html)
        self.assertIn("随机基线", html)
        self.assertIn("长期统计", html)


if __name__ == "__main__":
    unittest.main()
