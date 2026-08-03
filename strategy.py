import json
import os
from datetime import datetime
from model_registry import (
    MODEL_LABELS,
    candidate_recommendations,
    frequency_predict,
    interval_predict,
    linear_score_predict,
    model_predict,
    omission_predict,
    predict_model,
)


STRATEGY_LABELS = dict(MODEL_LABELS)

DIR = os.path.dirname(__file__)
SELECTION_FILE = os.path.join(DIR, "strategy_selection.json")
ALGORITHM_VERSION = "model-registry-v1"

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
    return model_predict(
        [],
        {"field": "numbers", "total": total, "pick": pick, "zones": 4},
        {"predictions": predictions, "counter": counter},
    )


def frequency_recommendation(history, field, total, pick):
    return frequency_predict(
        history,
        {"field": field, "total": total, "pick": pick, "zones": 4},
    )


def omission_recommendation(history, field, total, pick):
    return omission_predict(
        history,
        {"field": field, "total": total, "pick": pick, "zones": 4},
    )


def interval_recommendation(history, field, total, pick, zones=4):
    return interval_predict(
        history,
        {"field": field, "total": total, "pick": pick, "zones": zones},
    )


def linear_score_recommendation(history, field, total, pick, zones=4, predictions=None, counter=None):
    return linear_score_predict(
        history,
        {"field": field, "total": total, "pick": pick, "zones": zones},
        {"predictions": predictions or {}, "counter": counter or {}},
    )


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
    if strategy not in STRATEGY_LABELS:
        strategy = "model"
    if strategy != "model" and not history:
        strategy = "model"
    nums = predict_model(
        strategy,
        history,
        {**cfg, "field": field, "total": total, "pick": pick},
        {"predictions": predictions or {}, "counter": counter or {}},
    )
    return nums, strategy
