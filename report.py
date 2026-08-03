import os
from datetime import datetime
from collections import Counter
from strategy import ALGORITHM_VERSION, choose_recommendation, strategy_detail, strategy_label

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def _compute_omission(data, field, total_n):
    omission = [len(data)] * total_n
    for idx, entry in enumerate(data):
        nums = {int(n) for n in entry[field]}
        for n in nums:
            if 1 <= n <= total_n and omission[n - 1] == len(data):
                omission[n - 1] = idx
    return omission


def _num_entries(data, field):
    return [sorted(int(n) for n in entry[field]) for entry in data]


def _style():
    return """
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #222; line-height: 1.45; }
        h1 { color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 8px; font-size: 26px; line-height: 1.25; }
        h2 { color: #16213e; margin-top: 28px; font-size: 21px; line-height: 1.3; }
        h3 { color: #24324a; margin: 18px 0 8px; font-size: 16px; line-height: 1.35; }
        .meta { color: #666; font-size: 14px; margin: 4px 0; }
        table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 4px 6px; text-align: center; }
        th { background: #16213e; color: #fff; position: sticky; top: 0; }
        tr:nth-child(even) { background: #f9f9f9; }
        .hit { background: #e94560 !important; color: #fff; font-weight: bold; }
        .hot-row { background: #fff3cd !important; }
        .cold-row { background: #d1ecf1 !important; }
        .bar { display: inline-block; height: 18px; margin-right: 4px; border-radius: 3px; }
        .bar-bg { background: #f0f0f0; border-radius: 3px; margin: 2px 0; }
        .tag { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; margin-left: 4px; font-weight: bold; }
        .tag-hot { background: #fff3cd; color: #856404; }
        .tag-cold { background: #d1ecf1; color: #0c5460; }
        .tag-a { background: #e2e3e5; color: #383d41; }
        .tag-b { background: #d4edda; color: #155724; }
        .tag-c { background: #cce5ff; color: #004085; }
        .group-box { background: #fff; border-radius: 8px; padding: 12px 16px; margin: 12px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .num { font-size: 15px; font-weight: bold; font-family: 'SF Mono', 'Courier New', monospace; padding: 2px 5px; margin: 1px; display: inline-block; }
        .nums { display: inline-flex; flex-wrap: wrap; gap: 2px 4px; align-items: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(36px, 1fr)); gap: 2px; margin: 8px 0; }
        .grid-cell { text-align: center; font-size: 12px; padding: 4px 0; border-radius: 3px; background: #fff; border: 1px solid #eee; }
        .grid-cell.on { background: #e94560; color: #fff; font-weight: bold; }
        .grid-cell.off { color: #ccc; }
        .summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
        .stat-card { background: #fff; border-radius: 6px; padding: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .stat-card .val { font-size: 22px; font-weight: bold; }
        .stat-card .lbl { font-size: 12px; color: #666; }
        .key-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 14px 0 18px; }
        .summary-card { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 11px 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .summary-card.primary { border-color: #16213e; grid-column: 1 / -1; }
        .summary-card .title { color: #16213e; font-size: 14px; font-weight: 700; margin-bottom: 6px; }
        .summary-card .line { color: #555; font-size: 12px; margin-top: 5px; }
        .data-status { display: block; margin: 8px 0 12px; border: 1px solid #ddd; border-left: 4px solid #155724; border-radius: 8px; background: #fff; padding: 8px 10px; color: #555; font-size: 12px; font-weight: 700; }
        .data-status.stale { border-left-color: #9f1239; }
        .data-status .state { color: #155724; font-weight: 900; }
        .data-status.stale .state { color: #9f1239; }
        .today-grid { display: grid; gap: 10px; margin: 10px 0 16px; }
        .today-card { background: #fff; border: 1px solid #d8dde6; border-radius: 8px; padding: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .today-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
        .today-title { color: #16213e; font-size: 15px; font-weight: 900; }
        .today-badge { background: #16213e; color: #fff; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 800; white-space: nowrap; }
        .today-rec { margin: 6px 0 8px; }
        .today-rec .num { font-size: 16px; padding: 2px 5px; }
        .today-lines { display: grid; gap: 6px; margin-top: 8px; }
        .today-line { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 8px; align-items: start; color: #555; font-size: 12px; }
        .today-line b { color: #16213e; }
        .source-details { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 9px 10px; margin: 8px 0 12px; }
        .source-details summary { color: #16213e; cursor: pointer; font-size: 14px; font-weight: 800; }
        .tier-box { display: grid; gap: 7px; margin-top: 6px; }
        .tier-line { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 8px; align-items: start; }
        .tier-label { color: #16213e; font-size: 12px; font-weight: 800; line-height: 1.5; }
        .reason-list { display: grid; gap: 5px; margin-top: 8px; }
        .reason-row { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 7px; align-items: start; color: #555; font-size: 12px; }
        .reason-row .num { margin: 0; padding: 1px 4px; }
        .source-grid { display: grid; gap: 7px; }
        .source-row { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 8px 9px; }
        .source-head { display: flex; justify-content: space-between; gap: 8px; color: #16213e; font-size: 13px; font-weight: 800; margin-bottom: 4px; }
        .source-note { color: #666; font-size: 12px; margin-top: 4px; }
        .review-card { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 11px 12px; margin: 10px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .review-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 8px; }
        .review-title { color: #16213e; font-size: 15px; font-weight: 800; }
        .review-score { color: #fff; background: #e94560; border-radius: 999px; padding: 2px 8px; font-size: 13px; font-weight: 800; white-space: nowrap; }
        .review-lines { display: grid; gap: 7px; }
        .review-line { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; align-items: start; }
        .review-line b { color: #16213e; font-size: 12px; line-height: 1.6; }
        .review-details { margin-top: 8px; }
        .review-details summary { color: #666; font-size: 12px; font-weight: 700; cursor: pointer; }
        .expert-block { margin: 14px 0; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; background: #fff; }
        .expert-block summary { color: #16213e; font-size: 16px; font-weight: 800; cursor: pointer; }
        .expert-note { color: #666; font-size: 12px; margin: 7px 0 10px; }
        .expert-overlap { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; margin: 8px 0 10px; }
        .expert-overlap-card { border: 1px solid #eee; border-radius: 8px; padding: 8px; background: #fafafa; }
        .expert-overlap-card .title { color: #16213e; font-size: 13px; font-weight: 800; margin-bottom: 4px; }
        .trend-wrap { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 8px 0 6px; border: 1px solid #d8dde6; border-radius: 8px; background: #fff; }
        .trend-table { border-collapse: separate; border-spacing: 0; table-layout: fixed; width: max-content; min-width: 100%; margin: 0; font-size: 12px; }
        .trend-table th, .trend-table td { border: 0; border-right: 1px solid #edf0f5; border-bottom: 1px solid #edf0f5; padding: 0; text-align: center; }
        .trend-table tr:last-child th, .trend-table tr:last-child td { border-bottom: 0; }
        .trend-label { position: sticky; left: 0; z-index: 3; width: 82px; min-width: 82px; max-width: 82px; padding: 5px 6px !important; text-align: left !important; background: #fff; color: #16213e; font-weight: 800; line-height: 1.2; }
        .trend-head { background: #16213e !important; color: #fff !important; }
        .trend-num { width: 26px; min-width: 26px; max-width: 26px; height: 24px; background: #16213e; color: #fff; font-size: 11px; font-weight: 700; position: static; }
        .trend-cell { width: 26px; min-width: 26px; max-width: 26px; height: 26px; background: #fff; color: #c3cad5; font-family: 'SF Mono', 'Courier New', monospace; font-size: 11px; font-weight: 800; }
        .trend-cell span { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; }
        .trend-empty { background: #fbfcfe; color: #c3cad5; font-weight: 600; }
        .trend-empty span { border-radius: 0; }
        .trend-on { color: #fff; }
        .trend-draw span { background: #e94560; }
        .trend-hot span { background: #f2a900; color: #1f2933; }
        .trend-cold span { background: #00a6a6; }
        .trend-kill-a span { background: #7d8597; }
        .trend-kill-b span { background: #5a8f29; }
        .trend-kill-c span { background: #2f80ed; }
        .trend-rec span { background: #111827; box-shadow: inset 0 0 0 2px #fff; }
        .trend-manual-cell { cursor: pointer; touch-action: manipulation; }
        .trend-manual-cell span { border: 1px dashed #d4dae5; }
        .trend-manual-cell.manual-on { color: #fff; }
        .trend-manual-cell.manual-on span { background: #7c3aed; border-color: #7c3aed; border-radius: 50%; box-shadow: inset 0 0 0 2px #fff; }
        .trend-section th { position: sticky; left: 0; z-index: 4; background: #f0f3f8; color: #16213e; text-align: left; padding: 5px 7px; font-size: 12px; border-right: 0; }
        .trend-legend { display: flex; flex-wrap: wrap; gap: 6px 10px; margin: 7px 0 2px; color: #555; font-size: 12px; }
        .trend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
        .trend-dot.draw { background: #e94560; }
        .trend-dot.pred { background: #111827; }
        .trend-dot.manual { background: #7c3aed; }
        .trend-dot.kill { background: #7d8597; }
        .matrix { font-size: 12px; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; padding-bottom: 4px; }
        .matrix td { padding: 2px 4px; min-width: 22px; }
        .matrix .period-col { text-align: left; font-weight: bold; padding-right: 8px; min-width: 70px; }
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%; }
        .wide-table { min-width: 820px; }
        .stack-table td .meta { display: inline; }
        @media (max-width: 768px) {
            body { padding: 10px; max-width: 100%; }
            h1 { font-size: 20px; }
            h2 { font-size: 16px; margin-top: 20px; }
            h3 { font-size: 15px; }
            table { font-size: 11px; }
            th, td { padding: 3px 4px; }
            .num { font-size: 13px; padding: 1px 3px; }
            .group-box { padding: 8px 10px; }
            .summary-grid { grid-template-columns: repeat(2, 1fr); gap: 4px; }
            .key-summary { grid-template-columns: 1fr; gap: 8px; margin: 10px 0 14px; }
            .summary-card { padding: 9px 10px; }
            .stat-card { padding: 4px; }
            .stat-card .val { font-size: 16px; }
            .grid-cell { font-size: 10px; padding: 3px 0; }
            .grid { grid-template-columns: repeat(auto-fill, minmax(28px, 1fr)); gap: 1px; }
        }
        @media (max-width: 640px) {
            .mobile-cards { overflow: visible; }
            .mobile-cards .wide-table { min-width: 0; }
            .mobile-cards table,
            .mobile-cards thead,
            .mobile-cards tbody,
            .mobile-cards tr,
            .mobile-cards th,
            .mobile-cards td { display: block; width: 100%; }
            .mobile-cards thead { display: none; }
            .mobile-cards table { margin: 8px 0; border-collapse: separate; border-spacing: 0; }
            .mobile-cards tr { background: #fff; border: 1px solid #ddd; border-radius: 8px; margin: 8px 0; padding: 6px 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
            .mobile-cards tr:nth-child(even) { background: #fff; }
            .mobile-cards td { border: 0; border-bottom: 1px solid #eee; display: grid; grid-template-columns: minmax(82px, 32%) minmax(0, 1fr); gap: 8px; align-items: start; text-align: left; padding: 7px 0; }
            .mobile-cards td:last-child { border-bottom: 0; }
            .mobile-cards td::before { content: attr(data-label); color: #666; font-weight: 600; font-size: 12px; line-height: 1.45; }
            .mobile-cards td[data-label="期号"],
            .mobile-cards td[data-label="类型"] { font-size: 14px; font-weight: 700; color: #16213e; }
            .mobile-cards td[data-label="期号"]::before,
            .mobile-cards td[data-label="类型"]::before { color: #16213e; }
            .mobile-cards .num { margin-bottom: 3px; }
            .nums { gap: 1px 3px; }
            .trend-label { width: 68px; min-width: 68px; max-width: 68px; padding: 4px 4px !important; font-size: 10px; }
            .trend-num, .trend-cell { width: 21px; min-width: 21px; max-width: 21px; }
            .trend-num { height: 21px; font-size: 9px; }
            .trend-cell { height: 22px; font-size: 9px; }
            .trend-cell span { width: 18px; height: 18px; }
        }
        @media (max-width: 480px) {
            .summary-grid { grid-template-columns: 1fr; }
            .meta { font-size: 12px; }
            .grid { grid-template-columns: repeat(auto-fill, minmax(22px, 1fr)); }
            .grid-cell { font-size: 9px; padding: 2px 0; }
            .bar { height: 14px; }
            body { padding: 8px; }
            .group-box { border-radius: 6px; margin: 8px 0; }
            .trend-label { width: 64px; min-width: 64px; max-width: 64px; }
            .trend-num, .trend-cell { width: 20px; min-width: 20px; max-width: 20px; }
            .trend-cell span { width: 17px; height: 17px; }
        }
    </style>
    <script>
    (function() {
        function readSet(key) {
            try {
                return new Set(JSON.parse(localStorage.getItem(key) || "[]"));
            } catch (e) {
                return new Set();
            }
        }

        function writeSet(key, selected) {
            try {
                localStorage.setItem(key, JSON.stringify(Array.from(selected).sort()));
            } catch (e) {}
        }

        function setCell(cell, on) {
            cell.classList.toggle("manual-on", on);
            cell.setAttribute("aria-pressed", on ? "true" : "false");
        }

        function updateCount(table, selected) {
            var target = table.querySelector("[data-manual-count]");
            if (target) {
                target.textContent = selected.size + "个";
            }
        }

        document.addEventListener("DOMContentLoaded", function() {
            document.querySelectorAll(".trend-table[data-manual-key]").forEach(function(table) {
                var key = "lottery-manual:" + location.pathname + ":" + table.dataset.manualKey;
                var selected = readSet(key);
                table.querySelectorAll("[data-manual-cell]").forEach(function(cell) {
                    var n = cell.dataset.number;
                    setCell(cell, selected.has(n));
                    cell.addEventListener("click", function() {
                        if (selected.has(n)) {
                            selected.delete(n);
                        } else {
                            selected.add(n);
                        }
                        setCell(cell, selected.has(n));
                        updateCount(table, selected);
                        writeSet(key, selected);
                    });
                    cell.addEventListener("keydown", function(event) {
                        if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            cell.click();
                        }
                    });
                });
                updateCount(table, selected);
            });
        });
    })();
    </script>
    """


