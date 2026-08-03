import json
import os
from collections import Counter
from datetime import datetime
from json import JSONDecodeError
from strategy import (
    ALGORITHM_VERSION,
    candidate_recommendations,
    choose_recommendation,
    model_recommendation,
    strategy_detail,
    strategy_label,
)


DIR = os.path.dirname(__file__)
PREDICTIONS_FILE = os.path.join(DIR, "predictions_history.json")


def _load_store(filename=PREDICTIONS_FILE):
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        try:
            with open(filename) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (JSONDecodeError, OSError):
            return {}
    return {}


def _save_store(store, filename=PREDICTIONS_FILE):
    tmp = filename + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filename)


def _recommendation(predictions, pick, counter=None):
    if counter:
        ranked = sorted(
            ((int(n), cnt) for n, cnt in counter.items() if cnt > 0),
            key=lambda item: (-item[1], item[0]),
        )
        top = [n for n, _ in ranked[:pick]]
    else:
        combined = Counter()
        for name in ("hot", "cold"):
            combined.update(int(n) for n in predictions.get(name, []))
        if len(combined) < pick:
            for nums in predictions.values():
                combined.update(int(n) for n in nums)
        top = [n for n, _ in combined.most_common(pick)]
    top = sorted(top)
    return [f"{n:02d}" for n in top]


def _expert_consensus(expert_data, field, pick):
    if not expert_data:
        return []
    key = "back" if field == "back" else "front"
    counter = Counter()
    for _, _, all_picks in expert_data:
        counter.update(int(n) for n in all_picks.get(key, []))
    top = [n for n, _ in counter.most_common(pick)]
    return [f"{n:02d}" for n in sorted(top)]


def save_prediction(lotid, period, seed, areas, filename=PREDICTIONS_FILE, expert_data=None, history=None):
    """Persist current run predictions so the next draw can be reviewed."""
    store = _load_store(filename)
    lot_store = store.setdefault(lotid, {})
    period_key = str(period)

    record = {
        "lotid": lotid,
        "period": period_key,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "seed": seed,
        "algorithm_version": ALGORITHM_VERSION,
        "data_latest_period": str(history[0].get("period")) if history else "",
        "training_periods": len(history or []),
        "areas": {},
    }

    for label, field, predictions, counter, cfg in areas:
        clean_predictions = {
            name: [str(n).zfill(2) for n in nums]
            for name, nums in predictions.items()
        }
        pick = int(cfg["pick"])
        area_record = {
            "label": label,
            "field": field,
            "total": int(cfg["total"]),
            "pick": pick,
            "sample_count": sum(counter.values()),
            "predictions": clean_predictions,
        }
        rec, strategy = choose_recommendation(
            lotid,
            field,
            clean_predictions,
            counter,
            cfg,
            history=history,
            use_saved_selection=True,
        )
        area_record["recommendation"] = [f"{int(n):02d}" for n in rec]
        area_record["model_recommendation"] = [
            f"{int(n):02d}"
            for n in model_recommendation(clean_predictions, counter, pick, int(cfg["total"]))
        ]
        if history:
            candidates = candidate_recommendations(
                clean_predictions,
                counter,
                {**cfg, "field": field},
                history=history,
            )
            area_record["model_candidates"] = {
                name: [f"{int(n):02d}" for n in nums]
                for name, nums in candidates.items()
            }
        area_record["strategy"] = strategy
        area_record["strategy_label"] = strategy_label(strategy)
        detail = strategy_detail(lotid, field)
        area_record["strategy_confidence"] = detail.get("confidence", "未开始动态选择")
        area_record["strategy_selection_source"] = detail.get(
            "selection_source", "默认策略"
        )
        expert_consensus = _expert_consensus(expert_data, field, pick)
        if expert_consensus:
            area_record["expert_consensus"] = expert_consensus
        record["areas"][field] = area_record

    lot_store[period_key] = record
    _save_store(store, filename)
    return record


def evaluate_prediction(lotid, actual_draw, filename=PREDICTIONS_FILE):
    """Compare a stored prediction for actual_draw['period'] with actual numbers."""
    store = _load_store(filename)
    period_key = str(actual_draw["period"])
    record = store.get(lotid, {}).get(period_key)
    if not record:
        return None

    result = {
        "lotid": lotid,
        "period": period_key,
        "generated_at": record.get("generated_at", ""),
        "seed": record.get("seed"),
        "areas": [],
    }

    for area in record.get("areas", {}).values():
        field = area.get("field")
        if field not in actual_draw:
            continue

        actual = sorted(int(n) for n in actual_draw[field])
        groups = dict(area.get("predictions", {}))
        if area.get("recommendation"):
            groups["recommendation"] = area["recommendation"]
        if area.get("expert_consensus"):
            groups["expert_consensus"] = area["expert_consensus"]

        comparisons = []
        actual_set = set(actual)
        for name, nums in groups.items():
            predicted = sorted(int(n) for n in nums)
            predicted_set = set(predicted)
            comparisons.append({
                "name": name,
                "predicted": predicted,
                "hits": sorted(predicted_set & actual_set),
                "misses": sorted(predicted_set - actual_set),
                "uncovered": sorted(actual_set - predicted_set),
            })

        result["areas"].append({
            "label": area.get("label", field),
            "field": field,
            "actual": actual,
            "comparisons": comparisons,
        })

    return result
