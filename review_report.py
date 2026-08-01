import json
import os
import sys
from collections import defaultdict
from datetime import datetime

from prediction_store import PREDICTIONS_FILE
from report import REPORTS_DIR


DIR = os.path.dirname(__file__)

LOTTERY_LABELS = {
    "kl8": "快乐8",
    "dlt": "大乐透",
    "ssq": "双色球",
}

HISTORY_FILES = {
    "kl8": os.path.join(DIR, "kl8_history.json"),
    "dlt": os.path.join(DIR, "dlt_history.json"),
    "ssq": os.path.join(DIR, "ssq_history.json"),
}

GROUP_LABELS = {
    "hot": "热门",
    "cold": "冷门",
    "kill_a": "杀号A",
    "kill_b": "杀号B",
    "kill_c": "杀号C",
    "recommendation": "综合推荐",
}


def _load_json(filename, default):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return default


def _fmt_nums(nums):
    if not nums:
        return '<span class="muted">无</span>'
    return " ".join(f'<span class="num">{int(n):02d}</span>' for n in nums)


def _num_key(period):
    try:
        return int(period)
    except (TypeError, ValueError):
        return 0


def _style():
    return """
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      * { box-sizing: border-box; }
      body { margin: 0; padding: 14px; background: #f5f5f5; color: #222; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.45; }
      main { max-width: 960px; margin: 0 auto; }
      h1 { margin: 4px 0 6px; color: #1a1a2e; font-size: 24px; line-height: 1.25; }
      h2 { margin: 22px 0 8px; color: #16213e; font-size: 19px; line-height: 1.3; }
      h3 { margin: 16px 0 8px; color: #24324a; font-size: 16px; line-height: 1.35; }
      .meta, .muted { color: #666; font-size: 13px; }
      .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin: 12px 0; }
      .stat { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 10px; }
      .stat .val { display: block; color: #16213e; font-size: 20px; font-weight: 700; }
      .stat .lbl { display: block; color: #666; font-size: 12px; margin-top: 2px; }
      .table-wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
      table { width: 100%; min-width: 760px; border-collapse: collapse; margin: 10px 0; background: #fff; font-size: 13px; }
      th, td { border: 1px solid #ddd; padding: 5px 6px; text-align: center; vertical-align: top; }
      th { background: #16213e; color: #fff; position: sticky; top: 0; }
      tr:nth-child(even) { background: #fafafa; }
      .num { display: inline-block; margin: 1px; padding: 2px 5px; font-weight: 700; font-family: 'SF Mono', 'Courier New', monospace; }
      .good { color: #155724; font-weight: 700; }
      .bad { color: #9f1239; font-weight: 700; }
      .flat { color: #666; font-weight: 700; }
      .section { margin: 14px 0; padding-top: 2px; border-top: 1px solid #ddd; }
      @media (max-width: 640px) {
        body { padding: 10px; }
        h1 { font-size: 21px; }
        h2 { font-size: 17px; }
        .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .mobile-cards { overflow: visible; }
        .mobile-cards table,
        .mobile-cards thead,
        .mobile-cards tbody,
        .mobile-cards tr,
        .mobile-cards th,
        .mobile-cards td { display: block; width: 100%; min-width: 0; }
        .mobile-cards thead { display: none; }
        .mobile-cards table { min-width: 0; border-collapse: separate; border-spacing: 0; background: transparent; }
        .mobile-cards tr { margin: 8px 0; padding: 7px 9px; border: 1px solid #ddd; border-radius: 8px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
        .mobile-cards tr:nth-child(even) { background: #fff; }
        .mobile-cards td { display: grid; grid-template-columns: minmax(86px, 34%) minmax(0, 1fr); gap: 8px; border: 0; border-bottom: 1px solid #eee; padding: 7px 0; text-align: left; }
        .mobile-cards td:last-child { border-bottom: 0; }
        .mobile-cards td::before { content: attr(data-label); color: #666; font-size: 12px; font-weight: 600; }
        .mobile-cards td[data-label="期号"],
        .mobile-cards td[data-label="类型"] { color: #16213e; font-weight: 700; }
      }
    </style>
    """


def _td(label, value):
    return f'<td data-label="{label}">{value}</td>'


