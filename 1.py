import os
import sys

from crawler import output_file
from analyzer import CONFIGS, generate_prediction_groups
from utils import data_status, ensure_fresh, get_latest_draw
from report import generate_combined_report
from expert import get_expert_picks
from prediction_store import evaluate_prediction, save_prediction


if __name__ == "__main__":
    print("=" * 60)
    print("快乐8 数据分析预测工具")
    print("=" * 60)

    LOTID = "kl8"
    cfg = CONFIGS[LOTID]
    fpath = output_file(LOTID)

    pick_count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    tune_cfg = {**cfg, "pick": pick_count}

    try:
        data = ensure_fresh(fpath, LOTID, max_age_hours=1)
    except Exception as e:
        print(f"\n错误: {e}")
        exit(1)
    status = data_status(fpath, LOTID, data, max_age_hours=1)
    print(f"\n已加载 {len(data)} 期历史数据")

    latest_entry, next_period = get_latest_draw(data, LOTID)
    latest_numbers = latest_entry["numbers"]
    next_seed = next_period

    print(f"最新: {latest_entry['period']}期 -> {latest_numbers}")
    print(f"预测: {next_period}期")

    evaluation = evaluate_prediction(LOTID, latest_entry)
    if evaluation:
        for area in evaluation["areas"]:
            for comp in area["comparisons"]:
                if comp["name"] == "recommendation":
                    print(f"  复盘 {area['label']} 综合推荐: 中 {len(comp['hits'])} 个")
    else:
        print("  复盘: 未找到本期历史预测记录")

    predictions, counter, model_meta = generate_prediction_groups(data, tune_cfg, next_seed)
    print(
        f"  回测调优: {model_meta['best_avg']:.2f}/期 "
        f"(窗口{model_meta['best_window']}, 生成{model_meta['model_window']}期, "
        f"{model_meta['variant_count']}组变体)"
    )

    areas = [("号码", "numbers", predictions, counter, {**cfg, "pick": pick_count, "field": "numbers"})]
    expert_data = []
    experts, all_picks = get_expert_picks(LOTID, next_period, max_articles=12)
    if experts:
        expert_data.append(("号码", experts, all_picks))

    fpath = generate_combined_report(
        data, latest_entry, areas, LOTID, next_period, next_seed,
        expert_data=expert_data or None,
        evaluation=evaluation,
        data_status=status,
    )
    save_prediction(LOTID, next_period, next_seed, areas, expert_data=expert_data or None)
    print(f"  已保存 {next_period}期预测记录")
    print(f"  总采样: {model_meta['sample_count']} 次")
