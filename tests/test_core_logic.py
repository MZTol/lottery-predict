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
import data_quality
import main
import model_registry
import prediction_store
import report
import review_report
import site_index
import utils
import strategy


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

    def test_backtest_evaluation_uses_filtered_production_generator(self):
        cfg = {"total": 3, "pick": 1, "field": "numbers", "zones": 1}
        dims = {name: [1.0, 0.0, 0.0] for name in analyzer.DEFAULT_WEIGHTS}
        entries = [({1}, dims, [[0.0] * 3 for _ in range(3)], 120, 1.0)]

        with patch("utils.generate_filtered", return_value=["01"]) as mocked:
            score = analyzer._eval_weights(entries, cfg, analyzer.DEFAULT_WEIGHTS, seed_trials=2)

        self.assertEqual(score, 1.0)
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(mocked.call_args.kwargs["max_attempts"], analyzer.BACKTEST_FILTER_ATTEMPTS)

    def test_prediction_generation_uses_best_window_and_all_weight_variants(self):
        data = [
            {"period": str(period), "numbers": ["01", "02", "03"]}
            for period in range(10, 4, -1)
        ]
        cfg = {"total": 12, "pick": 3, "field": "numbers", "zones": 3}
        dim_windows = []
        co_windows = []
        calls = []

        def fake_dimensions(train, _cfg):
            dim_windows.append(len(train))
            return {name: [1.0] * _cfg["total"] for name in analyzer.DEFAULT_WEIGHTS}

        def fake_cooccurrence(train, _cfg):
            co_windows.append(len(train))
            return [[0.0] * _cfg["total"] for _ in range(_cfg["total"])]

        def fake_generate(_weights, k, _seed, _cfg, _cooccur, max_attempts=30):
            calls.append(_seed)
            start = ((len(calls) - 1) % _cfg["total"]) + 1
            nums = [((start + offset - 1) % _cfg["total"]) + 1 for offset in range(k)]
            return [str(n).zfill(2) for n in nums]

        with patch("analyzer.tune_weights", return_value=(2.0, analyzer.DEFAULT_WEIGHTS, 3)):
            with patch("analyzer.compute_all_dimensions", side_effect=fake_dimensions):
                with patch("analyzer.compute_cooccurrence", side_effect=fake_cooccurrence):
                    with patch("utils.generate_filtered", side_effect=fake_generate):
                        predictions, counter, meta = analyzer.generate_prediction_groups(
                            data, cfg, seed=999, sample_target=20
                        )

        self.assertEqual(dim_windows, [3])
        self.assertEqual(co_windows, [3])
        self.assertEqual(meta["model_window"], 3)
        self.assertEqual(meta["variant_count"], len(analyzer.DEFAULT_WEIGHTS) + 1)
        self.assertEqual(len(calls), 20)
        self.assertEqual(sum(counter.values()), 60)
        self.assertEqual(len(predictions["hot"]), 3)

    def test_small_pick_generation_skips_large_combo_filters(self):
        cfg = {"total": 16, "pick": 1, "field": "back", "zones": 4}

        with patch("utils.weighted_sample", return_value=["16"]) as mocked:
            result = utils.generate_filtered([0.0] * 15 + [1.0], 1, 7, cfg, max_attempts=3)

        self.assertEqual(result, ["16"])
        self.assertEqual(mocked.call_count, 1)

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

    def test_expert_consensus_is_saved_and_evaluated_separately(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            areas = [(
                "前区",
                "front",
                {
                    "hot": ["01", "02", "03", "04", "05"],
                    "cold": ["06", "07", "08", "09", "10"],
                    "kill_a": ["11", "12", "13", "14", "15"],
                },
                Counter({1: 5, 2: 4, 3: 3, 4: 2, 5: 1}),
                {"total": 35, "pick": 5},
            )]
            expert_data = [("前区", [], {"front": [7, 7, 8, 8, 9, 10], "back": []})]

            saved = prediction_store.save_prediction(
                "dlt", 124, 124, areas, filename=filename, expert_data=expert_data
            )
            evaluation = prediction_store.evaluate_prediction(
                "dlt",
                {"period": "124", "front": ["07", "08", "09", "11", "12"]},
                filename=filename,
            )

        self.assertEqual(saved["areas"]["front"]["expert_consensus"], ["07", "08", "09", "10"])
        expert = next(c for c in evaluation["areas"][0]["comparisons"] if c["name"] == "expert_consensus")
        self.assertEqual(expert["hits"], [7, 8, 9])

    def test_expert_avoid_and_contrarian_groups_are_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            areas = [("号码", "numbers", {"hot": ["01", "02", "03"]}, Counter({1: 5, 2: 4, 3: 3}), {"total": 12, "pick": 3})]
            expert_data = [("号码", [
                {"name": "甲", "picks": {"3+0": {"front": [1, 2, 3], "back": []}}, "avoid": [9, 10], "url": ""},
                {"name": "乙", "picks": {"3+0": {"front": [1, 4, 5], "back": []}}, "avoid": [9, 11], "url": ""},
            ], {"front": [1, 2, 3, 1, 4, 5], "back": [], "avoid_front": [9, 10, 9, 11]})]
            saved = prediction_store.save_prediction("kl8", 1, 1, areas, filename=filename, expert_data=expert_data)

        self.assertEqual(saved["areas"]["numbers"]["expert_consensus"], ["01", "02", "03"])
        self.assertEqual(saved["areas"]["numbers"]["expert_avoid"], ["09", "10", "11"])
        self.assertEqual(len(saved["areas"]["numbers"]["expert_contrarian"]), 3)

    def test_unproven_saved_strategy_falls_back_to_model(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            selection_file = os.path.join(tmpdir, "strategy_selection.json")
            with open(selection_file, "w") as f:
                import json
                json.dump({"kl8": {"numbers": {"selected_strategy": "interval", "confidence": "未证实", "selected_stats": {"sample_count": 100}}}}, f)
            with patch("strategy.SELECTION_FILE", selection_file):
                self.assertEqual(strategy.strategy_for("kl8", "numbers"), "model")

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
        self.assertIn("本期综合模型", html)
        self.assertIn("综合模型", html)
        self.assertIn("手动选择", html)
        self.assertIn("自选号码", html)
        self.assertIn('data-manual-key="numbers-9"', html)
        self.assertIn('data-manual-cell data-number="04"', html)
        self.assertIn('role="button"', html)
        self.assertNotIn("本期最终分层", html)
        self.assertIn("当前主推回看", html)
        self.assertIn("trend-draw", html)
        self.assertIn("trend-rec", html)
        self.assertIn("01", html)
        self.assertIn("09", html)
        self.assertIn('<td class="trend-cell trend-empty"><span>04</span></td>', html)

    def test_prediction_history_comparison_uses_saved_prediction_when_available(self):
        data = [
            {"period": "004", "numbers": ["01", "03", "05"]},
            {"period": "003", "numbers": ["02", "04", "06"]},
        ]
        predictions = {"hot": ["01", "02", "03"], "cold": ["04", "05", "06"]}
        counter = Counter({1: 5, 2: 4, 3: 3})
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, "predictions_history.json")
            with open(filename, "w") as f:
                import json
                json.dump({"kl8": {"004": {"areas": {"numbers": {
                    "field": "numbers", "recommendation": ["01", "02", "04"]
                }}}}}, f)
            with patch("report.PREDICTIONS_FILE", filename):
                html = report._prediction_history_comparison(
                    data, "numbers", predictions, counter, pick=3,
                    periods=2, total_n=9, lotid="kl8",
                    cfg={"field": "numbers", "total": 9, "pick": 3, "zones": 2},
                )

        self.assertIn("上期预测中1", html)
        self.assertIn("当前主推回看", html)

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

    def test_expert_section_is_folded_external_reference(self):
        html = report._expert_section_html(
            [{"name": "专家A", "picks": {"5+2": {"front": [1, 2, 3, 4, 5], "back": [1, 2]}}}],
            {"front": [1, 1, 2, 3, 8], "back": [1, 2]},
            ("前区", "后区"),
            {"front": [1, 4, 8], "back": [2]},
        )

        self.assertIn("<details", html)
        self.assertIn("专家明细", html)
        self.assertIn("只占低权重", html)
        self.assertIn("重合 2 个", html)

    def test_saved_recommendation_uses_area_strategy(self):
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
            history = [
                {"period": "003", "numbers": ["04", "05", "06"]},
                {"period": "002", "numbers": ["04", "05", "06"]},
                {"period": "001", "numbers": ["01", "02", "03"]},
            ]

            selection_file = os.path.join(tmpdir, "strategy_selection.json")
            with patch("strategy.SELECTION_FILE", selection_file):
                saved = prediction_store.save_prediction("kl8", 456, 456, areas, filename=filename, history=history)

        self.assertEqual(saved["areas"]["numbers"]["strategy"], "omission")
        self.assertEqual(saved["areas"]["numbers"]["recommendation"], ["07", "08", "09"])

    def test_strategy_selects_frequency_for_ssq_front(self):
        predictions = {"hot": ["01", "02", "03", "04", "05", "06"]}
        counter = Counter({1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5})
        cfg = {"total": 33, "pick": 6}
        history = [
            {"front": ["10", "11", "12", "13", "14", "15"]},
            {"front": ["10", "11", "12", "13", "14", "16"]},
        ]

        nums, selected = strategy.choose_recommendation("ssq", "front", predictions, counter, cfg, history)

        self.assertEqual(selected, "frequency")
        self.assertEqual(nums, [10, 11, 12, 13, 14, 15])

    def test_model_strategy_never_exceeds_pick_count(self):
        predictions = {
            "hot": ["01", "02", "03", "04", "05"],
            "cold": ["06", "07", "08", "09", "10"],
        }
        counter = Counter({1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5})
        cfg = {"total": 35, "pick": 5}

        nums, selected = strategy.choose_recommendation("dlt", "front", predictions, counter, cfg, history=[])

        self.assertEqual(selected, "model")
        self.assertEqual(len(nums), 5)
        self.assertEqual(nums, [1, 2, 3, 4, 5])

    def test_candidate_models_return_same_pick_count(self):
        history = [
            {"period": "003", "numbers": ["01", "04", "07"]},
            {"period": "002", "numbers": ["02", "05", "08"]},
            {"period": "001", "numbers": ["03", "06", "09"]},
        ]
        cfg = {"field": "numbers", "total": 12, "pick": 3, "zones": 3}
        candidates = strategy.candidate_recommendations(
            {"hot": ["01", "02", "03"]},
            Counter({1: 5, 2: 4, 3: 3}),
            cfg,
            history=history,
        )

        self.assertEqual(
            set(candidates),
            {"model", "frequency", "omission", "interval", "linear_score", "nearest_draw"},
        )
        self.assertTrue(all(len(nums) == 3 for nums in candidates.values()))

    def test_nearest_draw_model_votes_from_the_following_known_draw(self):
        history = [
            {"period": "004", "numbers": ["01", "02"]},
            {"period": "003", "numbers": ["08", "09"]},
            {"period": "002", "numbers": ["01", "02"]},
            {"period": "001", "numbers": ["10", "11"]},
        ]
        cfg = {"field": "numbers", "total": 12, "pick": 2, "zones": 3}

        predicted = model_registry.nearest_draw_predict(history, cfg)

        self.assertEqual(predicted, [8, 9])

    def test_prediction_output_validation_rejects_wrong_count_and_range(self):
        cfg = {"field": "numbers", "total": 10, "pick": 3}

        self.assertEqual(
            model_registry.validate_prediction_output(["03", "01", "02"], cfg, "test"),
            [1, 2, 3],
        )
        with self.assertRaises(ValueError):
            model_registry.validate_prediction_output(["01", "02"], cfg, "test")
        with self.assertRaises(ValueError):
            model_registry.validate_prediction_output(["01", "02", "11"], cfg, "test")

    def test_main_predict_uses_legacy_scripts_in_lottery_order(self):
        calls = []

        def fake_run_path(path, run_name):
            calls.append((os.path.basename(path), list(sys.argv[1:]), run_name))

        with patch("runpy.run_path", side_effect=fake_run_path):
            main.predict("all")

        self.assertEqual(
            calls,
            [
                ("1.py", ["10"], "__main__"),
                ("2.py", [], "__main__"),
                ("3.py", [], "__main__"),
            ],
        )

    def test_history_quality_rejects_invalid_shape_and_accepts_valid_shape(self):
        valid = [
            {"period": "003", "numbers": [f"{n:02d}" for n in range(1, 21)]},
            {"period": "002", "numbers": [f"{n:02d}" for n in range(21, 41)]},
        ]
        invalid = [
            {"period": "003", "numbers": [f"{n:02d}" for n in range(1, 20)] + ["99"]},
            {"period": "003", "numbers": [f"{n:02d}" for n in range(1, 20)]},
        ]

        self.assertTrue(data_quality.validate_history(valid, "kl8")["ok"])
        result = data_quality.validate_history(invalid, "kl8")
        self.assertFalse(result["ok"])
        self.assertTrue(any("越界" in message for message in result["errors"]))
        self.assertTrue(any("重复" in message for message in result["errors"]))

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

        self.assertIn("本期号码", html)
        self.assertIn("本期主推", html)
        self.assertIn("综合模型", html)
        self.assertNotIn("分层", html)
        self.assertNotIn("核心", html)
        self.assertNotIn("备选", html)
        self.assertIn("状态", html)
        self.assertIn("结构", html)
        self.assertIn("上期", html)
        self.assertIn("中 2/3", html)

    def test_evaluation_section_prioritizes_plain_recommendation_result(self):
        evaluation = {
            "period": "123",
            "generated_at": "2026-01-01 18:00:00",
            "seed": 123,
            "areas": [{
                "label": "号码",
                "actual": [1, 3, 5],
                "comparisons": [{
                    "name": "recommendation",
                    "predicted": [1, 2, 3],
                    "hits": [1, 3],
                    "misses": [2],
                    "uncovered": [5],
                }],
            }],
        }

        html = report._evaluation_section_html(evaluation)

        self.assertIn("号码购买结果复盘", html)
        self.assertIn("中 2/3", html)
        self.assertIn("上期预测", html)
        self.assertIn("漏掉", html)
        self.assertIn("来源组明细", html)

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
                            "expert_consensus": ["01", "07", "08", "09", "10"],
                        }
                    },
                }
            }
        }
        history = [
            {"period": "123", "front": ["01", "03", "05", "07", "09"], "back": ["01", "02"]},
        ]

        review = review_report.build_review("dlt", prediction_store=store, history=history)

        self.assertEqual(len(review["rows"]), 4)
        hot = next(row for row in review["rows"] if row["group"] == "hot")
        self.assertEqual(hot["hit_count"], 3)
        self.assertAlmostEqual(hot["expected"], 5 * 5 / 35)
        self.assertGreater(hot["delta"], 0)
        expert = next(row for row in review["rows"] if row["group"] == "expert_consensus")
        self.assertEqual(expert["hit_count"], 3)

        summary = review["summaries"][("前区", "recommendation")]
        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["better"], 1)

        html = review_report.render_review_html(review)
        self.assertIn("大乐透 历史复盘", html)
        self.assertIn("先看结论", html)
        self.assertIn("前区最近一期", html)
        self.assertIn("中 3/5", html)
        self.assertIn("长期", html)
        self.assertIn("专家共识", html)
        self.assertIn("随机基线", html)
        self.assertIn("模型排行榜", html)
        self.assertIn("前区模型排行榜", html)
        self.assertIn("长期统计", html)

    def test_review_report_adds_frequency_and_omission_baselines_from_older_draws(self):
        store = {
            "kl8": {
                "003": {
                    "period": "003",
                    "areas": {
                        "numbers": {
                            "label": "号码",
                            "field": "numbers",
                            "total": 5,
                            "pick": 2,
                            "predictions": {"hot": ["01", "02"]},
                            "recommendation": ["01", "02"],
                        }
                    },
                }
            }
        }
        history = [
            {"period": "003", "numbers": ["01", "02"]},
            {"period": "002", "numbers": ["01", "03"]},
            {"period": "001", "numbers": ["01", "04"]},
        ]

        review = review_report.build_review("kl8", prediction_store=store, history=history)

        freq = next(row for row in review["rows"] if row["group"] == "baseline_frequency")
        omission = next(row for row in review["rows"] if row["group"] == "baseline_omission")
        self.assertEqual(freq["predicted"], [1, 3])
        self.assertEqual(omission["predicted"], [2, 5])
        self.assertEqual(review["summaries"][("号码", "baseline_frequency")]["count"], 1)

        html = review_report.render_review_html(review)
        self.assertIn("模型对比", html)
        self.assertIn("模型是否有效", html)
        self.assertIn("近期高频", html)
        self.assertIn("当前遗漏", html)

    def test_review_report_auto_replays_history_when_saved_samples_are_insufficient(self):
        history = [
            {"period": "005", "numbers": ["01", "02"]},
            {"period": "004", "numbers": ["02", "03"]},
            {"period": "003", "numbers": ["03", "04"]},
            {"period": "002", "numbers": ["04", "05"]},
            {"period": "001", "numbers": ["05", "06"]},
        ]

        def fake_generate(train, cfg, seed):
            pick = int(cfg["pick"])
            nums = [str(n).zfill(2) for n in range(1, pick + 1)]
            return {"hot": nums, "cold": nums, "kill_a": nums, "kill_b": nums, "kill_c": nums}, Counter({1: 3, 2: 2}), {"best_window": len(train)}

        with patch("review_report.REPLAY_TARGET_PERIODS", 3):
            with patch("review_report.REPLAY_MIN_TRAIN", 2):
                with patch("review_report.generate_prediction_groups", side_effect=fake_generate):
                    review = review_report.build_review("kl8", prediction_store={"kl8": {}}, history=history)

        self.assertEqual(review["saved_periods"], 0)
        self.assertEqual(review["replay_periods"], 3)
        rec_rows = [row for row in review["rows"] if row["group"] == "recommendation"]
        self.assertEqual(len(rec_rows), 3)
        self.assertTrue(all(row["source"] == "replay" for row in rec_rows))
        self.assertEqual(
            len([row for row in review["rows"] if row["group"] == "model"]),
            3,
        )
        self.assertEqual(
            len([row for row in review["rows"] if row["group"] == "interval"]),
            3,
        )

        html = review_report.render_review_html(review)
        self.assertIn("历史回放期数", html)
        self.assertIn("历史回放", html)

    def test_report_header_shows_data_cache_status(self):
        html = report._data_status_section({
            "state": "使用缓存",
            "fresh": False,
            "latest_period": "2026001",
            "cache_time": "2026-08-03 01:05",
            "age_hours": 12.25,
            "last_draw_time": "2026-08-03 21:30",
        })

        self.assertIn("数据：", html)
        self.assertIn("使用缓存", html)
        self.assertIn("2026001期", html)
        self.assertIn("12.2小时前", html)

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