def _baseline_class(delta, lower_is_better=False):
    if abs(delta) < 0.001:
        return "flat"
    better = delta < 0 if lower_is_better else delta > 0
    return "good" if better else "bad"


def _compare_group(group_name, predicted, actual, total):
    predicted_set = {int(n) for n in predicted}
    actual_set = {int(n) for n in actual}
    hits = sorted(predicted_set & actual_set)
    expected = len(predicted_set) * len(actual_set) / total if total else 0.0
    return {
        "group": group_name,
        "predicted": sorted(predicted_set),
        "actual": sorted(actual_set),
        "hits": hits,
        "hit_count": len(hits),
        "expected": expected,
        "delta": len(hits) - expected,
        "misses": sorted(predicted_set - actual_set),
        "uncovered": sorted(actual_set - predicted_set),
    }


def build_review(lotid, prediction_store=None, history=None):
    prediction_store = prediction_store if prediction_store is not None else _load_json(PREDICTIONS_FILE, {})
    history = history if history is not None else _load_json(HISTORY_FILES[lotid], [])
    actual_by_period = {str(entry["period"]): entry for entry in history}
    records = prediction_store.get(lotid, {})

    rows = []
    summaries = defaultdict(lambda: {
        "count": 0,
        "hits": 0.0,
        "expected": 0.0,
        "better": 0,
        "equal": 0,
        "worse": 0,
        "best": None,
        "worst": None,
    })

    for period, record in sorted(records.items(), key=lambda item: _num_key(item[0]), reverse=True):
        actual_draw = actual_by_period.get(str(period))
        if not actual_draw:
            continue
        for area in record.get("areas", {}).values():
            field = area.get("field")
            if field not in actual_draw:
                continue
            actual = [int(n) for n in actual_draw[field]]
            total = int(area.get("total", max(actual) if actual else 0))
            groups = dict(area.get("predictions", {}))
            if area.get("recommendation"):
                groups["recommendation"] = area["recommendation"]

            for group_name, predicted in groups.items():
                cmp = _compare_group(group_name, predicted, actual, total)
                label = area.get("label", field)
                lower_is_better = group_name.startswith("kill_")
                delta = cmp["delta"]
                better = delta < -0.001 if lower_is_better else delta > 0.001
                worse = delta > 0.001 if lower_is_better else delta < -0.001
                key = (label, group_name)
                summary = summaries[key]
                summary["count"] += 1
                summary["hits"] += cmp["hit_count"]
                summary["expected"] += cmp["expected"]
                summary["better"] += 1 if better else 0
                summary["equal"] += 1 if not better and not worse else 0
                summary["worse"] += 1 if worse else 0
                best_value = -cmp["hit_count"] if lower_is_better else cmp["hit_count"]
                worst_value = cmp["hit_count"] if lower_is_better else -cmp["hit_count"]
                if summary["best"] is None or best_value > summary["best"][0]:
                    summary["best"] = (best_value, period, cmp["hit_count"], cmp["hits"])
                if summary["worst"] is None or worst_value > summary["worst"][0]:
                    summary["worst"] = (worst_value, period, cmp["hit_count"], cmp["hits"])

                rows.append({
                    "period": str(period),
                    "generated_at": record.get("generated_at", ""),
                    "area": label,
                    "group": group_name,
                    "actual": cmp["actual"],
                    "predicted": cmp["predicted"],
                    "hits": cmp["hits"],
                    "hit_count": cmp["hit_count"],
                    "expected": cmp["expected"],
                    "delta": cmp["delta"],
                    "misses": cmp["misses"],
                    "uncovered": cmp["uncovered"],
                })

    return {
        "lotid": lotid,
        "label": LOTTERY_LABELS.get(lotid, lotid),
        "rows": rows,
        "summaries": summaries,
    }


