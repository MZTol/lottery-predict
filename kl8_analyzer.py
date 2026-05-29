import json
import os
from collections import Counter

TOTAL_NUMS = 80
SAMPLE_SIZE = 20

W_FREQ = 0.30
W_OMISSION = 0.20
W_ZONE = 0.15
W_ODD_EVEN = 0.10
W_FOLLOW = 0.25

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "kl8_history.json")


def load_history(filename=HISTORY_FILE):
    with open(filename) as f:
        return json.load(f)


def compute_frequency(data):
    counter = Counter()
    for entry in data:
        for n in entry["numbers"]:
            counter[int(n)] += 1
    total = len(data)
    return [counter.get(i, 0) / total for i in range(1, TOTAL_NUMS + 1)]


def compute_omission(data):
    omission = [0] * TOTAL_NUMS
    for entry in data:
        nums = {int(n) for n in entry["numbers"]}
        for i in range(TOTAL_NUMS):
            if (i + 1) in nums:
                omission[i] = 0
            else:
                omission[i] += 1
    mx = max(omission) if max(omission) > 0 else 1
    return [o / mx for o in omission]


def compute_zone_scores(data):
    if not data:
        return [0.5] * TOTAL_NUMS
    zones = [0, 0, 0, 0]
    latest = data[0]["numbers"]
    for n in latest:
        zones[(int(n) - 1) // 20] += 1
    expected = SAMPLE_SIZE / 4
    scores = []
    for i in range(TOTAL_NUMS):
        zone_idx = i // 20
        deficit = expected - zones[zone_idx]
        scores.append(max(0, deficit / expected))
    return scores


def compute_odd_even_scores(data):
    if not data:
        return [0.5] * TOTAL_NUMS
    latest = data[0]["numbers"]
    odd = sum(1 for n in latest if int(n) % 2 == 1)
    even = SAMPLE_SIZE - odd
    expected = SAMPLE_SIZE / 2
    odd_deficit = max(0, (expected - odd) / expected)
    even_deficit = max(0, (expected - even) / expected)
    scores = []
    for i in range(TOTAL_NUMS):
        scores.append(odd_deficit if (i + 1) % 2 == 1 else even_deficit)
    return scores


def compute_follow_scores(data):
    if len(data) < 2:
        return [0] * TOTAL_NUMS
    counter = Counter()
    for i in range(len(data) - 1):
        curr = {int(n) for n in data[i]["numbers"]}
        nxt = {int(n) for n in data[i + 1]["numbers"]}
        for c in curr:
            for n in nxt:
                counter[(c, n)] += 1
    latest = {int(n) for n in data[0]["numbers"]}
    scores = [0] * TOTAL_NUMS
    for n in range(1, TOTAL_NUMS + 1):
        total = sum(counter.get((c, n), 0) for c in latest)
        scores[n - 1] = total
    mx = max(scores) if max(scores) > 0 else 1
    return [s / mx for s in scores]


def generate_weights(data=None):
    if data is None:
        data = load_history()
    freq = compute_frequency(data)
    omission = compute_omission(data)
    zone = compute_zone_scores(data)
    oe = compute_odd_even_scores(data)
    follow = compute_follow_scores(data)
    weights = []
    for i in range(TOTAL_NUMS):
        w = (freq[i] * W_FREQ + omission[i] * W_OMISSION +
             zone[i] * W_ZONE + oe[i] * W_ODD_EVEN +
             follow[i] * W_FOLLOW)
        weights.append(w)
    return weights


def print_analysis(data=None):
    if data is None:
        data = load_history()
    weights = generate_weights(data)
    ranked = sorted(enumerate(weights, 1), key=lambda x: -x[1])
    print(f"数据分析 (基于最近{len(data)}期):")
    print(f"  频率权重: {W_FREQ}, 遗漏权重: {W_OMISSION}")
    print(f"  区间权重: {W_ZONE}, 奇偶权重: {W_ODD_EVEN}")
    print(f"  跟随权重: {W_FOLLOW}")
    print(f"\n综合权重 Top 20:")
    for num, w in ranked[:20]:
        bar = "█" * int(w * 50)
        print(f"  {num:02d}: {w:.4f} {bar}")
    print(f"\n综合权重 Bottom 10:")
    for num, w in ranked[-10:]:
        print(f"  {num:02d}: {w:.4f}")


if __name__ == "__main__":
    data = load_history()
    print_analysis(data)
