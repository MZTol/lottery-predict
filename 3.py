import os
import sys

from crawler import output_file
from analyzer import CONFIGS, generate_prediction_groups
from utils import data_status, ensure_fresh, get_latest_draw
from report import generate_combined_report
from expert import get_expert_picks
from prediction_store import evaluate_prediction, save_prediction


def _predict(data, cfg, seed):
    return generate_prediction_groups(data, cfg, seed)


if __name__ == "__main__":
    print("=" * 60)
    print("双色球 数据分析预测工具")
    print("=" * 60)

    LOTID = "ssq"
    fpath = output_file(LOTID)

    try:
        data = ensure_fresh(fpath, LOTID, max_age_hours=1)
    except Exception as e:
        print(f"\n错误: {e}")
        exit(1)
    status = data_status(fpath, LOTID, data, max_age_hours=1)
    print(f"\n已加载 {len(data)} 期历史数据")

    latest_entry, next_period = get_latest_draw(data, LOTID)
    next_seed = next_period

    print(f"最新: {latest_entry['period']}期")
    print(f"  红球: {latest_entry['front']}  蓝球: {latest_entry['back']}")
    print(f"预测: {next_period}期")

    evaluation = evaluate_prediction(LOTID, latest_entry)
    if evaluation:
        for area in evaluation["areas"]:
            for comp in area["comparisons"]:
                if comp["name"] == "recommendation":
                    print(f"  复盘 {area['label']} 综合推荐: 中 {len(comp['hits'])} 个")
    else:
        print("  复盘: 未找到本期历史预测记录")

    areas = []
    for label, field, cfg_key in [("红球", "front", CONFIGS["ssq_front"]), ("蓝球", "back", CONFIGS["ssq_back"])]:
        preds, counter, model_meta = _predict(data, cfg_key, next_seed)
        ov = set(int(n) for n in latest_entry[field])
        hits = len({int(n) for n in preds["hot"]} & ov)
        areas.append((label, field, preds, counter, {**cfg_key, "field": field}))
        print(
            f"  {label}: 与上期重号 {hits}/{cfg_key['pick']} "
            f"(窗口{model_meta['best_window']}, 生成{model_meta['model_window']}期)"
        )

    expert_data = []
    experts, all_picks = get_expert_picks(LOTID, next_period, max_articles=15)
    if experts:
        expert_data.append(("红球", experts, all_picks))
        print(f"  专家: {len(experts)} 位")

    generate_combined_report(
        data, latest_entry, areas, LOTID, next_period, next_seed,
        expert_data=expert_data or None,
        evaluation=evaluation,
        data_status=status,
    )
    save_prediction(LOTID, next_period, next_seed, areas, expert_data=expert_data or None)
    print(f"  已保存 {next_period}期预测记录")
