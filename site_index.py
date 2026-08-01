import html
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime


LOTTERY_ORDER = ["kl8", "dlt", "ssq"]
LOTTERY_LABELS = {
    "kl8": "快乐8",
    "dlt": "大乐透",
    "ssq": "双色球",
}

PREDICTION_RE = re.compile(r"^(kl8|dlt|ssq)_(\d+)\.html$")
REVIEW_RE = re.compile(r"^review_(kl8|dlt|ssq)\.html$")


def _period_key(filename):
    match = PREDICTION_RE.match(filename)
    return int(match.group(2)) if match else 0


def _prediction_files(report_dir):
    files = []
    if not os.path.isdir(report_dir):
        return files
    for name in os.listdir(report_dir):
        match = PREDICTION_RE.match(name)
        if not match:
            continue
        files.append({
            "name": name,
            "lotid": match.group(1),
            "period": int(match.group(2)),
        })
    return sorted(files, key=lambda item: (LOTTERY_ORDER.index(item["lotid"]), -item["period"]))


def _review_files(report_dir):
    files = []
    if not os.path.isdir(report_dir):
        return files
    for name in os.listdir(report_dir):
        match = REVIEW_RE.match(name)
        if match:
            files.append({"name": name, "lotid": match.group(1)})
    return sorted(files, key=lambda item: LOTTERY_ORDER.index(item["lotid"]))


def create_latest_aliases(report_dir):
    latest = {}
    by_lottery = defaultdict(list)
    for item in _prediction_files(report_dir):
        by_lottery[item["lotid"]].append(item)

    for lotid in LOTTERY_ORDER:
        items = by_lottery.get(lotid, [])
        if not items:
            continue
        newest = max(items, key=lambda item: item["period"])
        alias = f"latest_{lotid}.html"
        src = os.path.join(report_dir, newest["name"])
        dst = os.path.join(report_dir, alias)
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copyfile(src, dst)
        latest[lotid] = {**newest, "alias": alias}
    return latest


def _card(href, title, hint):
    return (
        f'<a class="card" href="{html.escape(href)}">'
        f'<span class="name">{html.escape(title)}</span>'
        f'<span class="hint">{html.escape(hint)}</span>'
        f'</a>'
    )


def _section(title, cards, empty_text="暂无"):
    if cards:
        body = "\n".join(cards)
    else:
        body = f'<p class="empty">{html.escape(empty_text)}</p>'
    return f"""
<section>
  <h2>{html.escape(title)}</h2>
  <div class="list">
    {body}
  </div>
</section>
"""


def build_index_html(report_dir, updated_at=None, recent_per_lottery=8):
    updated_at = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    latest = create_latest_aliases(report_dir)
    predictions = _prediction_files(report_dir)
    reviews = _review_files(report_dir)

    latest_cards = []
    for lotid in LOTTERY_ORDER:
        item = latest.get(lotid)
        if not item:
            continue
        label = LOTTERY_LABELS[lotid]
        latest_cards.append(_card(
            item["alias"],
            f"{label} 最新预测",
            f"{item['period']}期，固定入口",
        ))

    review_cards = []
    for item in reviews:
        label = LOTTERY_LABELS[item["lotid"]]
        review_cards.append(_card(
            item["name"],
            f"{label} 历史复盘",
            "长期命中统计与随机基线对比",
        ))

    recent_cards = []
    by_lottery = defaultdict(list)
    for item in predictions:
        by_lottery[item["lotid"]].append(item)
    for lotid in LOTTERY_ORDER:
        for item in sorted(by_lottery.get(lotid, []), key=lambda x: -x["period"])[:recent_per_lottery]:
            label = LOTTERY_LABELS[lotid]
            recent_cards.append(_card(
                item["name"],
                f"{label} {item['period']}期",
                item["name"],
            ))

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>彩票预测报告</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 14px;
      background: #f5f5f5;
      color: #222;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.45;
    }}
    main {{ max-width: 760px; margin: 0 auto; }}
    h1 {{
      margin: 4px 0 6px;
      color: #1a1a2e;
      font-size: 24px;
      line-height: 1.25;
    }}
    h2 {{
      margin: 20px 0 8px;
      color: #16213e;
      font-size: 17px;
      line-height: 1.3;
    }}
    .meta {{ margin: 0 0 14px; color: #666; font-size: 13px; }}
    .list {{ display: grid; gap: 10px; }}
    .card {{
      display: block;
      padding: 13px 14px;
      border: 1px solid #ddd;
      border-radius: 8px;
      background: #fff;
      color: inherit;
      text-decoration: none;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .name {{
      display: block;
      color: #16213e;
      font-size: 17px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .hint {{
      display: block;
      margin-top: 4px;
      color: #666;
      font-size: 12px;
    }}
    .empty {{
      margin: 8px 0;
      padding: 10px 12px;
      border: 1px dashed #ccc;
      border-radius: 8px;
      color: #666;
      background: #fff;
      font-size: 13px;
    }}
    @media (max-width: 480px) {{
      body {{ padding: 10px; }}
      h1 {{ font-size: 21px; }}
      h2 {{ font-size: 16px; }}
      .card {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>彩票预测报告</h1>
    <p class="meta">更新时间: {html.escape(updated_at)}</p>
    {_section("最新预测报告", latest_cards, "暂无最新预测报告")}
    {_section("历史复盘", review_cards, "暂无历史复盘报告")}
    {_section("最近预测归档", recent_cards, "暂无历史预测报告")}
  </main>
</body>
</html>
"""


def generate_site(report_dir, updated_at=None):
    os.makedirs(report_dir, exist_ok=True)
    index_html = build_index_html(report_dir, updated_at=updated_at)
    index_path = os.path.join(report_dir, "index.html")
    with open(index_path, "w") as f:
        f.write(index_html)
    return index_path


def main(argv):
    report_dir = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(__file__), "reports")
    updated_at = os.environ.get("SITE_UPDATED_AT")
    path = generate_site(report_dir, updated_at=updated_at)
    print(f"首页已生成: {path}")


if __name__ == "__main__":
    main(sys.argv)
