import os
from datetime import datetime
from collections import Counter

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
        body { font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 960px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        h1 { color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 8px; }
        h2 { color: #16213e; margin-top: 28px; }
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
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(36px, 1fr)); gap: 2px; margin: 8px 0; }
        .grid-cell { text-align: center; font-size: 12px; padding: 4px 0; border-radius: 3px; background: #fff; border: 1px solid #eee; }
        .grid-cell.on { background: #e94560; color: #fff; font-weight: bold; }
        .grid-cell.off { color: #ccc; }
        .summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
        .stat-card { background: #fff; border-radius: 6px; padding: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .stat-card .val { font-size: 22px; font-weight: bold; }
        .stat-card .lbl { font-size: 12px; color: #666; }
        .matrix { font-size: 12px; overflow-x: auto; white-space: nowrap; -webkit-overflow-scrolling: touch; }
        .matrix td { padding: 2px 4px; min-width: 22px; }
        .matrix .period-col { text-align: left; font-weight: bold; padding-right: 8px; min-width: 70px; }
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        @media (max-width: 768px) {
            body { padding: 10px; }
            h1 { font-size: 20px; }
            h2 { font-size: 16px; margin-top: 20px; }
            table { font-size: 11px; }
            th, td { padding: 3px 4px; }
            .num { font-size: 13px; padding: 1px 3px; }
            .group-box { padding: 8px 10px; }
            .summary-grid { grid-template-columns: repeat(2, 1fr); gap: 4px; }
            .stat-card { padding: 4px; }
            .stat-card .val { font-size: 16px; }
            .grid-cell { font-size: 10px; padding: 3px 0; }
            .grid { grid-template-columns: repeat(auto-fill, minmax(28px, 1fr)); gap: 1px; }
        }
        @media (max-width: 480px) {
            .summary-grid { grid-template-columns: 1fr; }
            .meta { font-size: 12px; }
            .grid { grid-template-columns: repeat(auto-fill, minmax(22px, 1fr)); }
            .grid-cell { font-size: 9px; padding: 2px 0; }
            .bar { height: 14px; }
        }
    </style>
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


def _predictions_table(predictions, counters, actual_set):
    labels = [
        ("热门", "hot", "tag-hot", predictions["hot"]),
        ("冷门", "cold", "tag-cold", predictions["cold"]),
        ("杀号A(随机)", "a", "tag-a", predictions["kill_a"]),
        ("杀号B(高频)", "b", "tag-b", predictions["kill_b"]),
        ("杀号C(等距)", "c", "tag-c", predictions["kill_c"]),
    ]

    blocks = []
    for label, key, tag_cls, nums in labels:
        nset = {int(n) for n in nums}
        hits = len(nset & actual_set) if actual_set else 0
        tags = " ".join(
            f'<span class="num">{n}</span>'
            for n in nums
        )
        s = sum(int(n) for n in nums)
        odd = sum(1 for n in nums if int(n) % 2 == 1)
        blocks.append(
            f'<div class="group-box">'
            f'<div><b>{label}</b> <span class="tag {tag_cls}">重号{hits}</span></div>'
            f'<div style="margin:6px 0">{tags}</div>'
            f'<div class="meta">和值{s} 奇偶{odd}:{len(nums)-odd} 跨度{max(int(n) for n in nums)-min(int(n) for n in nums)}</div>'
            f'</div>'
        )
    return "\n".join(blocks)


def _recommendation(all_preds, counter, pick):
    combined = Counter()
    for name, nums in all_preds.items():
        for n in nums:
            combined[int(n)] += 1
    top = [n for n, _ in combined.most_common(pick)]
    top.sort()
    return top


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


def _expert_section_html(experts, all_picks, labels):
    if not experts:
        return ""
    from collections import Counter

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
    max_fc = max((c for _, c in cons_f), default=1)
    max_bc = max((c for _, c in cons_b), default=1)

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
    <hr>
    <h2>👥 专家预测参考（共 {len(experts)} 位）</h2>
    {expert_table}
    <h3>📊 专家共识（{label_f} Top 10 + {label_b} Top 6）</h3>
    {consensus_table}
    """


def generate_report(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field="numbers", label="", overlay_hits=None):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    total_n = cfg["total"]
    pick = cfg["pick"]
    lot_name = {"kl8": "快乐8", "dlt": "大乐透", "ssq": "双色球"}.get(lotid, lotid)
    actual_set = {int(n) for n in latest_draw[field]} if field in latest_draw else set()
    area_suffix = f"_{label}" if label else ""

    html = _build_html(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field, label)
    fname = f"{lotid}_{next_period}{area_suffix}.html"
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, "w") as f:
        f.write(html)
    print(f"\n📄 报告已生成: {fpath}")
    return fpath


def generate_combined_report(data, latest_draw, areas, lotid, next_period, seed, expert_data=None):
    """areas: [(label, field, predictions, counter, cfg), ...]
       expert_data: [(label, experts, all_picks), ...] or None
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    lot_name = {"kl8": "快乐8", "dlt": "大乐透", "ssq": "双色球"}.get(lotid, lotid)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{lot_name} {next_period}期 预测报告</title>{_style()}</head>
<body>
<h1>🎯 {lot_name} {next_period}期 预测报告</h1>
<p class="meta">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  seed: {seed}</p>
<p class="meta">数据: {len(data)} 期历史  |  最新开奖: {latest_draw['period']}期</p>
"""

    for label, field, predictions, counter, cfg in areas:
        total_n = cfg["total"]
        pick = cfg["pick"]
        actual_set = {int(n) for n in latest_draw[field]} if field in latest_draw else set()

        html += f"""
<hr>
<h2>📌 {label}（{pick}/{total_n}）</h2>
<p class="meta">总采样: {sum(counter.values())} 次</p>

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

<h3>📋 五组预测</h3>
{_predictions_table(predictions, {}, actual_set)}

<h3>🗑️ 系统杀号后剩余</h3>
<div class="group-box">
{_remaining_section(predictions, counter, total_n)}
</div>
"""

    if expert_data:
        for ed in expert_data:
            label, experts, all_picks = ed
            lbl_pair = {"前区": ("前区", "后区"), "后区": ("前区", "后区"), "红球": ("红球", "蓝球"), "蓝球": ("红球", "蓝球")}
            html += _expert_section_html(experts, all_picks, lbl_pair.get(label, (label, "")))

        for label, field, predictions, counter, cfg in areas:
            total_n = cfg["total"]
            expert_remain = _expert_remaining_section(expert_data, total_n, field)
            if expert_remain:
                html += f"""
<hr>
<h2>📌 {label} 专家杀号后剩余</h2>
<div class="group-box">
{expert_remain}
</div>
"""

    html += """
<hr>
<h2>⭐ 综合推荐</h2>
<div style="display:flex;flex-wrap:wrap;gap:16px">
"""

    for label, field, predictions, counter, cfg in areas:
        pick = cfg["pick"]
        rec = _recommendation(predictions, counter, pick)
        rs = sum(rec)
        rodd = sum(1 for n in rec if n % 2 == 1)
        rspan = max(rec) - min(rec)
        html += f"""
<div class="group-box" style="flex:1;min-width:250px">
<div><b>{label} Top {pick}</b></div>
<p style="font-size:16px">{" ".join(f'<span class="num">{n:02d}</span>' for n in rec)}</p>
<p class="meta">和值{rs} 奇偶{rodd}:{pick-rodd} 跨度{rspan}</p>
</div>"""

    html += "</div></body></html>"
    fname = f"{lotid}_{next_period}.html"
    fpath = os.path.join(REPORTS_DIR, fname)
    with open(fpath, "w") as f:
        f.write(html)
    print(f"\n📄 报告已生成: {fpath}")
    return fpath


def _build_html(data, latest_draw, predictions, counter, cfg, lotid, next_period, seed, field, label):
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

<h2>📊 最近10期走势</h2>
<div class="matrix">{_history_matrix(data, field, total_n, 10)}</div>

<h2>🔴 遗漏 Top 10（最冷号）</h2>
{_omission_bar(data, field, total_n)}

<h2>📈 采样频次 TOP {min(15, total_n)}</h2>
{_freq_chart(counter, total_n, min(15, total_n))}

<h2>📋 五组预测结果</h2>
{_predictions_table(predictions, {}, actual_set)}

<h2>⭐ 推荐参考（综合排名 Top {pick}）</h2>
<div class="group-box">
<p style="font-size:18px">
"""
    rec = _recommendation(predictions, counter, pick)
    html += " ".join(f'<span class="num">{n:02d}</span>' for n in rec)

    rs = sum(rec)
    rodd = sum(1 for n in rec if n % 2 == 1)
    rspan = max(rec) - min(rec)
    html += f'</p><p class="meta">和值{rs} 奇偶{rodd}:{pick-rodd} 跨度{rspan}</p>'
    html += "</div></body></html>"
    return html
