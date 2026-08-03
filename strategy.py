from collections import defaultdict


STRATEGY_LABELS = {
    "model": "综合模型",
    "frequency": "近期高频",
    "omission": "当前遗漏",
}


AREA_STRATEGIES = {
    ("kl8", "numbers"): "omission",
    ("dlt", "front"): "model",
    ("dlt", "back"): "model",
    ("ssq", "front"): "frequency",
    ("ssq", "back"): "model",
}


def strategy_for(lotid, field):
    return AREA_STRATEGIES.get((lotid, field), "model")


def strategy_label(strategy):
    return STRATEGY_LABELS.get(strategy, strategy)


def _ranked_counter(counter, total=None):
    items = []
    for n, cnt in (counter or {}).items():
        ni = int(n)
        if cnt > 0 and (total is None or 1 <= ni <= total):
            items.append((ni, cnt))
    return [n for n, _ in sorted(items, key=lambda item: (-item[1], item[0]))]


def _pad(nums, total, pick):
    out = []
    for n in nums:
        ni = int(n)
        if 1 <= ni <= total and ni not in out:
            out.append(ni)
        if len(out) >= pick:
            return sorted(out)
    for n in range(1, total + 1):
        if n not in out:
            out.append(n)
        if len(out) >= pick:
            return sorted(out)
    return sorted(out)


def model_recommendation(predictions, counter, pick, total):
    ranked = _ranked_counter(counter, total)
    fallback = []
    for name in ("hot", "cold", "kill_b", "kill_c", "kill_a"):
        fallback.extend(int(n) for n in predictions.get(name, []))
    return _pad(ranked + fallback, total, pick)


def frequency_recommendation(history, field, total, pick):
    counts = defaultdict(int)
    for entry in history:
        for n in entry.get(field, []):
            ni = int(n)
            if 1 <= ni <= total:
                counts[ni] += 1
    ranked = sorted(range(1, total + 1), key=lambda n: (-counts[n], n))
    return sorted(ranked[:pick])


def omission_recommendation(history, field, total, pick):
    omission = {n: len(history) for n in range(1, total + 1)}
    for idx, entry in enumerate(history):
        nums = {int(n) for n in entry.get(field, [])}
        for n in nums:
            if 1 <= n <= total and omission[n] == len(history):
                omission[n] = idx
    ranked = sorted(range(1, total + 1), key=lambda n: (-omission[n], n))
    return sorted(ranked[:pick])


def choose_recommendation(lotid, field, predictions, counter, cfg, history=None):
    pick = int(cfg["pick"])
    total = int(cfg["total"])
    strategy = strategy_for(lotid, field)
    history = history or []
    if strategy == "frequency" and history:
        nums = frequency_recommendation(history, field, total, pick)
    elif strategy == "omission" and history:
        nums = omission_recommendation(history, field, total, pick)
    else:
        nums = model_recommendation(predictions, counter, pick, total)
        strategy = "model"
    return nums, strategy