def _history_matrix(data, field, total_n, periods=10):
    entries = _num_entries(data, field)[:periods]
    rows = []
    for ei, nums in enumerate(entries):
        cells = []
        for n in range(1, total_n + 1):
            cls = "on" if n in nums else "off"
            cells.append(f'<span class="grid-cell {cls}">{n:02d}</span>')
        period = data[ei]["period"]
        rows.append(f'<div style="margin:3px 0"><b>{period}</b>{" ".join(cells)}</div>')
    return "\n".join(rows)


def _omission_table(data, field, total_n, counter, top_n=15):
    omission = _compute_omission(data, field, total_n)
    rows = []
    for n in range(1, total_n + 1):
        cnt = counter.get(n, 0)
        rows.append((omission[n - 1], n, cnt))
    rows.sort(key=lambda x: -x[0])
    lines = []
    for omit, n, cnt in rows[:top_n]:
        bar_pct = min(omit / max(r[0] for r in rows[:top_n]) * 100, 100) if rows else 0
        lines.append(
            f"<tr><td>{n:02d}</td><td>{omit}</td><td>{cnt}</td>"
            f'<td><div class="bar-bg"><div class="bar" style="width:{bar_pct:.0f}%;background:#e94560"></div></div></td></tr>'
        )
    return f"""
    <table>
        <tr><th>号码</th><th>遗漏(期)</th><th>采样频次</th><th>分布</th></tr>
        {''.join(lines)}
    </table>
    """


