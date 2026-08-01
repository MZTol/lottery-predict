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
import site_index


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

    def test_prediction_store_treats_empty_or_invalid_json_as_empty_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            with open(filename, "w") as f:
                f.write("")
            self.assertEqual(prediction_store._load_store(filename), {})

            with open(filename, "w") as f:
                f.write("not-json")
            self.assertEqual(prediction_store._load_store(filename), {})

            with open(filename, "w") as f:
                f.write("[]")
            self.assertEqual(prediction_store._load_store(filename), {})

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
            data, "numbers", predictions, counter, pick=3, periods=2, total_n=9
        )

        self.assertIn("trend-wrap", html)
        self.assertIn("trend-table", html)
        self.assertIn("期号/号码", html)
        self.assertIn("004", html)
        self.assertIn("003", html)
        self.assertLess(html.index("003"), html.index("004"))
        self.assertIn("本期综合推荐", html)
        self.assertIn("综合推荐", html)
        self.assertIn("手动选择", html)
        self.assertIn("自选号码", html)
        self.assertIn('data-manual-key="numbers-9"', html)
        self.assertIn('data-manual-cell data-number="04"', html)
        self.assertIn('role="button"', html)
        self.assertNotIn("本期最终分层", html)
        self.assertIn("综合中", html)
        self.assertIn("trend-draw", html)
        self.assertIn("trend-rec", html)
        self.assertIn("01", html)
        self.assertIn("09", html)
        self.assertIn('<td class="trend-cell trend-empty"><span>04</span></td>', html)

    def test_recommendation_uses_sampling_counter_not_group_vote(self):
        predictions = {
            "hot": ["01", "02", "03"],
            "cold": ["04", "05", "06"],
            "kill_a": ["07", "08", "09"],
            "kill_b": ["07", "08", "09"],
            "kill_c": ["07", "08", "09"],
        }
        counter = Counter({1: 50, 2: 40, 3: 30, 7: 1, 8: 1, 9: 1})

        self.assertEqual(report._recommendation(predictions, counter, 3), [1, 2, 3])

    def test_report_style_contains_manual_selection_script(self):
        html = report._style()

        self.assertIn("localStorage", html)
        self.assertIn("manual-on", html)
        self.assertIn("data-manual-cell", html)

    def test_saved_recommendation_uses_sampling_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            areas = [(
                "号码",
                "numbers",
                {
                    "hot": ["01", "02", "03"],
                    "cold": ["04", "05", "06"],
                    "kill_a": ["07", "08", "09"],
                    "kill_b": ["07", "08", "09"],
                    "kill_c": ["07", "08", "09"],
                },
                Counter({1: 50, 2: 40, 3: 30, 7: 1, 8: 1, 9: 1}),
                {"total": 9, "pick": 3},
            )]

            saved = prediction_store.save_prediction("kl8", 456, 456, areas, filename=filename)

        self.assertEqual(saved["areas"]["numbers"]["recommendation"], ["01", "02", "03"])

    def test_key_summary_section_shows_first_screen_decision_points(self):
        data = [
            {"period": "004", "numbers": ["01", "03", "05"]},
            {"period": "003", "numbers": ["02", "04", "06"]},
            {"period": "002", "numbers": ["01", "02", "06"]},
        ]
        predictions = {
            "hot": ["01", "02", "03"],
            "cold": ["04", "05", "06"],
            "kill_a": ["07", "08", "09"],
            "kill_b": ["01", "04", "07"],
            "kill_c": ["02", "05", "08"],
        }
        counter = Counter({1: 5, 2: 4, 3: 3})
        areas = [("号码", "numbers", predictions, counter, {"total": 9, "pick": 3})]
        evaluation = {
            "areas": [{
                "field": "numbers",
                "comparisons": [{
                    "name": "recommendation",
                    "hits": [1, 3],
                    "uncovered": [5],
                }],
            }]
        }

        html = report._key_summary_section(data, areas, evaluation)

        self.assertIn("关键结论", html)
        self.assertIn("号码最终主推", html)
        self.assertIn("核心号", html)
        self.assertIn("备选号", html)
        self.assertIn("观察号", html)
        self.assertIn("号码近10期最相似", html)
        self.assertIn("号码当前遗漏高位", html)
        self.assertIn("号码上期综合复盘", html)
        self.assertIn("中 2 个", html)

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

    def test_site_index_generates_grouped_mobile_home_and_latest_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "dlt_2026001.html": "old",
                "dlt_2026003.html": "new",
                "ssq_2026002.html": "ssq",
                "review_dlt.html": "review",
            }
            for name, content in files.items():
                with open(os.path.join(tmpdir, name), "w") as f:
                    f.write(content)

            index_path = site_index.generate_site(tmpdir, updated_at="2026-08-01 22:10")

            with open(index_path) as f:
                index_html = f.read()
            with open(os.path.join(tmpdir, "latest_dlt.html")) as f:
                latest_dlt = f.read()

        self.assertEqual(latest_dlt, "new")
        self.assertIn("最新预测报告", index_html)
        self.assertIn("历史复盘", index_html)
        self.assertIn("最近预测归档", index_html)
        self.assertIn("latest_dlt.html", index_html)
        self.assertIn("latest_ssq.html", index_html)
        self.assertIn("review_dlt.html", index_html)
        self.assertIn("2026-08-01 22:10", index_html)


if __name__ == "__main__":
    unittest.main()
