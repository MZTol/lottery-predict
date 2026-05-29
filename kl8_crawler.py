import json
import os
import re
import time
import urllib.request

BASE_URL = "https://www.917500.cn/win/getlist.html"
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "kl8_history.json")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PAGES = 5


def fetch_page(page=1):
    url = f"{BASE_URL}?lotid=kl8&page={page}&limit=20&ish=0"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Referer": "https://www.917500.cn/",
        "X-Requested-With": "XMLHttpRequest",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    blocks = re.finditer(
        r'<p class="h1"><b>(\d+)期</b>.*?</p>\s*<p class="kl8">(.*?)</p>',
        html, re.DOTALL
    )

    results = []
    for m in blocks:
        period = m.group(1)
        nums_html = m.group(2)
        numbers = re.findall(r'<b>(\d+)</b>', nums_html)
        if len(numbers) == 20:
            results.append({"period": period, "numbers": numbers})

    return results


def fetch_all(max_pages=PAGES):
    all_data = []
    for p in range(1, max_pages + 1):
        try:
            data = fetch_page(p)
            if not data:
                break
            all_data.extend(data)
            print(f"  第{p}页: {len(data)}期 (累计{len(all_data)}期)")
            time.sleep(0.5)
        except Exception as e:
            print(f"  第{p}页失败: {e}")
            break
    return all_data


def save(data, filename=OUTPUT_FILE):
    with open(filename, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(data)} 期数据到 {filename}")


def load(filename=OUTPUT_FILE):
    if os.path.exists(filename):
        with open(filename) as f:
            return json.load(f)
    return []


if __name__ == "__main__":
    print(f"抓取快乐8历史数据 ({PAGES}页, 约{PAGES*10}期)...")
    data = fetch_all()
    save(data)
