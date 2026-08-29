from collections import Counter, defaultdict


MODEL_LABELS = {
    "model": "综合模型",
    "frequency": "近期高频",
    "omission": "当前遗漏",
    "interval": "区间模型",
    "linear_score": "线性评分",
    "nearest_draw": "相似期开奖",
}


def validate_prediction_output(nums, cfg, model_name="model"):
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    cleaned = []
    for n in nums:
        try:
            value = int(n)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{model_name} 输出包含非数字号码: {n}") from exc
        if not 1 <= value <= total:
            raise ValueError(f"{model_name} 输出号码越界: {value}")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) != pick:
        raise ValueError(f"{model_name} 输出数量应为{pick}，实际{len(cleaned)}")
    return sorted(cleaned)


def _pad(nums, cfg, model_name):
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    out = []
    for n in nums:
        value = int(n)
        if 1 <= value <= total and value not in out:
            out.append(value)
        if len(out) >= pick:
            return validate_prediction_output(out, cfg, model_name)
    for n in range(1, total + 1):
        if n not in out:
            out.append(n)
        if len(out) >= pick:
            return validate_prediction_output(out, cfg, model_name)
    return validate_prediction_output(out, cfg, model_name)


def _ranked_counter(counter, total):
    items = []
    for n, cnt in (counter or {}).items():
        value = int(n)
        if cnt > 0 and 1 <= value <= total:
            items.append((value, cnt))
    return [n for n, _ in sorted(items, key=lambda item: (-item[1], item[0]))]


def _latest_omission(history, field, total):
    omission = {n: len(history) for n in range(1, total + 1)}
    for idx, entry in enumerate(history or []):
        for n in {int(v) for v in entry.get(field, [])}:
            if 1 <= n <= total and omission[n] == len(history):
                omission[n] = idx
    return omission


def _frequency_counts(history, field, total, limit=None):
    counts = defaultdict(int)
    rows = history[:limit] if limit else history
    for entry in rows or []:
        for n in entry.get(field, []):
            value = int(n)
            if 1 <= value <= total:
                counts[value] += 1
    return counts


def model_predict(history, cfg, context=None):
    context = context or {}
    total = int(cfg["total"])
    predictions = context.get("predictions") or {}
    counter = context.get("counter") or Counter()
    ranked = _ranked_counter(counter, total)
    fallback = []
    for name in ("hot", "cold", "kill_b", "kill_c", "kill_a"):
        fallback.extend(int(n) for n in predictions.get(name, []))
    return _pad(ranked + fallback, cfg, "model")


def frequency_predict(history, cfg, context=None):
    total = int(cfg["total"])
    field = cfg["field"]
    counts = _frequency_counts(history or [], field, total)
    ranked = sorted(range(1, total + 1), key=lambda n: (-counts[n], n))
    return validate_prediction_output(ranked[: int(cfg["pick"])], cfg, "frequency")


def omission_predict(history, cfg, context=None):
    total = int(cfg["total"])
    field = cfg["field"]
    omission = _latest_omission(history or [], field, total)
    ranked = sorted(range(1, total + 1), key=lambda n: (-omission[n], n))
    return validate_prediction_output(ranked[: int(cfg["pick"])], cfg, "omission")