def _summary_table(review):
    rows = []
    for (area, group_name), summary in sorted(review["summaries"].items()):
        count = summary["count"]
        if count == 0:
            continue
        avg_hits = summary["hits"] / count
        avg_expected = summary["expected"] / count
        delta = avg_hits - avg_expected
        lower_is_better = group_name.startswith("kill_")
        cls = _baseline_class(delta, lower_is_better)
        best = summary["best"]
        worst = summary["worst"]
        rows.append(
            "<tr>"
            + _td("区域", area)
            + _td("类型", GROUP_LABELS.get(group_name, group_name))
            + _td("期数", count)
            + _td("平均撞号", f"{avg_hits:.2f}")
            + _td("随机基线", f"{avg_expected:.2f}")
            + _td("差值", f'<span class="{cls}">{delta:+.2f}</span>')
            + _td("优于随机", summary["better"])
            + _td("持平", summary["equal"])
            + _td("差于随机", summary["worse"])
            + _td("最好一期", f"{best[1]}期：{best[2]}个 {_fmt_nums(best[3])}" if best else "")
            + _td("最差一期", f"{worst[1]}期：{worst[2]}个 {_fmt_nums(worst[3])}" if worst else "")
            + "</tr>"
        )
    if not rows:
        return '<p class="meta">暂无可复盘数据。需要先运行预测并保存记录，且对应期号已经出现在历史开奖数据中。</p>'
    return f"""
<div class="table-wrap mobile-cards">
<table>
  <thead>
    <tr><th>区域</th><th>类型</th><th>期数</th><th>平均撞号</th><th>随机基线</th><th>差值</th><th>优于随机</th><th>持平</th><th>差于随机</th><th>最好一期</th><th>最差一期</th></tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>
"""


def _detail_table(review, limit=80):
    rows = []
    for row in review["rows"][:limit]:
        cls = _baseline_class(row["delta"], row["group"].startswith("kill_"))
        rows.append(
            "<tr>"
            + _td("期号", row["period"])
            + _td("区域", row["area"])
            + _td("类型", GROUP_LABELS.get(row["group"], row["group"]))
            + _td("实际开奖", _fmt_nums(row["actual"]))
            + _td("预测号码", _fmt_nums(row["predicted"]))
            + _td("撞号", f"{row['hit_count']} / {_fmt_nums(row['hits'])}")
            + _td("随机基线", f"{row['expected']:.2f}")
            + _td("差值", f'<span class="{cls}">{row["delta"]:+.2f}</span>')
            + _td("开奖未覆盖", _fmt_nums(row["uncovered"]))
            + "</tr>"
        )
    if not rows:
        return ""
    return f"""
<div class="table-wrap mobile-cards">
<table>
  <thead>
    <tr><th>期号</th><th>区域</th><th>类型</th><th>实际开奖</th><th>预测号码</th><th>撞号</th><th>随机基线</th><th>差值</th><th>开奖未覆盖</th></tr>
  </thead>
  <tbody>{''.join(rows)}</tbody>
</table>
</div>
<p class="meta">明细默认显示最近 {min(limit, len(review['rows']))} 条复盘记录。</p>
"""


def render_review_html(review):
    total_periods = len({row["period"] for row in review["rows"]})
    total_rows = len(review["rows"])
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{review['label']} 历史复盘</title>{_style()}</head>
<body>
<main>
  <h1>{review['label']} 历史复盘</h1>
  <p class="meta">生成时间: {generated}  |  数据来源: predictions_history.json + 开奖历史 JSON</p>
  <div class="summary">
    <div class="stat"><span class="val">{total_periods}</span><span class="lbl">已复盘期数</span></div>
    <div class="stat"><span class="val">{total_rows}</span><span class="lbl">分组记录</span></div>
    <div class="stat"><span class="val">随机</span><span class="lbl">基线: 预测数×开奖号数/号码池</span></div>
  </div>
  <section class="section">
    <h2>长期统计</h2>
    {_summary_table(review)}
  </section>
  <section class="section">
    <h2>最近明细</h2>
    {_detail_table(review)}
  </section>
  <p class="meta">说明：推荐组以高于随机基线为好；杀号组以低于随机基线为好，因为杀号的目标是少撞开奖号。</p>
</main>
</body>
</html>
"""


def write_review(lotid):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    review = build_review(lotid)
    fpath = os.path.join(REPORTS_DIR, f"review_{lotid}.html")
    with open(fpath, "w") as f:
        f.write(render_review_html(review))
    print(f"历史复盘报告已生成: {fpath}")
    return fpath


def main(argv):
    targets = argv[1:] or ["all"]
    if "all" in targets:
        targets = ["kl8", "dlt", "ssq"]
    for lotid in targets:
        if lotid not in LOTTERY_LABELS:
            raise SystemExit(f"未知彩种: {lotid}")
        write_review(lotid)


if __name__ == "__main__":
    main(sys.argv)
