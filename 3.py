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


def _predict(data, cfg, seed):
    pick = cfg["pick"]
    tune_cfg = {**cfg, "pick": pick}
    total = tune_cfg["total"]

    best_avg, best_wt, best_win = tune_weights(data, tune_cfg)
    cooccur = compute_cooccurrence(data, tune_cfg)
    dims = compute_all_dimensions(data, tune_cfg)

    all_numbers = []
    for vi, wt in enumerate(_weight_variants(best_wt)[:5]):
        w = combine_dimensions(dims, wt, total)
        for i in range(30):
            s = seed * 100000 + vi * 10000 + i
            r = generate_filtered(w, pick, s, tune_cfg, cooccur, max_attempts=30)
            if r:
                all_numbers.extend(int(n) for n in r)

    counter = Counter(all_numbers)

    top = sorted(n for n, _ in counter.most_common(pick))
    hot = [str(n).zfill(2) for n in top]

    bottom_all = [n for n, _ in counter.most_common() if counter[n] > 0]
    bottom = sorted(bottom_all[-pick:])
    cold = [str(n).zfill(2) for n in bottom]

    kill_set = set(top) | set(bottom)
    middle_freq = [n for n, _ in counter.most_common() if n not in kill_set]
    middle_b = sorted(middle_freq[:pick])
    kill_b = [str(n).zfill(2) for n in middle_b]

    middle_sorted = sorted(n for n in range(1, total + 1) if n not in kill_set)
    step = len(middle_sorted) / max(pick, 1)
    kill_c = [str(n).zfill(2) for n in (middle_sorted[int(i * step)] for i in range(pick))]

    random.seed(seed)
    kill_a = [str(n).zfill(2) for n in sorted(random.sample(middle_sorted, pick))]

    return {"hot": hot, "cold": cold, "kill_a": kill_a, "kill_b": kill_b, "kill_c": kill_c}, counter


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
    print(f"\n已加载 {len(data)} 期历史数据")

    latest_entry, next_period = get_latest_draw(data, LOTID)
    next_seed = next_period

    print(f"最新: {latest_entry['period']}期")
    print(f"  红球: {latest_entry['front']}  蓝球: {latest_entry['back']}")
    print(f"预测: {next_period}期")

    areas = []
    for label, field, cfg_key in [("红球", "front", CONFIGS["ssq_front"]), ("蓝球", "back", CONFIGS["ssq_back"])]:
        preds, counter = _predict(data, cfg_key, next_seed)
        ov = set(int(n) for n in latest_entry[field])
        hits = sum(1 for name in preds for n in preds[name] if int(n) in ov)
        areas.append((label, field, preds, counter, {**cfg_key, "field": field}))
        print(f"  {label}: 命中 {hits}/{cfg_key['pick']}")

    expert_data = []
    experts, all_picks = get_expert_picks(LOTID, next_period, max_articles=15)
    if experts:
        expert_data.append(("红球", experts, all_picks))
        print(f"  专家: {len(experts)} 位")

    generate_combined_report(data, latest_entry, areas, LOTID, next_period, next_seed, expert_data=expert_data or None)
