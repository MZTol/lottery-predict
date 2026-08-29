import json
import os
from collections import Counter

DIR = os.path.dirname(__file__)

CONFIGS = {
    "kl8": {
        "file": os.path.join(DIR, "kl8_history.json"),
        "total": 80, "pick": 20, "field": "numbers", "zones": 4,
    },
    "dlt_front": {
        "file": os.path.join(DIR, "dlt_history.json"),
        "total": 35, "pick": 5, "field": "front", "zones": 4,
    },
    "dlt_back": {
        "file": os.path.join(DIR, "dlt_history.json"),
        "total": 12, "pick": 2, "field": "back", "zones": 4,
    },
    "ssq_front": {
        "file": os.path.join(DIR, "ssq_history.json"),
        "total": 33, "pick": 6, "field": "front", "zones": 4,
    },
    "ssq_back": {
        "file": os.path.join(DIR, "ssq_history.json"),
        "total": 16, "pick": 1, "field": "back", "zones": 4,
    },
}

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79}


def load_history(cfg):
    with open(cfg["file"]) as f:
        return json.load(f)


def _nums(entry, cfg):
    return [int(n) for n in entry[cfg["field"]]]


# ─── 原有5维度 ───

def compute_frequency_weighted(data, cfg):
    total_n, field = cfg["total"], cfg["field"]
    n = len(data)
    scores = [0.0] * total_n
    total_w = 0.0
    for i, entry in enumerate(data):
        w = 1.0 + (n - i) / n * 3
        total_w += w
        for ns in entry[field]:
            scores[int(ns) - 1] += w
    return [s / total_w for s in scores]


def compute_omission_exponential(data, cfg):
    total_n, field = cfg["total"], cfg["field"]
    omission = [len(data)] * total_n
    for idx, entry in enumerate(data):
        nums = {int(n) for n in entry[field]}
        for n in nums:
            if 1 <= n <= total_n and omission[n - 1] == len(data):
                omission[n - 1] = idx
    scores = [(1.15 ** o) - 1 for o in omission]
    mx = max(scores) or 1
    return [s / mx for s in scores]


