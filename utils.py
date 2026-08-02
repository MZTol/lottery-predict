import json
import os
import random
from collections import Counter
from datetime import datetime, timedelta


def weighted_sample(weights, k, seed, cooccur=None, cooccur_factor=0.4):
    indices = list(range(len(weights)))
    w = list(weights)
    rng = random.Random(seed)
    result = []
    for _ in range(k):
        total = sum(w)
        if total <= 0:
            pick = rng.choice(indices)
        else:
            r = rng.random() * total
            cumulative = 0
            pick = indices[0]
            for i, idx in enumerate(indices):
                cumulative += w[i]
                if r <= cumulative:
                    pick = idx
                    break
        result.append(pick + 1)
        pos = indices.index(pick)
        indices.pop(pos)
        w.pop(pos)
        if cooccur is not None:
            for i, idx in enumerate(indices):
                w[i] *= (1.0 + cooccur[pick][idx] * cooccur_factor)
    result.sort()
    return [str(n).zfill(2) for n in result]


LOTTERY_INFO = {
    "kl8":  {"draw_days": list(range(7)), "draw_time": "21:30"},
    "dlt":  {"draw_days": [0, 2, 5],       "draw_time": "21:25"},
    "ssq":  {"draw_days": [1, 3, 6],       "draw_time": "21:15"},
}


def get_latest_draw(data, lotid):
    latest = data[0]
    next_period = int(latest["period"]) + 1
    return latest, next_period


def _last_draw_datetime(lotid):
    """返回最近一次已过的开奖时间（往前查3天）"""
    info = LOTTERY_INFO[lotid]
    now = datetime.now()
    for days_ago in range(3):
        day = now - timedelta(days=days_ago)
        if day.weekday() in info["draw_days"]:
            dt_str = day.strftime("%Y-%m-%d") + " " + info["draw_time"]
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            if dt <= now:
                return dt
    return None


def is_data_fresh(filepath, lotid, max_age_hours=1):
    if not os.path.exists(filepath):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    age = (datetime.now() - mtime).total_seconds() / 3600
    if age >= max_age_hours:
        return False
    last_draw = _last_draw_datetime(lotid)
    if last_draw is not None and mtime < last_draw:
        return False
    return True


def data_status(filepath, lotid, data=None, max_age_hours=1):
    exists = os.path.exists(filepath)
    mtime = datetime.fromtimestamp(os.path.getmtime(filepath)) if exists else None
    age_hours = (datetime.now() - mtime).total_seconds() / 3600 if mtime else None
    latest_period = data[0].get("period") if data else ""
    last_draw = _last_draw_datetime(lotid)
    fresh = is_data_fresh(filepath, lotid, max_age_hours) if exists else False
    if not exists:
        state = "无缓存"
    elif fresh:
        state = "数据较新"
    else:
        state = "使用缓存"
    return {
        "state": state,
        "fresh": fresh,
        "latest_period": str(latest_period),
        "cache_time": mtime.strftime("%Y-%m-%d %H:%M") if mtime else "",
        "age_hours": age_hours,
        "last_draw_time": last_draw.strftime("%Y-%m-%d %H:%M") if last_draw else "",
    }


