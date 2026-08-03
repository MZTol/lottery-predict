import json
import os
from collections import defaultdict
from datetime import datetime


STRATEGY_LABELS = {
    "model": "综合模型",
    "frequency": "近期高频",
    "omission": "当前遗漏",
    "interval": "区间模型",
}

DIR = os.path.dirname(__file__)
SELECTION_FILE = os.path.join(DIR, "strategy_selection.json")
ALGORITHM_VERSION = "strategy-benchmark-v1"

AREA_STRATEGIES = {
    ("kl8", "numbers"): "omission",
    ("dlt", "front"): "model",
    ("dlt", "back"): "model",
    ("ssq", "front"): "frequency",
    ("ssq", "back"): "model",
}


def _load_selection():
    if not os.path.exists(SELECTION_FILE) or os.path.getsize(SELECTION_FILE) == 0:
        return {}
    try:
        with open(SELECTION_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_strategy_selection(data):
    merged = _load_selection()
    if data.get("version"):
        merged["version"] = data["version"]
    if data.get("updated_at"):
        merged["updated_at"] = data["updated_at"]
    for lotid, value in data.items():
        if lotid in ("version", "updated_at"):
            continue
        if isinstance(value, dict):
            merged[lotid] = value
    tmp = SELECTION_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SELECTION_FILE)


def strategy_for(lotid, field, use_saved_selection=True):
    default = AREA_STRATEGIES.get((lotid, field), "model")
    if not use_saved_selection:
        return default
    entry = _load_selection().get(lotid, {}).get(field, {})
    selected = entry.get("selected_strategy")
    return selected if selected in STRATEGY_LABELS else default


def strategy_detail(lotid, field):
    entry = _load_selection().get(lotid, {}).get(field, {})
    if entry:
        return entry
    selected = AREA_STRATEGIES.get((lotid, field), "model")
    return {
        "selected_strategy": selected,
        "strategy_label": strategy_label(selected),
        "selection_source": "默认策略",
        "sample_count": 0,
        "confidence": "未开始动态选择",
    }


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


def interval_recommendation(history, field, total, pick, zones=4):
    """Prefer balanced number ranges without pretending to predict exact draws."""
    if not history:
        return list(range(1, min(total, pick) + 1))

    zone_count = max(1, int(zones or 4))
    zone_size = max(1, (total + zone_count - 1) // zone_count)
    latest = {int(n) for n in history[0].get(field, [])}
    latest_zone_counts = [0] * zone_count
    for n in latest:
        latest_zone_counts[min((n - 1) // zone_size, zone_count - 1)] += 1
    expected_zone = pick / zone_count
    zone_deficit = [
        max(0.0, (expected_zone - count) / max(expected_zone, 1.0))
        for count in latest_zone_counts
    ]

    latest_odd = sum(n % 2 for n in latest)
    expected_odd = pick / 2
    odd_deficit = max(0.0, (expected_odd - latest_odd) / max(expected_odd, 1.0))
    even_deficit = max(
        0.0,
        (expected_odd - (len(latest) - latest_odd)) / max(expected_odd, 1.0),
    )

    omission = {n: len(history) for n in range(1, total + 1)}
    for idx, entry in enumerate(history):
        for n in {int(v) for v in entry.get(field, [])}:
            if 1 <= n <= total and omission[n] == len(history):
                omission[n] = idx
    max_omission = max(omission.values()) or 1

    scored = []
    for n in range(1, total + 1):
        zone = min((n - 1) // zone_size, zone_count - 1)
        parity_deficit = odd_deficit if n % 2 else even_deficit
        omission_score = omission[n] / max_omission
        score = zone_deficit[zone] * 0.55 + parity_deficit * 0.25 + omission_score * 0.20
        scored.append((score, -n, n))

    return sorted(n for _, _, n in sorted(scored, reverse=True)[:pick])


def candidate_recommendations(predictions, counter, cfg, history=None):
    """Return every comparable candidate using only the supplied training history."""
    history = history or []
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    field = cfg["field"]
    return {
        "model": model_recommendation(predictions, counter, pick, total),
        "frequency": frequency_recommendation(history, field, total, pick),
        "omission": omission_recommendation(history, field, total, pick),
        "interval": interval_recommendation(history, field, total, pick, cfg.get("zones", 4)),
    }


def choose_recommendation(
    lotid,
    field,
    predictions,
    counter,
    cfg,
    history=None,
    strategy_override=None,
    use_saved_selection=False,
):
    pick = int(cfg["pick"])
    total = int(cfg["total"])
    strategy = strategy_override or strategy_for(lotid, field, use_saved_selection)
    history = history or []
    if strategy == "frequency" and history:
        nums = frequency_recommendation(history, field, total, pick)
    elif strategy == "omission" and history:
        nums = omission_recommendation(history, field, total, pick)
    elif strategy == "interval" and history:
        nums = interval_recommendation(history, field, total, pick, cfg.get("zones", 4))
    else:
        nums = model_recommendation(predictions, counter, pick, total)
        strategy = "model"
    return nums, strategy