def interval_predict(history, cfg, context=None):
    history = history or []
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    field = cfg["field"]
    zone_count = max(1, int(cfg.get("zones", 4) or 4))
    zone_size = max(1, (total + zone_count - 1) // zone_count)

    latest = {int(n) for n in history[0].get(field, [])} if history else set()
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
    omission = _latest_omission(history, field, total)
    max_omission = max(omission.values()) or 1

    scored = []
    for n in range(1, total + 1):
        zone = min((n - 1) // zone_size, zone_count - 1)
        parity_deficit = odd_deficit if n % 2 else even_deficit
        omission_score = omission[n] / max_omission
        score = zone_deficit[zone] * 0.55 + parity_deficit * 0.25 + omission_score * 0.20
        scored.append((score, -n, n))
    nums = [n for _, _, n in sorted(scored, reverse=True)[:pick]]
    return validate_prediction_output(nums, cfg, "interval")


def linear_score_predict(history, cfg, context=None):
    history = history or []
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    field = cfg["field"]
    context = context or {}
    counter = context.get("counter") or Counter()
    model_rank = {n: i for i, n in enumerate(_ranked_counter(counter, total))}

    recent_counts = _frequency_counts(history, field, total, limit=30)
    long_counts = _frequency_counts(history, field, total)
    omission = _latest_omission(history, field, total)
    max_recent = max(recent_counts.values(), default=1)
    max_long = max(long_counts.values(), default=1)
    max_omission = max(omission.values(), default=1)

    latest = {int(n) for n in history[0].get(field, [])} if history else set()
    neighbor = defaultdict(float)
    for n in latest:
        for offset in (-2, -1, 1, 2):
            value = n + offset
            if 1 <= value <= total:
                neighbor[value] += 1.0 / abs(offset)
    max_neighbor = max(neighbor.values(), default=1.0)

    interval_nums = set(interval_predict(history, cfg, context)) if history else set()
    model_norm = max(1, len(model_rank) - 1)
    scored = []
    for n in range(1, total + 1):
        model_score = 1.0 - (model_rank.get(n, total) / max(total, model_norm))
        score = (
            (recent_counts[n] / max_recent) * 0.25
            + (long_counts[n] / max_long) * 0.18
            + (omission[n] / max_omission) * 0.22
            + (neighbor[n] / max_neighbor) * 0.15
            + (1.0 if n in interval_nums else 0.0) * 0.10
            + model_score * 0.10
        )
        scored.append((score, -n, n))
    nums = [n for _, _, n in sorted(scored, reverse=True)[:pick]]
    return validate_prediction_output(nums, cfg, "linear_score")


def _draw_similarity(left, right, total, zones=4):
    """Compare two draws by overlap and coarse structure, not period number."""
    left = set(left)
    right = set(right)
    if not left or not right:
        return 0.0
    overlap = len(left & right) / max(len(left), len(right))
    max_sum_gap = max(1, total * max(len(left), len(right)))
    sum_score = 1.0 - min(1.0, abs(sum(left) - sum(right)) / max_sum_gap)
    odd_score = 1.0 - abs(sum(n % 2 for n in left) - sum(n % 2 for n in right)) / max(len(left), len(right))
    zone_size = max(1, (total + zones - 1) // zones)

    def zone_counts(nums):
        counts = [0] * zones
        for n in nums:
            counts[min((n - 1) // zone_size, zones - 1)] += 1
        return counts

    left_zones = zone_counts(left)
    right_zones = zone_counts(right)
    zone_gap = sum(abs(a - b) for a, b in zip(left_zones, right_zones))
    zone_score = 1.0 - min(1.0, zone_gap / max(1, len(left) + len(right)))
    return overlap * 0.65 + sum_score * 0.15 + odd_score * 0.10 + zone_score * 0.10


def nearest_draw_predict(history, cfg, context=None):
    """Vote from outcomes following past draws most similar to the latest draw."""
    history = history or []
    total = int(cfg["total"])
    pick = int(cfg["pick"])
    field = cfg["field"]
    zones = max(1, int(cfg.get("zones", 4) or 4))
    if len(history) < 3:
        return frequency_predict(history, cfg, context)

    query = {int(n) for n in history[0].get(field, [])}
    matches = []
    # history is newest first. For an anchor at i, i-1 is the draw that
    # happened immediately after it and is therefore its known outcome.
    for i in range(1, len(history)):
        anchor = {int(n) for n in history[i].get(field, [])}
        outcome = {int(n) for n in history[i - 1].get(field, [])}
        similarity = _draw_similarity(query, anchor, total, zones)
        recency = 1.0 / (1.0 + i / 30.0)
        matches.append((similarity, recency, -i, outcome))

    neighbor_count = min(12, max(5, int(len(matches) ** 0.5)))
    votes = defaultdict(float)
    for similarity, recency, _, outcome in sorted(matches, reverse=True)[:neighbor_count]:
        # Cubing prevents many structurally vague matches from overwhelming
        # the few genuinely close draws.
        weight = max(similarity, 0.01) ** 3 * (0.80 + recency * 0.20)
        for n in outcome:
            if 1 <= n <= total:
                votes[n] += weight

    recent = _frequency_counts(history, field, total, limit=30)
    ranked = sorted(
        range(1, total + 1),
        key=lambda n: (-votes[n], -recent[n], n),
    )
    return validate_prediction_output(ranked[:pick], cfg, "nearest_draw")


MODEL_REGISTRY = {
    "model": model_predict,
    "frequency": frequency_predict,
    "omission": omission_predict,
    "interval": interval_predict,
    "linear_score": linear_score_predict,
    "nearest_draw": nearest_draw_predict,
}


def predict_model(name, history, cfg, context=None):
    if name not in MODEL_REGISTRY:
        raise KeyError(f"未知模型: {name}")
    return MODEL_REGISTRY[name](history or [], cfg, context or {})


def candidate_recommendations(predictions, counter, cfg, history=None):
    context = {"predictions": predictions or {}, "counter": counter or Counter()}
    return {
        name: predict_model(name, history or [], cfg, context)
        for name in MODEL_REGISTRY
    }


def explain_numbers(nums, history, cfg, context=None):
    history = history or []
    total = int(cfg["total"])
    field = cfg["field"]
    recent_counts = _frequency_counts(history, field, total, limit=30)
    omission = _latest_omission(history, field, total)
    interval_set = set(interval_predict(history, cfg, context)) if history else set()
    nearest_set = set(nearest_draw_predict(history, cfg, context)) if len(history) >= 3 else set()
    explanations = {}
    for n in sorted(int(v) for v in nums):
        tags = []
        if recent_counts[n] > 0:
            tags.append(f"近30期{recent_counts[n]}次")
        if omission[n] > 0:
            tags.append(f"遗漏{omission[n]}期")
        if n in interval_set:
            tags.append("区间补位")
        if n in nearest_set:
            tags.append("相似期后续高频")
        tags.append("奇数" if n % 2 else "偶数")
        explanations[n] = tags[:4]
    return explanations