def ensure_fresh(filepath, lotid, max_age_hours=1):
    from crawler import fetch_incremental, fetch_all, save

    if os.path.exists(filepath):
        with open(filepath) as f:
            stale = json.load(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        age = (datetime.now() - mtime).total_seconds() / 3600
        print(f"  缓存 {os.path.basename(filepath)}: {len(stale)}期, {age:.1f}小时前保存")
        if is_data_fresh(filepath, lotid, max_age_hours) and stale:
            return stale
        print(f"  增量更新 {lotid}...")
        try:
            data = fetch_incremental(lotid, filepath)
            if data:
                save(data, filepath)
            return data or stale
        except Exception as e:
            print(f"  增量拉取失败: {e}")
            if stale:
                print(f"  使用旧缓存 ({len(stale)}期)")
                return stale
            raise
    else:
        print(f"  首次拉取 {lotid}...")
        data = fetch_all(lotid)
        if not data:
            raise RuntimeError(f"无法获取 {lotid} 数据")
        save(data, filepath)
        return data


# ─── 过滤器 ───

def check_sum_range(numbers, cfg):
    total_n = cfg["total"]
    pick = cfg["pick"]
    avg = (1 + total_n) / 2 * pick
    tol = avg * 0.15
    s = sum(int(n) for n in numbers)
    return abs(s - avg) <= tol


def check_odd_even_ratio(numbers):
    ns = [int(n) for n in numbers]
    if len(ns) <= 1:
        return True
    odd = sum(1 for n in ns if n % 2 == 1)
    r = odd / len(ns)
    return 0.25 <= r <= 0.75


def check_zone_distribution(numbers, cfg, max_per_zone=None):
    total_n = cfg["total"]
    pick = cfg["pick"]
    zc = cfg.get("zones", 4)
    zone_size = total_n // zc
    max_pz = max_per_zone or (pick // zc + min(pick // zc, 3))
    zones = [0] * zc
    for n in numbers:
        zi = min((int(n) - 1) // zone_size, zc - 1)
        zones[zi] += 1
    return all(z <= max_pz for z in zones)


def check_consecutive(numbers, max_consec=4):
    ns = sorted(int(n) for n in numbers)
    if len(ns) <= 1:
        return True
    streak = 1
    for i in range(1, len(ns)):
        if ns[i] == ns[i - 1] + 1:
            streak += 1
            if streak > max_consec:
                return False
        else:
            streak = 1
    return True


def check_spread(numbers, cfg):
    ns = [int(n) for n in numbers]
    if len(ns) <= 1:
        return True
    span = max(ns) - min(ns)
    total_n = cfg["total"]
    return span >= total_n * 0.5


def generate_filtered(weights, k, seed, cfg, cooccur=None, max_attempts=50, cooccur_factor=0.4):
    for offset in range(max_attempts):
        s = seed * 1000 + offset
        result = weighted_sample(weights, k, s, cooccur, cooccur_factor)
        ns = [int(n) for n in result]
        if k >= 5 and not check_sum_range(result, cfg):
            continue
        if k >= 4 and not check_odd_even_ratio(result):
            continue
        if k >= 4 and not check_zone_distribution(result, cfg):
            continue
        if k >= 4 and not check_consecutive(result):
            continue
        if k >= 5 and not check_spread(result, cfg):
            continue
        return result
    return weighted_sample(weights, k, seed * 1000, cooccur, cooccur_factor)


# ─── 集成投票 ───

def ensemble_vote(data, cfg, seed, cooccur=None, n_variants=10):
    """多组权重生成结果，投票取高频号码"""
    from analyzer import generate_weights, DEFAULT_WEIGHTS, WINDOWS

    weight_sets = []

    weight_sets.append(DEFAULT_WEIGHTS)

    for k in DEFAULT_WEIGHTS:
        v = dict(DEFAULT_WEIGHTS)
        v[k] = min(v[k] + 0.05, 0.30)
        for other in DEFAULT_WEIGHTS:
            if other != k:
                v[other] = max(v[other] - 0.05 / (len(DEFAULT_WEIGHTS) - 1), 0)
        weight_sets.append(v)

    all_picks = []
    window = max(min(w for w in WINDOWS if w <= len(data)), 20)
    for i, wt in enumerate(weight_sets[:n_variants]):
        w = generate_weights(data, cfg, wt)
        r = weighted_sample(w, cfg["pick"], seed + i, cooccur)
        all_picks.extend(int(n) for n in r)

    counter = Counter(all_picks)
    top = [n for n, _ in counter.most_common(cfg["pick"])]
    top.sort()
    result = [str(n).zfill(2) for n in top]

    if not check_sum_range(result, cfg):
        for offset in range(10):
            alt = [n for n, _ in counter.most_common(cfg["pick"] + offset)]
            alt = alt[:cfg["pick"]]
            alt.sort()
            result = [str(n).zfill(2) for n in alt]
            if check_sum_range(result, cfg):
                break

    return result, counter