def _freq_chart(counter, total_n, top_n=15):
    items = counter.most_common(top_n)
    max_cnt = max(c for _, c in items) or 1
    lines = []
    for n, cnt in items:
        pct = cnt / max_cnt * 100
        lines.append(
            f'<tr><td style="font-weight:bold">{n:02d}</td>'
            f'<td style="width:60%"><div class="bar-bg"><div class="bar" style="width:{pct:.0f}%;background:#16213e"></div></div></td>'
            f'<td>{cnt}次</td></tr>'
        )
    return f"""
    <table>
        <tr><th>号码</th><th>频次分布</th><th>次数</th></tr>
        {''.join(lines)}
    </table>
    """


def _source_label(name):
    return {
        "hot": "热门候选",
        "cold": "冷门观察",
        "kill_a": "中间候选A",
        "kill_b": "中间候选B",
        "kill_c": "中间候选C",
    }.get(name, name)


def _source_note(name):
    return {
        "hot": "采样频次最高，是最终主推的主要来源。",
        "cold": "采样中出现过但频次偏低，只作为补充观察。",
        "kill_a": "从中间区间随机抽取，用于增加覆盖，不参与主推排序。",
        "kill_b": "中间区间里频次较高的候选，不参与主推排序。",
        "kill_c": "中间区间按号码轴等距覆盖，不参与主推排序。",
    }.get(name, "来源参考。")


