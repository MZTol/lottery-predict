import json
import os
from collections import Counter

TOTAL_FRONT = 33
PICK_FRONT = 6
TOTAL_BACK = 16
PICK_BACK = 1

W_FREQ = 0.30
W_OMISSION = 0.20
W_ZONE = 0.15
W_ODD_EVEN = 0.10
W_FOLLOW = 0.25

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "ssq_history.json")


def load_history(filename=HISTORY_FILE):
    with open(filename) as f:
        return json.load(f)


def _compute_frequency(data, field, total):
    counter = Counter()
    for entry in data:
        for n in entry[field]:
            counter[int(n)] += 1
    t = len(data)
    return [counter.get(i, 0) / t for i in range(1, total + 1)]


def _compute_omission(data, field, total):
    omission = [0] * total
    for entry in data:
        nums = {int(n) for n in entry[field]}
        for i in range(total):
            omission[i] = 0 if (i + 1) in nums else omission[i] + 1
    mx = max(omission) if max(omission) > 0 else 1
    return [o / mx for o in omission]


def _compute_zone_scores(data, field, total, pick):
    if not data or pick <= 1:
        return [0.5] * total
    zone_count = 4
    zones = [0] * zone_count
    for n in data[0][field]:
        zi = min((int(n) - 1) * zone_count // total, zone_count - 1)
        zones[zi] += 1
    expected = pick / zone_count
    scores = []
    for i in range(total):
        zi = min(i * zone_count // total, zone_count - 1)
        scores.append(max(0, (expected - zones[zi]) / expected))
    return scores


def _compute_odd_even_scores(data, field, total, pick):
    if not data or pick <= 1:
        return [0.5] * total
    latest = data[0][field]
    odd = sum(1 for n in latest if int(n) % 2 == 1)
    even = pick - odd
    expected = pick / 2
    odd_deficit = max(0, (expected - odd) / expected)
    even_deficit = max(0, (expected - even) / expected)
    scores = []
    for i in range(total):
        scores.append(odd_deficit if (i + 1) % 2 == 1 else even_deficit)
    return scores


def _compute_follow_scores(data, field, total):
    if len(data) < 2:
        return [0] * total
    counter = Counter()
    for i in range(len(data) - 1):
        curr = {int(n) for n in data[i][field]}
        nxt = {int(n) for n in data[i + 1][field]}
        for c in curr:
            for n in nxt:
                counter[(c, n)] += 1
    latest = {int(n) for n in data[0][field]}
    scores = [0] * total
    for n in range(1, total + 1):
        s = sum(counter.get((c, n), 0) for c in latest)
        scores[n - 1] = s
    mx = max(scores) if max(scores) > 0 else 1
    return [s / mx for s in scores]


def generate_weights(data=None, is_front=True):
    if data is None:
        data = load_history()
    field = "front" if is_front else "back"
    total = TOTAL_FRONT if is_front else TOTAL_BACK
    pick = PICK_FRONT if is_front else PICK_BACK

    freq = _compute_frequency(data, field, total)
    omission = _compute_omission(data, field, total)
    zone = _compute_zone_scores(data, field, total, pick)
    oe = _compute_odd_even_scores(data, field, total, pick)
    follow = _compute_follow_scores(data, field, total)

    weights = []
    for i in range(total):
        w = (freq[i] * W_FREQ + omission[i] * W_OMISSION +
             zone[i] * W_ZONE + oe[i] * W_ODD_EVEN +
             follow[i] * W_FOLLOW)
        weights.append(w)
    return weights


def print_analysis(data=None):
    if data is None:
        data = load_history()

    for label, is_front in [("红球", True), ("蓝球", False)]:
        w = generate_weights(data, is_front)
        ranked = sorted(enumerate(w, 1), key=lambda x: -x[1])
        top_n = 6 if is_front else len(ranked)
        print(f"\n{label} 综合权重 Top {top_n}:")
        for num, score in ranked[:top_n]:
            bar = "█" * int(score * 50)
            print(f"  {num:02d}: {score:.4f} {bar}")


if __name__ == "__main__":
    data = load_history()
    print(f"已加载 {len(data)} 期双色球数据")
    print_analysis(data)
