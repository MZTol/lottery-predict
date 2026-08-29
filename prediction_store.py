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
EXPERT_SIGNAL_WEIGHT = 0.10


def _load_store(filename=PREDICTIONS_FILE):
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        try:
            with open(filename) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (JSONDecodeError, OSError):
            return {}
    return {}


def load_prediction_store(filename=PREDICTIONS_FILE):
    """Load saved predictions for report-time historical comparisons."""
    return _load_store(filename)


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


def _expert_reliability(lot_store, history, field, total):
    """Estimate expert lift against the per-draw random baseline."""
    actual_by_period = {str(row.get("period")): set(int(n) for n in row.get(field, [])) for row in history or []}
    stats = {}
    for period, record in (lot_store or {}).items():
        actual = actual_by_period.get(str(period))
        if not actual:
            continue
        area = next((item for item in record.get("areas", {}).values() if item.get("field") == field), None)
        if not area:
            continue
        draw_size = len(actual)
        for source in area.get("expert_sources", []):
            values = set()
            for pick in (source.get("picks") or {}).values():
                values.update(int(n) for n in pick.get("front" if field != "back" else "back", []))
            if not values:
                continue
            item = stats.setdefault(source.get("name", ""), {"periods": 0, "delta": 0.0})
            item["periods"] += 1
            item["delta"] += len(values & actual) - len(values) * draw_size / max(total, 1)
    result = {}
    for name, item in stats.items():
        periods = item["periods"]
        if periods < 30:
            result[name] = {"periods": periods, "weight": 1.0}
            continue
        lift = item["delta"] / periods
        shrink = periods / (periods + 30.0)
        result[name] = {
            "periods": periods,
            "weight": max(-1.0, min(1.0, lift * shrink)),
        }
    return result


def _expert_vote_counters(expert_data, field, total, reliability=None):
    """Count one ballot per expert, rather than rewarding duplicate articles."""
    key = "back" if field == "back" else "front"
    positive = Counter()
    negative = Counter()
    expert_count = 0
    if not expert_data:
        return positive, negative, expert_count
    for _, experts, all_picks in expert_data:
        if experts:
            for expert in experts:
                expert_count += 1
                values = set()
                for pick in (expert.get("picks") or {}).values():
                    values.update(int(n) for n in pick.get(key, []))
                rel = (reliability or {}).get(expert.get("name", ""), {})
                weight = float(rel.get("weight", 1.0))
                vote_weight = max(0.25, 1.0 + 0.5 * weight)
                positive.update({n: vote_weight for n in values if 1 <= n <= total})
                # Current article parsers classify explicit exclusions as
                # front/number exclusions. Do not leak them into a back-area
                # recommendation until a source provides area-specific data.
                if field != "back":
                    negative.update({
                        n: vote_weight for n in set(int(v) for v in expert.get("avoid", []))
                        if 1 <= n <= total
                    })
                if rel.get("periods", 0) >= 30 and weight < 0:
                    negative.update({n: abs(weight) for n in values if 1 <= n <= total})
        else:
            # Backward-compatible fallback for old callers/tests that only
            # provide the flattened all_picks structure.
            values = set(int(n) for n in all_picks.get(key, []))
            positive.update(n for n in values if 1 <= n <= total)
            negative.update(
                n for n in set(int(v) for v in all_picks.get("avoid_front", []))
                if 1 <= n <= total
            )
            expert_count = max(expert_count, 1 if values or negative else 0)
    return positive, negative, expert_count


def expert_recommendation(base, predictions, counter, expert_data, cfg, reliability=None):
    """Return expert groups and a conservative expert-adjusted recommendation.

    The expert signal is intentionally capped.  It is an external feature,
    not a replacement for the lottery model, and explicit exclusions are
    exposed separately so they cannot silently become "cold number" logic.
    """
    if not expert_data:
        return {
            "recommendation": list(base),
            "consensus": [],
            "avoid": [],
            "contrarian": [],
            "expert_count": 0,
        }
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    positive, negative, expert_count = _expert_vote_counters(
        expert_data, cfg.get("field", "front"), total, reliability=reliability
    )
    consensus = [n for n, _ in positive.most_common(pick)]
    avoid = [n for n, _ in negative.most_common(pick)]

    # Build a stable base ranking from the already selected numbers, then
    # from the model's high-confidence candidates and sampling frequency.
    ranking = []
    for group in (base, predictions.get("hot", []), predictions.get("kill_b", [])):
        for value in group:
            n = int(value)
            if 1 <= n <= total and n not in ranking:
                ranking.append(n)
    for n, _ in sorted(((int(n), c) for n, c in (counter or {}).items()), key=lambda item: (-item[1], item[0])):
        if 1 <= n <= total and n not in ranking:
            ranking.append(n)
    ranking.extend(n for n in range(1, total + 1) if n not in ranking)
    base_rank = {n: 1.0 - i / max(len(ranking), 1) for i, n in enumerate(ranking)}
    max_positive = max(positive.values(), default=1)
    max_negative = max(negative.values(), default=1)
    scores = []
    for n in range(1, total + 1):
        expert_score = positive[n] / max_positive if positive else 0.0
        avoid_score = negative[n] / max_negative if negative else 0.0
        score = (
            base_rank[n] * (1.0 - EXPERT_SIGNAL_WEIGHT)
            + expert_score * EXPERT_SIGNAL_WEIGHT
            - avoid_score * EXPERT_SIGNAL_WEIGHT
        )
        scores.append((score, -n, n))
    recommendation = sorted(n for _, _, n in sorted(scores, reverse=True)[:pick])
    contrarian_pool = [n for _, _, n in sorted(scores, reverse=True) if n not in set(consensus) and n not in set(avoid)]
    contrarian = sorted(contrarian_pool[:pick])
    return {
        "recommendation": recommendation,
        "consensus": sorted(consensus),
        "avoid": sorted(avoid),
        "contrarian": contrarian,
        "expert_count": expert_count,
    }


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
        reliability = _expert_reliability(lot_store, history, field, int(cfg["total"]))
        expert_info = expert_recommendation(
            rec, clean_predictions, counter, expert_data, {**cfg, "field": field}, reliability=reliability
        )
        rec = expert_info["recommendation"]
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
        if expert_info["consensus"]:
            area_record["expert_consensus"] = [f"{n:02d}" for n in expert_info["consensus"]]
        if expert_info["avoid"]:
            area_record["expert_avoid"] = [f"{n:02d}" for n in expert_info["avoid"]]
        if expert_info["contrarian"]:
            area_record["expert_contrarian"] = [f"{n:02d}" for n in expert_info["contrarian"]]
        if expert_data:
            area_record["expert_reliability"] = reliability
            area_record["expert_sources"] = [
                {
                    "name": item.get("name", ""),
                    "url": item.get("url", ""),
                    "picks": item.get("picks", {}),
                    "avoid": item.get("avoid", []),
                }
                for _, expert_list, _ in expert_data
                for item in expert_list
            ]
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
        if area.get("expert_avoid"):
            groups["expert_avoid"] = area["expert_avoid"]
        if area.get("expert_contrarian"):
            groups["expert_contrarian"] = area["expert_contrarian"]

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
