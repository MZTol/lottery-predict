import json
import os
import re
import time
import urllib.request
import urllib.error

BASE_URL = "https://www.917500.cn/win/getlist.html"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PAGES = 5
MAX_RETRIES = 3
DIR = os.path.dirname(__file__)

OUTPUT_FILES = {
    "kl8": os.path.join(DIR, "kl8_history.json"),
    "dlt": os.path.join(DIR, "dlt_history.json"),
    "ssq": os.path.join(DIR, "ssq_history.json"),
}


def output_file(lotid):
    return OUTPUT_FILES.get(lotid, os.path.join(DIR, f"{lotid}_history.json"))


def fetch_page(lotid, page=1):
    url = f"{BASE_URL}?lotid={lotid}&page={page}&limit=20&ish=0"
    html = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://www.917500.cn/",
                "X-Requested-With": "XMLHttpRequest",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"  429限流，等待{wait}秒后重试...")
                time.sleep(wait)
            else:
                raise

    if html is None:
        raise RuntimeError(f"获取页面失败: {url}")

    if lotid == "kl8":
        return _parse_kl8(html)
    elif lotid == "dlt":
        return _parse_dlt(html)
    elif lotid == "ssq":
        return _parse_ssq(html)
    return []


def _parse_kl8(html):
    blocks = re.finditer(
        r'<p class="h1"><b>(\d+)期</b>.*?</p>\s*<p class="kl8">(.*?)</p>',
        html, re.DOTALL
    )
    results = []
    for m in blocks:
        nums = re.findall(r'<b>(\d+)</b>', m.group(2))
        if len(nums) == 20:
            results.append({"period": m.group(1), "numbers": nums})
    return results


def _parse_dlt(html):
    blocks = re.finditer(
        r'<p class="h1"><b>(\d+)期</b>.*?</p>\s*<p class="h2">(.*?)</p>',
        html, re.DOTALL
    )
    results = []
    for m in blocks:
        front = re.findall(r'<b class="rb">(\d+)</b>', m.group(2))
        back = re.findall(r'<b class="bb">(\d+)</b>', m.group(2))
        if len(front) == 5 and len(back) == 2:
            results.append({"period": m.group(1), "front": front, "back": back})
    return results


def _parse_ssq(html):
    blocks = re.finditer(
        r'<p class="h1"><b>(\d+)期</b>.*?</p>\s*<p class="h2">(.*?)</p>',
        html, re.DOTALL
    )
    results = []
    for m in blocks:
        front = re.findall(r'<b class="rb">(\d+)</b>', m.group(2))
        back = re.findall(r'<b class="bb">(\d+)</b>', m.group(2))
        if len(front) == 6 and len(back) == 1:
            results.append({"period": m.group(1), "front": front, "back": back})
    return results


def fetch_incremental(lotid, filename=None):
    """增量拉取：只取第1页，合并到缓存头部"""
    stale = load(filename) if filename else []
    existing = {e["period"] for e in stale}

    new_data = fetch_page(lotid, 1)
    if not new_data:
        return stale or []

    added = [e for e in new_data if e["period"] not in existing]
    if not added:
        return stale

    merged = added + stale
    print(f"  新增 {len(added)} 期 (缓存共 {len(merged)} 期)")
    return merged


def fetch_all(lotid, max_pages=PAGES):
    """全量拉取：首次无缓存时使用"""
    all_data = []
    for p in range(1, max_pages + 1):
        try:
            data = fetch_page(lotid, p)
            if not data:
                break
            all_data.extend(data)
            print(f"  第{p}页: {len(data)}期 (累计{len(all_data)}期)")
            time.sleep(0.5)
        except Exception as e:
            print(f"  第{p}页失败: {e}")
            break
    return all_data


def save(data, filename=None):
    if filename is None or not data:
        return
    tmp = filename + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filename)
    print(f"已保存 {len(data)} 期数据到 {filename}")


def load(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return []


if __name__ == "__main__":
    for lotid, label in [("kl8", "快乐8"), ("dlt", "大乐透"), ("ssq", "双色球")]:
        print(f"\n抓取{label}历史数据...")
        data = fetch_all(lotid)
        save(data, output_file(lotid))