def compute_zone_scores(data, cfg):
    total_n, pick, field, zc = cfg["total"], cfg["pick"], cfg["field"], cfg["zones"]
    if not data or pick <= 1:
        return [0.5] * total_n
    zones = [0] * zc
    for n in _nums(data[0], cfg):
        zones[min((n - 1) * zc // total_n, zc - 1)] += 1
    expected = pick / zc
    return [max(0, (expected - zones[min(i * zc // total_n, zc - 1)]) / expected) for i in range(total_n)]


def compute_odd_even_scores(data, cfg):
    total_n, pick, field = cfg["total"], cfg["pick"], cfg["field"]
    if not data or pick <= 1:
        return [0.5] * total_n
    latest = _nums(data[0], cfg)
    odd = sum(1 for n in latest if n % 2 == 1)
    odd_d = max(0, ((pick / 2) - odd) / (pick / 2))
    even_d = max(0, ((pick / 2) - (pick - odd)) / (pick / 2))
    return [odd_d if (i + 1) % 2 == 1 else even_d for i in range(total_n)]


def compute_follow_scores(data, cfg):
    total_n, field = cfg["total"], cfg["field"]
    if len(data) < 2:
        return [0] * total_n
    pair_cnt = Counter()
    for i in range(len(data) - 1):
        newer = {int(n) for n in data[i][field]}
        older = {int(n) for n in data[i + 1][field]}
        for old_n in older:
            for new_n in newer:
                pair_cnt[(old_n, new_n)] += 1
    latest = {int(n) for n in data[0][field]}
    scores = [sum(pair_cnt.get((c, n), 0) for c in latest) for n in range(1, total_n + 1)]
    mx = max(scores) or 1
    return [s / mx for s in scores]


# ─── 新增4维度 ───

def compute_sum_scores(data, cfg):
    """和值维度：靠近历史平均和值的数得分高"""
    total_n, pick, field = cfg["total"], cfg["pick"], cfg["field"]
    historical_sums = [sum(_nums(e, cfg)) for e in data]
    mean_sum = sum(historical_sums) / len(historical_sums)
    ideal_avg = mean_sum / pick
    scores = [(1 - abs((i + 1) - ideal_avg) / total_n) for i in range(total_n)]
    mn, mx = min(scores), max(scores)
    if mx <= mn:
        return [0.5] * total_n
    return [(s - mn) / (mx - mn) for s in scores]


def compute_tail_scores(data, cfg):
    """尾数维度：近期冷尾加分"""
    total_n, pick, field = cfg["total"], cfg["pick"], cfg["field"]
    tail_cnt = Counter()
    for e in data[:30]:
        for n in _nums(e, cfg):
            tail_cnt[n % 10] += 1
    total_tail = sum(tail_cnt.values()) or 1
    tail_prob = {t: tail_cnt[t] / total_tail for t in range(10)}
    latest_tail = Counter(n % 10 for n in _nums(data[0], cfg))
    scores = []
    for i in range(total_n):
        t = (i + 1) % 10
        deficit = max(0, (tail_prob[t] - latest_tail.get(t, 0) / max(pick, 1)) / max(tail_prob[t], 0.01))
        scores.append(min(deficit, 1.0))
    return scores


def compute_neighbor_scores(data, cfg):
    """邻号维度：上期号码 ±1 加权"""
    total_n, field = cfg["total"], cfg["field"]
    latest = {int(n) for n in data[0][field]}
    scores = [0.0] * total_n
    for n in latest:
        for offset in [-2, -1, 1, 2]:
            nb = n + offset
            if 1 <= nb <= total_n:
                scores[nb - 1] += 1.0 / abs(offset)
    mx = max(scores) or 1
    return [s / mx for s in scores]


def compute_prime_scores(data, cfg):
    """质数维度：平衡质数数量"""
    total_n, pick, field = cfg["total"], cfg["pick"], cfg["field"]
    primes_in_range = [i + 1 for i in range(total_n) if (i + 1) in PRIMES]
    hist_prime_cnt = [sum(1 for n in _nums(e, cfg) if n in PRIMES) for e in data]
    avg_primes = sum(hist_prime_cnt) / len(hist_prime_cnt)
    latest_prime = sum(1 for n in _nums(data[0], cfg) if n in PRIMES)
    deficit = max(0, (avg_primes - latest_prime) / max(avg_primes, 1))
    return [deficit if (i + 1) in PRIMES else 0.0 for i in range(total_n)]


# ─── 共现分析 ───

def compute_cooccurrence(data, cfg):
    """构建共现矩阵: matrix[a][b] = a出现后b也出现的比例(归一化)"""
    total_n = cfg["total"]
    field = cfg["field"]
    matrix = [[0] * total_n for _ in range(total_n)]
    for entry in data:
        nums = [int(n) for n in entry[field]]
        for i in range(len(nums)):
            ai = nums[i] - 1
            for j in range(i + 1, len(nums)):
                bj = nums[j] - 1
                matrix[ai][bj] += 1
                matrix[bj][ai] += 1
    for i in range(total_n):
        mx = max(matrix[i]) or 1
        for j in range(total_n):
            matrix[i][j] = matrix[i][j] / mx
    return matrix


# ─── 权重配置 ───

DEFAULT_WEIGHTS = {
    "freq": 0.18,
    "omission": 0.14,
    "zone": 0.09,
    "odd_even": 0.05,
    "follow": 0.14,
    "sum_score": 0.10,
    "tail": 0.10,
    "neighbor": 0.12,
    "prime": 0.08,
}

MODEL_SAMPLE_TARGET = 150


def generate_weights(data, cfg, weights_override=None):
    wt = weights_override or DEFAULT_WEIGHTS
    return combine_dimensions(compute_all_dimensions(data, cfg), wt, cfg["total"])


def compute_all_dimensions(data, cfg):
    """预计算所有9个维度，返回 {name → scores_list}"""
    return {
        "freq": compute_frequency_weighted(data, cfg),
        "omission": compute_omission_exponential(data, cfg),
        "zone": compute_zone_scores(data, cfg),
        "odd_even": compute_odd_even_scores(data, cfg),
        "follow": compute_follow_scores(data, cfg),
        "sum_score": compute_sum_scores(data, cfg),
        "tail": compute_tail_scores(data, cfg),
        "neighbor": compute_neighbor_scores(data, cfg),
        "prime": compute_prime_scores(data, cfg),
    }


def combine_dimensions(dims, wt, total_n):
    """给定预计算维度和权重组合，合成最终权重向量"""
    return [
        sum(dims[name][i] * wt.get(name, 0) for name in dims)
        for i in range(total_n)
    ]


def weight_variants(base_wt, delta=0.12):
    variants = [dict(base_wt)]
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


def _sample_plan(variant_count, total_samples=MODEL_SAMPLE_TARGET):
    if variant_count <= 0:
        return []
    base = total_samples // variant_count
    extra = total_samples % variant_count
    return [base + (1 if i < extra else 0) for i in range(variant_count)]


def _pad_unique(nums, candidates, pick):
    out = []
    for n in nums:
        if n not in out:
            out.append(n)
        if len(out) >= pick:
            return out
    for n in candidates:
        if n not in out:
            out.append(n)
        if len(out) >= pick:
            return out
    return out


def _spread_pick(candidates, pick):
    if not candidates or pick <= 0:
        return []
    if len(candidates) <= pick:
        return list(candidates)
    step = len(candidates) / pick
    return [candidates[min(int(i * step), len(candidates) - 1)] for i in range(pick)]


def generate_prediction_groups(data, cfg, seed, sample_target=MODEL_SAMPLE_TARGET):
    """Generate report groups and the sampling counter with the tuned production model."""
    from utils import generate_filtered

    pick = int(cfg["pick"])
    total = int(cfg["total"])
    best_avg, best_wt, best_win = tune_weights(data, cfg)
    model_data = data[:best_win] if best_win and len(data) >= best_win else data

    cooccur = compute_cooccurrence(model_data, cfg)
    dims = compute_all_dimensions(model_data, cfg)
    variants = weight_variants(best_wt)
    plan = _sample_plan(len(variants), sample_target)

    all_numbers = []
    for vi, wt in enumerate(variants):
        w = combine_dimensions(dims, wt, total)
        for i in range(plan[vi]):
            s = seed * 100000 + vi * 10000 + i
            r = generate_filtered(w, pick, s, cfg, cooccur, max_attempts=30)
            if r:
                all_numbers.extend(int(n) for n in r)

    counter = Counter(all_numbers)
    ranked = [n for n, _ in counter.most_common()]
    all_candidates = list(range(1, total + 1))

    top = _pad_unique(ranked[:pick], all_candidates, pick)
    hot = [str(n).zfill(2) for n in sorted(top)]

    bottom = _pad_unique(list(reversed(ranked))[:pick], all_candidates, pick)
    cold = [str(n).zfill(2) for n in sorted(bottom)]

    edge_set = set(top) | set(bottom)
    middle_freq = [n for n in ranked if n not in edge_set]
    middle_b = _pad_unique(middle_freq[:pick], all_candidates, pick)
    kill_b = [str(n).zfill(2) for n in sorted(middle_b)]

    middle_sorted = [n for n in all_candidates if n not in edge_set]
    spread = _pad_unique(_spread_pick(middle_sorted, pick), all_candidates, pick)
    kill_c = [str(n).zfill(2) for n in sorted(spread)]

    import random
    rng = random.Random(seed)
    pool = middle_sorted if len(middle_sorted) >= pick else all_candidates
    kill_a_nums = rng.sample(pool, min(pick, len(pool)))
    kill_a = [str(n).zfill(2) for n in sorted(_pad_unique(kill_a_nums, all_candidates, pick))]

    predictions = {
        "hot": hot,
        "cold": cold,
        "kill_a": kill_a,
        "kill_b": kill_b,
        "kill_c": kill_c,
    }
    meta = {
        "best_avg": best_avg,
        "best_window": best_win,
        "model_window": len(model_data),
        "variant_count": len(variants),
        "sample_count": sum(counter.values()),
    }
    return predictions, counter, meta


# ─── 回测 ───

WINDOWS = [20, 30, 50]
BACKTEST_COUNT = 15
BACKTEST_SEED_TRIALS = 3
BACKTEST_FILTER_ATTEMPTS = 30


def _backtest_window_dims(data, cfg, window, test_count=BACKTEST_COUNT):
    """预计算每个回测期的训练集维度，供多次权重组合复用"""
    entries = []
    usable_count = min(test_count, max(0, len(data) - 10))
    for idx in range(usable_count):
        train = data[idx + 1: idx + 1 + window]
        if len(train) < 10:
            entries.append(None)
            continue
        actual = {int(n) for n in data[idx][cfg["field"]]}
        dims = compute_all_dimensions(train, cfg)
        cooccur = compute_cooccurrence(train, cfg)
        period_seed = int(data[idx]["period"])
        weight = 1.0 + (usable_count - idx) / usable_count
        entries.append((actual, dims, cooccur, period_seed, weight))
    return entries


def _eval_weights(entries, cfg, wt, seed_trials=BACKTEST_SEED_TRIALS):
    """对预计算的数据，用给定权重组合评估命中率"""
    from utils import generate_filtered
    total_hits, total_weight = 0.0, 0.0
    for entry in entries:
        if entry is None:
            continue
        actual, dims, cooccur, seed, weight = entry
        w = combine_dimensions(dims, wt, cfg["total"])
        hits = 0
        for si in range(seed_trials):
            pred = generate_filtered(
                w, cfg["pick"], seed * 1000 + si, cfg, cooccur,
                max_attempts=BACKTEST_FILTER_ATTEMPTS,
            )
            pred_set = {int(n) for n in pred}
            hits += len(pred_set & actual)
        avg_hits = hits / seed_trials
        total_hits += avg_hits * weight
        total_weight += weight
    return total_hits / total_weight if total_weight else 0


def backtest(data, cfg, weights_override=None, window=30, test_count=BACKTEST_COUNT):
    """测试最近test_count期，返回平均命中数"""
    entries = _backtest_window_dims(data, cfg, window, test_count)
    wt = weights_override or DEFAULT_WEIGHTS
    return _eval_weights(entries, cfg, wt)


def tune_weights_stepwise(data, cfg, window=30):
    """逐步调优：从默认权重开始，每轮微调每个维度，保留收益最大的变化"""
    entries = _backtest_window_dims(data, cfg, window)
    keys = list(DEFAULT_WEIGHTS.keys())
    best_wt = dict(DEFAULT_WEIGHTS)
    best_avg = _eval_weights(entries, cfg, best_wt)
    improved = True
    while improved:
        improved = False
        for k in keys:
            for delta in [0.03, -0.03]:
                test = dict(best_wt)
                test[k] += delta
                if test[k] < 0 or test[k] > 0.35:
                    continue
                avg = _eval_weights(entries, cfg, test)
                if avg > best_avg + 0.01:
                    best_avg = avg
                    best_wt = test
                    improved = True
                    break
            if improved:
                break
    return best_avg, best_wt


def tune_weights(data, cfg):
    """Tune on older draws and select the window on a newer holdout block."""
    holdout_count = BACKTEST_COUNT
    if len(data) < holdout_count + max(WINDOWS) + 10:
        # Small synthetic/test datasets cannot support a clean split.
        tuning_data = data
        holdout_entries_by_window = None
    else:
        tuning_data = data[holdout_count:]
        holdout_entries_by_window = {
            window: _backtest_window_dims(data, cfg, window, holdout_count)
            for window in WINDOWS
        }

    best_avg = 0
    best_wt = dict(DEFAULT_WEIGHTS)
    best_window = 30
    for w in WINDOWS:
        tuning_avg, tuned_wt = tune_weights_stepwise(tuning_data, cfg, w)
        if holdout_entries_by_window is None:
            score = tuning_avg
            candidate_wt = tuned_wt
        else:
            # Shrink toward the stable defaults before evaluating unseen
            # recent periods. This reduces short-window parameter chasing.
            candidate_wt = {
                name: DEFAULT_WEIGHTS[name] * 0.5 + tuned_wt[name] * 0.5
                for name in DEFAULT_WEIGHTS
            }
            score = _eval_weights(holdout_entries_by_window[w], cfg, candidate_wt)
        if score > best_avg:
            best_avg = score
            best_wt = candidate_wt
            best_window = w
    return best_avg, best_wt, best_window


# ─── 打印 ───

def print_top(data, cfg, label="", top_n=10):
    w = generate_weights(data, cfg)
    ranked = sorted(enumerate(w, 1), key=lambda x: -x[1])
    print(f"  {label} Top {top_n}:")
    for num, score in ranked[:top_n]:
        print(f"    {num:02d}: {score:.4f}")


if __name__ == "__main__":
    for key, cfg in CONFIGS.items():
        data = load_history(cfg)
        print(f"\n{key}:")
        print_top(data, cfg, top_n=10)