def _number_reasons(n, predictions, counter):
    tags = []
    max_cnt = max(counter.values(), default=0)
    cnt = counter.get(int(n), 0)
    if max_cnt:
        tags.append(f"采样{cnt}/{max_cnt}")
    for key in ("hot", "cold", "kill_a", "kill_b", "kill_c"):
        if int(n) in {int(x) for x in predictions.get(key, [])}:
            tags.append(_source_label(key))
    return " / ".join(tags) if tags else "候选补位"


def _source_explanation_section(predictions, counter):
    rows = []
    for name in ("hot", "cold", "kill_a", "kill_b", "kill_c"):
        nums = [int(n) for n in predictions.get(name, [])]
        if not nums:
            continue
        rows.append(f"""
<div class="source-row">
  <div class="source-head"><span>{_source_label(name)}</span><span>{len(nums)}个</span></div>
  <div>{_fmt_nums(nums)}</div>
  <div class="source-note">{_source_note(name)}</div>
</div>
""")
    return f'<div class="source-grid">{"".join(rows)}</div>'


def _predictions_table(predictions, counters, actual_set):
    return f"""
<details class="source-details">
  <summary>推荐来源参考（默认折叠）</summary>
  <p class="source-note">这里只解释五组候选来源；最终主推会按当前彩种策略从综合模型、近期高频或当前遗漏中选择。</p>
  {_source_explanation_section(predictions, Counter())}
</details>
"""


def _comparison_cell(predicted, actual_set):
    hits = sorted(set(int(n) for n in predicted) & actual_set)
    return f"{len(hits)} / {_fmt_nums(hits)}"


def _compare_item(label, nums, actual_set):
    hits = sorted(set(int(n) for n in nums) & actual_set)
    return f"""
<div class="compare-item">
  <div class="compare-item-top"><span class="compare-name">{label}重号</span><span class="compare-count">{len(hits)}</span></div>
  <div>{_fmt_nums(hits)}</div>
</div>
"""


def _td(label, value, style=""):
    style_attr = f' style="{style}"' if style else ""
    return f'<td data-label="{label}"{style_attr}>{value}</td>'


def _data_status_section(status):
    if not status:
        return ""
    age = status.get("age_hours")
    age_text = f"{age:.1f}小时前" if isinstance(age, (int, float)) else "未知"
    cls = "" if status.get("fresh") else "stale"
    last_draw = status.get("last_draw_time") or "未知"
    return f"""
<div class="data-status {cls}">
  数据：<span class="state">{status.get('state', '未知')}</span>
  · 最新 {status.get('latest_period', '')}期
  · 缓存 {age_text}
  · 最近开奖 {last_draw}
</div>
"""


def _trend_total_n(data, field, predictions, total_n=None):
    if total_n:
        return total_n
    nums = []
    for entry in data:
        nums.extend(int(n) for n in entry.get(field, []))
    for group_nums in predictions.values():
        nums.extend(int(n) for n in group_nums)
    return max(nums) if nums else 0


def _trend_cell(n, selected, css_class):
    if selected:
        return f'<td class="trend-cell trend-on {css_class}"><span>{n:02d}</span></td>'
    return f'<td class="trend-cell trend-empty"><span>{n:02d}</span></td>'


def _trend_row(label, nums, total_n, css_class, label_note=""):
    selected = {int(n) for n in nums}
    note_html = f'<br><span class="meta">{label_note}</span>' if label_note else ""
    cells = "".join(_trend_cell(n, n in selected, css_class) for n in range(1, total_n + 1))
    return f'<tr><th class="trend-label">{label}{note_html}</th>{cells}</tr>'


def _manual_trend_row(total_n):
    cells = "".join(
        f'<td class="trend-cell trend-empty trend-manual-cell" data-manual-cell data-number="{n:02d}" role="button" tabindex="0" aria-pressed="false"><span>{n:02d}</span></td>'
        for n in range(1, total_n + 1)
    )
    return f'<tr><th class="trend-label">自选号码<br><span class="meta" data-manual-count>0个</span></th>{cells}</tr>'


def _prediction_history_comparison(data, field, predictions, counter, pick, periods=10, total_n=None, lotid=None, cfg=None):
    total_n = _trend_total_n(data, field, predictions, total_n)
    if not total_n:
        return '<p class="meta">暂无可对比号码。</p>'

    cfg = cfg or {"pick": pick, "total": total_n}
    rec, strategy = choose_recommendation(
        lotid, field, predictions, counter, cfg, history=data, use_saved_selection=True
    )

    header = "".join(f'<th class="trend-num">{n:02d}</th>' for n in range(1, total_n + 1))
    draw_rows = []
    rec_set = set(rec)
    for entry in reversed(data[:periods]):
        actual = sorted(int(n) for n in entry[field])
        hits = len(set(actual) & rec_set)
        draw_rows.append(_trend_row(str(entry["period"]), actual, total_n, "trend-draw", f"主推中{hits}"))

    prediction_rows = [_trend_row(strategy_label(strategy), rec, total_n, "trend-rec")]

    return f"""
<div class="trend-legend">
  <span><i class="trend-dot draw"></i>期开奖</span>
  <span><i class="trend-dot pred"></i>{strategy_label(strategy)}</span>
  <span><i class="trend-dot manual"></i>自选号码</span>
</div>
<div class="trend-wrap" aria-label="预测号码和历史开奖号码号码轴对比">
<table class="trend-table" data-manual-key="{field}-{total_n}">
  <thead>
    <tr><th class="trend-label trend-head">期号/号码</th>{header}</tr>
  </thead>
  <tbody>
    <tr class="trend-section"><th colspan="{total_n + 1}">最近 {min(periods, len(data))} 期开奖</th></tr>
    {''.join(draw_rows)}
    <tr class="trend-section"><th colspan="{total_n + 1}">本期{strategy_label(strategy)}</th></tr>
    {''.join(prediction_rows)}
    <tr class="trend-section"><th colspan="{total_n + 1}">手动选择</th></tr>
    {_manual_trend_row(total_n)}
  </tbody>
</table>
</div>
<p class="meta">同一列代表同一个号码；开奖行左侧“主推中N”表示当前策略推荐与该期开奖号重合数量。自选号码保存在当前浏览器。</p>
"""


