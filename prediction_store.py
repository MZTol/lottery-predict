import json
import os
from collections import Counter
from datetime import datetime


DIR = os.path.dirname(__file__)
PREDICTIONS_FILE = os.path.join(DIR, "predictions_history.json")


def _load_store(filename=PREDICTIONS_FILE):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return {}


def _save_store(store, filename=PREDICTIONS_FILE):
    tmp = filename + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filename)


def _recommendation(predictions, pick):
    combined = Counter()
    for nums in predictions.values():
        combined.update(int(n) for n in nums)
    top = sorted(n for n, _ in combined.most_common(pick))
    return [f"{n:02d}" for n in top]


def save_prediction(lotid, period, seed, areas, filename=PREDICTIONS_FILE):
    """Persist current run predictions so the next draw can be reviewed."""
    store = _load_store(filename)
    lot_store = store.setdefault(lotid, {})
    period_key = str(period)

    record = {
        "lotid": lotid,
        "period": period_key,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "seed": seed,
        "areas": {},
    }

    for label, field, predictions, counter, cfg in areas:
        clean_predictions = {
            name: [str(n).zfill(2) for n in nums]
            for name, nums in predictions.items()
        }
        pick = int(cfg["pick"])
        record["areas"][field] = {
            "label": label,
            "field": field,
            "total": int(cfg["total"]),
            "pick": pick,
            "sample_count": sum(counter.values()),
            "predictions": clean_predictions,
            "recommendation": _recommendation(clean_predictions, pick),
        }

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
