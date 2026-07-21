import os
import sys
import random
from collections import Counter

from crawler import output_file
from analyzer import (
    tune_weights, compute_cooccurrence,
    compute_all_dimensions, combine_dimensions,
    CONFIGS,
)
from utils import ensure_fresh, generate_filtered, get_latest_draw
from report import generate_combined_report
from expert import get_expert_picks


def _weight_variants(base_wt, delta=0.12):
    variants = [base_wt]
    for k in base_wt:
        v = dict(base_wt)
        v[k] = min(v[k] + delta, 0.35)
        others = [o for o in base_wt if o != k]
        if others:
            each = delta / len(others)
            for o in others:
                v[o] = max(v[o] - each, 0)
        variants.append(v)
    return variants


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
    print(f"\n已加载 {len(data)} 期历史数据")

    latest_entry, next_period = get_latest_draw(data, LOTID)
    latest_numbers = latest_entry["numbers"]
    next_seed = next_period

    print(f"最新: {latest_entry['period']}期 -> {latest_numbers}")
    print(f"预测: {next_period}期")

    best_avg, best_wt, best_win = tune_weights(data, tune_cfg)
    print(f"  回测调优: {best_avg:.2f}/期 (窗口{best_win})")

    cooccur = compute_cooccurrence(data, tune_cfg)
    dims = compute_all_dimensions(data, tune_cfg)

    all_numbers = []
    for vi, wt in enumerate(_weight_variants(best_wt)[:5]):
        w = combine_dimensions(dims, wt, tune_cfg["total"])
        for i in range(30):
            s = next_seed * 100000 + vi * 10000 + i
            r = generate_filtered(w, pick_count, s, tune_cfg, cooccur, max_attempts=30)
            if r:
                all_numbers.extend(int(n) for n in r)

    counter = Counter(all_numbers)

    top = sorted(n for n, _ in counter.most_common(pick_count))
    hot = [str(n).zfill(2) for n in top]

    bottom_all = [n for n, _ in counter.most_common() if counter[n] > 0]
    bottom = sorted(bottom_all[-pick_count:])
    cold = [str(n).zfill(2) for n in bottom]

    kill_set = set(top) | set(bottom)
    middle_freq = [n for n, _ in counter.most_common() if n not in kill_set]
    middle_b = sorted(middle_freq[:pick_count])
    kill_b = [str(n).zfill(2) for n in middle_b]

    middle_sorted = sorted(n for n in range(1, 81) if n not in kill_set)
    step = len(middle_sorted) / pick_count
    kill_c = [str(n).zfill(2) for n in (middle_sorted[int(i * step)] for i in range(pick_count))]

    rng = random.Random(next_seed)
    kill_a = [str(n).zfill(2) for n in sorted(rng.sample(middle_sorted, pick_count))]

    predictions = {"hot": hot, "cold": cold, "kill_a": kill_a, "kill_b": kill_b, "kill_c": kill_c}

    areas = [("号码", "numbers", predictions, counter, {**cfg, "pick": pick_count, "field": "numbers"})]
    expert_data = []
    experts, all_picks = get_expert_picks(LOTID, next_period, max_articles=12)
    if experts:
        expert_data.append(("号码", experts, all_picks))

    fpath = generate_combined_report(data, latest_entry, areas, LOTID, next_period, next_seed, expert_data=expert_data or None)
    print(f"  总采样: {len(all_numbers)} 次")