def _ranked_numbers(counter, total_n=None):
    if not counter:
        return []
    items = []
    for n, cnt in counter.items():
        ni = int(n)
        if cnt > 0 and (total_n is None or 1 <= ni <= total_n):
            items.append((ni, cnt))
    return [n for n, _ in sorted(items, key=lambda item: (-item[1], item[0]))]


def _recommendation(all_preds, counter, pick):
    ranked = _ranked_numbers(counter)
    top = ranked[:pick]
    if len(top) < pick:
        fallback = []
        for name in ("hot", "cold"):
            fallback.extend(int(n) for n in all_preds.get(name, []))
        if len(top) + len(set(fallback) - set(top)) < pick:
            for nums in all_preds.values():
                fallback.extend(int(n) for n in nums)
        for n in fallback:
            if n not in top:
                top.append(n)
            if len(top) >= pick:
                break
    top.sort()
    return top


def _recommendation_tiers(predictions, counter, pick, total_n, rec=None):
    ranked = _ranked_numbers(counter, total_n)
    rec = sorted(int(n) for n in rec) if rec is not None else _recommendation(predictions, counter, pick)
    rec_set = set(rec)
    rec_ranked = [n for n in ranked if n in rec_set]
    for n in rec:
        if n not in rec_ranked:
            rec_ranked.append(n)

    core_count = max(1, min(len(rec_ranked), (pick + 1) // 2))
    core = sorted(rec_ranked[:core_count])
    backup = sorted(rec_ranked[core_count:pick])
    watch_count = min(max(2, pick // 2), max(0, total_n - pick))
    watch = sorted([n for n in ranked if n not in rec_set][:watch_count])
    return {"core": core, "backup": backup, "watch": watch}


def _best_recent_match(data, field, predicted, periods=10):
    pred_set = {int(n) for n in predicted}
    best = None
    for entry in data[:periods]:
        actual = sorted(int(n) for n in entry[field])
        hits = sorted(pred_set & set(actual))
        item = {
            "period": entry["period"],
            "hit_count": len(hits),
            "hits": hits,
            "actual": actual,
        }
        if best is None or item["hit_count"] > best["hit_count"]:
            best = item
    return best


def _top_omissions(data, field, total_n, limit=5):
    omission = _compute_omission(data, field, total_n)
    ranked = sorted(enumerate(omission, 1), key=lambda item: (-item[1], item[0]))
    return ranked[:limit]


def _evaluation_lookup(evaluation):
    result = {}
    if not evaluation:
        return result
    for area in evaluation.get("areas", []):
        rec = next((c for c in area.get("comparisons", []) if c.get("name") == "recommendation"), None)
        if rec:
            result[area.get("field")] = rec
    return result


def _key_summary_section(data, areas, evaluation=None, lotid=None):
    eval_by_field = _evaluation_lookup(evaluation)
    cards = []
    for label, field, predictions, counter, cfg in areas:
        pick = cfg["pick"]
        total_n = cfg["total"]
        rec, strategy = choose_recommendation(
            lotid, field, predictions, counter, cfg, history=data, use_saved_selection=True
        )
        detail = strategy_detail(lotid, field)
        tiers = _recommendation_tiers(predictions, counter, pick, total_n, rec)
        best = _best_recent_match(data, field, rec, 10)
        omissions = _top_omissions(data, field, total_n, min(5, total_n))
        omit_text = " ".join(f"{n:02d}<span class=\"meta\">({o})</span>" for n, o in omissions)
        rec_eval = eval_by_field.get(field)
        if rec_eval:
            predicted_count = len(rec_eval.get("predicted", [])) or pick
            review_html = f"中 {len(rec_eval['hits'])}/{predicted_count}: {_fmt_nums(rec_eval['hits'])}"
            review_miss = f"漏掉: {_fmt_nums(rec_eval['uncovered'])}"
        else:
            review_html = "暂无上期开奖复盘"
            review_miss = "本次运行后会保存预测，下一期开奖后自动对比"
        best_html = f"{best['period']}期，重号 {best['hit_count']} 个: {_fmt_nums(best['hits'])}" if best else "暂无"
        cards.append(f"""
<div class="today-card">
  <div class="today-head">
    <div class="today-title">{label}{strategy_label(strategy)}</div>
    <div class="today-badge">{pick}/{total_n}</div>
  </div>
  <div class="today-rec">{_fmt_nums(rec)}</div>
  <div class="today-lines">
    <div class="today-line"><b>上期</b><span>{review_html}<br><span class="meta">{review_miss}</span></span></div>
    <div class="today-line"><b>策略</b><span>{strategy_label(strategy)}，{detail.get('selection_source', '默认策略')}，信心：{detail.get('confidence', '未开始动态选择')}</span></div>
    <div class="today-line"><b>分层</b><span>核心 {_fmt_nums(tiers["core"])}<br>备选 {_fmt_nums(tiers["backup"])}</span></div>
    <div class="today-line"><b>结构</b><span>和值 {sum(rec)}，奇偶 {sum(1 for n in rec if n % 2 == 1)}:{pick - sum(1 for n in rec if n % 2 == 1)}</span></div>
    <div class="today-line"><b>相似</b><span>{best_html}</span></div>
    <div class="today-line"><b>遗漏</b><span>{omit_text}</span></div>
  </div>
</div>
""")
        if rec_eval:
            continue

    return f"""
<h2>今日结论</h2>
<div class="today-grid">
{''.join(cards)}
</div>
"""


def _remaining_section(predictions, counter, total_n):
    pred_all = set()
    for name in predictions:
        pred_all.update(int(n) for n in predictions[name])

    all_nums = set(range(1, total_n + 1))
    remain = sorted(all_nums - pred_all)

    if remain:
        nums = " ".join(f'<span class="num">{n:02d}</span>' for n in remain)
        return f'<p style="font-size:16px">{nums}</p><p class="meta">共 {len(remain)}/{total_n} 个号码未被覆盖</p>'

    threshold = 1
    cold = sorted(n for n in all_nums if counter.get(n, 0) <= threshold)
    if not cold:
        threshold = 2
        cold = sorted(n for n, _ in counter.most_common() if counter[n] <= threshold)
    if cold:
        nums = " ".join(f'<span class="num">{n:02d}</span>' for n in cold)
        return f'<p style="font-size:16px">{nums}</p><p class="meta">已覆盖全部号码，以上为采样频次 ≤{threshold} 的最冷号</p>'

    return '<p class="meta">无可推荐号码</p>'


def _expert_remaining_section(expert_data, total_n, field):
    all_nums = set(range(1, total_n + 1))
    expert_nums = set()
    expert_counter = Counter()

    if expert_data:
        for _, _, ed_all_picks in expert_data:
            ek = "front" if field in ("front", "numbers") else "back"
            picks = ed_all_picks.get(ek, [])
            expert_nums.update(picks)
            expert_counter.update(picks)

    remain = sorted(all_nums - expert_nums)

    if remain:
        nums = " ".join(f'<span class="num">{n:02d}</span>' for n in remain)
        return f'<p style="font-size:16px">{nums}</p><p class="meta">共 {len(remain)}/{total_n} 个号码未被专家覆盖</p>'

    min_cnt = min(expert_counter.get(n, 0) for n in all_nums) if expert_counter else 0
    cold = sorted(n for n in all_nums if expert_counter.get(n, 0) == min_cnt)
    if cold:
        nums = " ".join(f'<span class="num">{n:02d}</span>' for n in cold)
        return f'<p style="font-size:16px">{nums}</p><p class="meta">已覆盖全部号码，以上为专家提及最少（{min_cnt}次）的号码</p>'

    return ""


def _omission_bar(data, field, total_n):
    omission = _compute_omission(data, field, total_n)
    items = sorted(enumerate(omission, 1), key=lambda x: -x[1])[:10]
    lines = []
    max_o = max(o for _, o in items) or 1
    for n, o in items:
        pct = o / max_o * 100
        lines.append(
            f'<tr><td style="font-weight:bold">{n:02d}</td>'
            f'<td>{o}期</td>'
            f'<td style="width:60%"><div class="bar-bg"><div class="bar" style="width:{pct:.0f}%;background:#e94560"></div></div></td></tr>'
        )
    return f"""
    <table>
        <tr><th>号码</th><th>遗漏</th><th>分布</th></tr>
        {''.join(lines)}
    </table>
    """


def _expert_section_html(experts, all_picks, labels, recommendations=None):
    if not experts:
        return ""
    from collections import Counter

    recommendations = recommendations or {}
    fc = Counter(all_picks["front"])
    bc = Counter(all_picks["back"])
    label_f, label_b = labels

    rows = []
    for e in experts:
        picks_str = []
        for k in sorted(e["picks"].keys()):
            p = e["picks"][k]
            picks_str.append(f"{k}: {' '.join(f'{n:02d}' for n in p['front'])} + {' '.join(f'{n:02d}' for n in p['back'])}")
        rows.append(f'<tr><td style="font-weight:bold">{e["name"]}</td><td style="text-align:left;font-size:13px">{"<br>".join(picks_str)}</td></tr>')

    expert_table = f"""
    <table>
        <tr><th style="width:80px">专家</th><th>推荐号码</th></tr>
        {''.join(rows)}
    </table>
    """

    cons_f = fc.most_common(10)
    cons_b = bc.most_common(6)
    cons_f_nums = [n for n, _ in cons_f]
    cons_b_nums = [n for n, _ in cons_b]
    max_fc = max((c for _, c in cons_f), default=1)
    max_bc = max((c for _, c in cons_b), default=1)

    overlap_blocks = []
    front_rec = recommendations.get("front") or recommendations.get("numbers") or []
    if cons_f_nums and front_rec:
        overlap = sorted(set(cons_f_nums) & {int(n) for n in front_rec})
        overlap_blocks.append(f"""
<div class="expert-overlap-card">
  <div class="title">{label_f}专家共识 vs 综合推荐</div>
  <div>重合 {len(overlap)} 个: {_fmt_nums(overlap)}</div>
  <div class="meta">仅作为外部参考，未参与综合推荐排序。</div>
</div>
""")
    back_rec = recommendations.get("back") or []
    if cons_b_nums and back_rec:
        overlap = sorted(set(cons_b_nums) & {int(n) for n in back_rec})
        overlap_blocks.append(f"""
<div class="expert-overlap-card">
  <div class="title">{label_b}专家共识 vs 综合推荐</div>
  <div>重合 {len(overlap)} 个: {_fmt_nums(overlap)}</div>
  <div class="meta">仅作为外部参考，未参与综合推荐排序。</div>
</div>
""")

    cons_rows = []
    for n, cnt in cons_f:
        pct = cnt / max_fc * 100
        cons_rows.append(f'<tr><td style="font-weight:bold">{n:02d}</td><td>{cnt}次</td><td style="width:60%"><div class="bar-bg"><div class="bar" style="width:{pct:.0f}%;background:#16213e"></div></div></td></tr>')
    if cons_rows:
        cons_rows.append(f'<tr><td colspan="3" style="background:#eee;font-weight:bold;text-align:left;padding:6px 8px">{label_b}</td></tr>')
    for n, cnt in cons_b:
        pct = cnt / max_bc * 100
        cons_rows.append(f'<tr><td style="font-weight:bold">{n:02d}</td><td>{cnt}次</td><td style="width:60%"><div class="bar-bg"><div class="bar" style="width:{pct:.0f}%;background:#e94560"></div></div></td></tr>')

    consensus_table = f"""
    <table>
        <tr><th>号码</th><th>推荐次数</th><th>分布</th></tr>
        {''.join(cons_rows)}
    </table>
    """

    return f"""
    <details class="expert-block">
      <summary>专家外部参考（{len(experts)} 位，默认折叠）</summary>
      <p class="expert-note">专家内容不参与综合推荐，仅用于观察外部共识和主推号码是否重合；后续复盘会单独评估专家共识是否强于随机。</p>
      <div class="expert-overlap">{''.join(overlap_blocks) or '<p class="meta">暂无可计算的专家共识重合。</p>'}</div>
      <h3>专家共识（{label_f} Top 10 + {label_b} Top 6）</h3>
      {consensus_table}
      <h3>专家原始推荐</h3>
      {expert_table}
    </details>
    """


GROUP_LABELS = {
    "hot": "热门",
    "cold": "冷门",
    "kill_a": "中间候选A(随机)",
    "kill_b": "中间候选B(高频)",
    "kill_c": "中间候选C(等距)",
    "recommendation": "最终主推",
    "expert_consensus": "专家共识",
}


def _fmt_nums(nums):
    if not nums:
        return '<span class="meta">无</span>'
    return '<span class="nums">' + "".join(f'<span class="num">{int(n):02d}</span>' for n in nums) + '</span>'


def _evaluation_section_html(evaluation):
    if not evaluation:
        return """
<hr>
<h2>🧾 上期预测复盘</h2>
<p class="meta">没有找到本期对应的历史预测记录；从本次运行开始会保存预测，下一期开奖后可自动复盘。</p>
"""

    html = f"""
<hr>
<h2>🧾 上期预测复盘</h2>
<p class="meta">复盘期号: {evaluation['period']}期  |  预测生成: {evaluation.get('generated_at') or '未知'}  |  seed: {evaluation.get('seed')}</p>
"""
    for area in evaluation.get("areas", []):
        actual = area["actual"]
        rec = next((comp for comp in area["comparisons"] if comp.get("name") == "recommendation"), None)
        if rec:
            hit_count = len(rec["hits"])
            predicted_count = len(rec["predicted"])
            html += f"""
<div class="review-card">
  <div class="review-head">
    <div class="review-title">{area['label']}最终主推复盘</div>
    <div class="review-score">中 {hit_count}/{predicted_count}</div>
  </div>
  <div class="review-lines">
    <div class="review-line"><b>开奖</b><span>{_fmt_nums(actual)}</span></div>
    <div class="review-line"><b>上期预测</b><span>{_fmt_nums(rec['predicted'])}</span></div>
    <div class="review-line"><b>命中</b><span>{_fmt_nums(rec['hits'])}</span></div>
    <div class="review-line"><b>未中</b><span>{_fmt_nums(rec['misses'])}</span></div>
    <div class="review-line"><b>漏掉</b><span>{_fmt_nums(rec['uncovered'])}</span></div>
  </div>
</div>
"""
        rows = []
        for comp in area["comparisons"]:
            rows.append(
                f"<tr>"
                f"{_td('类型', GROUP_LABELS.get(comp['name'], comp['name']), 'font-weight:bold')}"
                f"{_td('预测号码', _fmt_nums(comp['predicted']))}"
                f"{_td('中几个', len(comp['hits']))}"
                f"{_td('命中', _fmt_nums(comp['hits']))}"
                f"{_td('预测未中', _fmt_nums(comp['misses']))}"
                f"{_td('开奖未覆盖', _fmt_nums(comp['uncovered']))}"
                f"</tr>"
            )
        html += f"""
<details class="review-details">
<summary>{area['label']}来源组明细</summary>
<div class="table-wrap mobile-cards">
<table class="wide-table stack-table">
    <thead>
        <tr><th>类型</th><th>预测号码</th><th>中几个</th><th>命中</th><th>预测未中</th><th>开奖未覆盖</th></tr>
    </thead>
    <tbody>
        {''.join(rows)}
    </tbody>
</table>
</div>
</details>
"""
    return html


def generate_report(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field="numbers", label="", overlay_hits=None, data_status=None):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    total_n = cfg["total"]
    pick = cfg["pick"]
    lot_name = {"kl8": "快乐8", "dlt": "大乐透", "ssq": "双色球"}.get(lotid, lotid)
    actual_set = {int(n) for n in latest_draw[field]} if field in latest_draw else set()
    area_suffix = f"_{label}" if label else ""

    html = _build_html(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field, label, data_status)
    fname = f"{lotid}_{next_period}{area_suffix}.html"
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, "w") as f:
        f.write(html)
    print(f"\n📄 报告已生成: {fpath}")
    return fpath


def generate_combined_report(data, latest_draw, areas, lotid, next_period, seed, expert_data=None, evaluation=None, data_status=None):
    """areas: [(label, field, predictions, counter, cfg), ...]
       expert_data: [(label, experts, all_picks), ...] or None
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    lot_name = {"kl8": "快乐8", "dlt": "大乐透", "ssq": "双色球"}.get(lotid, lotid)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{lot_name} {next_period}期 预测报告</title>{_style()}</head>
<body>
<h1>🎯 {lot_name} {next_period}期 预测报告</h1>
<p class="meta">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  seed: {seed}  |  算法: {ALGORITHM_VERSION}</p>
<p class="meta">数据: {len(data)} 期历史  |  最新开奖: {latest_draw['period']}期</p>
{_data_status_section(data_status)}
"""

    html += _key_summary_section(data, areas, evaluation, lotid)
    html += _evaluation_section_html(evaluation)

    for label, field, predictions, counter, cfg in areas:
        total_n = cfg["total"]
        pick = cfg["pick"]
        actual_set = {int(n) for n in latest_draw[field]} if field in latest_draw else set()

        html += f"""
<hr>
<h2>📌 {label}（{pick}/{total_n}）</h2>
<p class="meta">总采样: {sum(counter.values())} 次</p>

<h3>🔎 本期预测 vs 最近10期开奖</h3>
{_prediction_history_comparison(data, field, predictions, counter, pick, 10, total_n, lotid, cfg)}

<h3>📊 最近10期走势</h3>
<div class="matrix">{_history_matrix(data, field, total_n, 10)}</div>

<div style="display:flex;gap:16px;flex-wrap:wrap">
<div style="flex:1;min-width:280px">
<h3>🔴 遗漏 Top 10</h3>
{_omission_bar(data, field, total_n)}
</div>
<div style="flex:1;min-width:280px">
<h3>📈 采样频次 TOP {min(12, total_n)}</h3>
{_freq_chart(counter, total_n, min(12, total_n))}
</div>
</div>

<h3>📋 推荐来源参考</h3>
{_predictions_table(predictions, counter, actual_set)}

<h3>低覆盖号码参考</h3>
<div class="group-box">
{_remaining_section(predictions, counter, total_n)}
</div>
"""

    if expert_data:
        recommendations_by_field = {
            field: choose_recommendation(
                lotid,
                field,
                predictions,
                counter,
                cfg,
                history=data,
                use_saved_selection=True,
            )[0]
            for _, field, predictions, counter, cfg in areas
        }
        for ed in expert_data:
            label, experts, all_picks = ed
            lbl_pair = {"前区": ("前区", "后区"), "后区": ("前区", "后区"), "红球": ("红球", "蓝球"), "蓝球": ("红球", "蓝球")}
            html += _expert_section_html(experts, all_picks, lbl_pair.get(label, (label, "")), recommendations_by_field)

    html += """
<hr>
<h2>⭐ 最终主推</h2>
<div style="display:flex;flex-wrap:wrap;gap:16px">
"""

    for label, field, predictions, counter, cfg in areas:
        pick = cfg["pick"]
        total_n = cfg["total"]
        rec, strategy = choose_recommendation(
            lotid, field, predictions, counter, cfg, history=data, use_saved_selection=True
        )
        tiers = _recommendation_tiers(predictions, counter, pick, total_n, rec)
        rs = sum(rec)
        rodd = sum(1 for n in rec if n % 2 == 1)
        rspan = max(rec) - min(rec)
        html += f"""
<div class="group-box" style="flex:1;min-width:250px">
<div><b>{label}最终主推（{strategy_label(strategy)}）</b></div>
<div class="tier-box">
  <div class="tier-line"><span class="tier-label">核心号</span><span>{_fmt_nums(tiers["core"])}</span></div>
  <div class="tier-line"><span class="tier-label">备选号</span><span>{_fmt_nums(tiers["backup"])}</span></div>
  <div class="tier-line"><span class="tier-label">观察号</span><span>{_fmt_nums(tiers["watch"])}</span></div>
</div>
<p class="meta">和值{rs} 奇偶{rodd}:{pick-rodd} 跨度{rspan}</p>
</div>"""

    html += "</div></body></html>"
    fname = f"{lotid}_{next_period}.html"
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, "w") as f:
        f.write(html)
    print(f"\n📄 报告已生成: {fpath}")
    return fpath


def _build_html(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field, label, data_status=None):
    total_n = cfg["total"]
    pick = cfg["pick"]
    lot_name = {"kl8": "快乐8", "dlt": "大乐透", "ssq": "双色球"}.get(lotid, lotid)
    actual_set = {int(n) for n in latest_draw[field]} if field in latest_draw else set()
    area_str = f" {label}" if label else ""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{lot_name} {next_period}期{area_str} 预测报告</title>{_style()}</head>
<body>
<h1>🎯 {lot_name} {next_period}期{area_str} 预测报告</h1>
<p class="meta">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  seed: {seed}  |  总采样: {sum(counter.values())} 次</p>
<p class="meta">数据: {len(data)} 期历史  |  选号: {pick}/{total_n}  |  最新开奖: {latest_draw['period']}期</p>
{_data_status_section(data_status)}

{_key_summary_section(data, [(label or "号码", field, predictions, counter, cfg)], None, lotid)}

<h2>🔎 本期预测 vs 最近10期开奖</h2>
{_prediction_history_comparison(data, field, predictions, counter, pick, 10, total_n, lotid, cfg)}

<h2>📊 最近10期走势</h2>
<div class="matrix">{_history_matrix(data, field, total_n, 10)}</div>

<h2>🔴 遗漏 Top 10（最冷号）</h2>
{_omission_bar(data, field, total_n)}

<h2>📈 采样频次 TOP {min(15, total_n)}</h2>
{_freq_chart(counter, total_n, min(15, total_n))}

<h2>📋 推荐来源参考</h2>
{_predictions_table(predictions, counter, actual_set)}

<h2>⭐ 最终主推</h2>
<div class="group-box">
"""
    rec, strategy = choose_recommendation(
        lotid, field, predictions, counter, cfg, history=data, use_saved_selection=True
    )
    tiers = _recommendation_tiers(predictions, counter, pick, total_n, rec)
    html += f"""
<div class="tier-box">
  <div class="tier-line"><span class="tier-label">核心号</span><span>{_fmt_nums(tiers["core"])}</span></div>
  <div class="tier-line"><span class="tier-label">备选号</span><span>{_fmt_nums(tiers["backup"])}</span></div>
  <div class="tier-line"><span class="tier-label">观察号</span><span>{_fmt_nums(tiers["watch"])}</span></div>
</div>
"""

    rs = sum(rec)
    rodd = sum(1 for n in rec if n % 2 == 1)
    rspan = max(rec) - min(rec)
    html += f'<p class="meta">和值{rs} 奇偶{rodd}:{pick-rodd} 跨度{rspan}</p>'
    html += "</div></body></html>"
    return html
