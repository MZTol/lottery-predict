import urllib.request
import re
import json
import time


_CN = "零一二三四五六七八九"
_CN_MAP = {c: i for i, c in enumerate(_CN)}
_UNITS = {"十": 10, "百": 100}
_CN_NUM_PAT = re.compile(rf"[{_CN}十百]+期")


def _chinese_to_num(s):
    """五十九 -> 59, 五十八 -> 58"""
    s = s.replace("期", "")
    if not s:
        return None
    total = 0
    tmp = 0
    for ch in s:
        if ch in _CN_MAP:
            tmp = _CN_MAP[ch]
        elif ch in _UNITS:
            unit = _UNITS[ch]
            if tmp == 0:
                tmp = 1
            total += tmp * unit
            tmp = 0
    total += tmp
    return total if total > 0 else None


def _extract_period(title):
    # Try Arabic numerals first: 059期, 2026061期
    m = re.search(r"(\d+)期", title)
    if m:
        return int(m.group(1))
    # Try Chinese numerals: 五十九期
    m = _CN_NUM_PAT.search(title)
    if m:
        return _chinese_to_num(m.group())
    return None


def match_period(articles, target_period):
    matched = []
    for art in articles:
        p = _extract_period(art["title"])
        if p is None:
            continue
        if p == target_period or p == target_period % 1000:
            matched.append(art)
    return matched


def fetch_article_list(lid, page=1, num=30):
    url = (
        f"https://feed.mix.sina.com.cn/api/roll/get"
        f"?lid={lid}&pageid=400&num={num}&page={page}"
        f"&fields=wapurl%2Ctitle&callback=ct6"
    )
    d = _fetch_json(url)
    return d["result"].get("data", []) if d else []


def fetch_article_detail(url, timeout=10):
    resp = urllib.request.urlopen(url, timeout=timeout)
    return resp.read().decode("utf-8", errors="ignore")


def _fetch_json(url, timeout=10):
    resp = urllib.request.urlopen(url, timeout=timeout)
    raw = resp.read().decode("utf-8", errors="ignore")
    prefix = "try{ct6("
    suffix = ");}catch(e){};"
    if raw.startswith(prefix) and raw.endswith(suffix):
        raw = raw[len(prefix) : -len(suffix)]
    depth = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0 and ch == "}":
            return json.loads(raw[: i + 1])
    return None


def get_articles_by_lid(lid, target_period, num=30, max_pages=10):
    all_articles = []
    target_suffix = target_period % 1000
    for p in range(1, max_pages + 1):
        try:
            articles = fetch_article_list(lid, page=p, num=num)
        except Exception:
            break
        if not articles:
            break
        n_before = len(all_articles)
        for art in articles:
            period = _extract_period(art["title"])
            if period is None:
                continue
            if period == target_period or period == target_suffix:
                all_articles.append(art)
        if len(all_articles) == n_before:
            break
        time.sleep(0.2)
    return all_articles


def _extract_name(title):
    for sep in ["大乐透", "双色球", "快乐8"]:
        m = re.search(r"\d+期(.+?)" + sep, title)
        if m:
            return m.group(1).strip()
    m = re.search(r"\d+期(.+)", title)
    if m:
        return m.group(1).strip()[:6]
    m = _CN_NUM_PAT.search(title)
    if m:
        rest = title[m.end():]
        for sep in ["大乐透", "双色球", "快乐8"]:
            idx = rest.find(sep)
            if idx > 0:
                return rest[:idx].strip()
    return title[:8]


def _parse_generic_predictions(html, lotid):
    result = {}
    seen = set()
    text = re.sub(r"\s+", " ", html)
    kw = r"(?:推荐|参考|单挑一注)"

    def _add(fs, bs, nums):
        nonlocal result, seen
        key = f"{fs}+{bs}"
        if key in seen:
            return
        seen.add(key)
        parts = nums.split("+")
        if len(parts) == 2:
            front = [int(x.strip()) for x in re.split(r"[,\s，]+", parts[0]) if x.strip().isdigit()]
            back = [int(x.strip()) for x in re.split(r"[,\s，]+", parts[1]) if x.strip().isdigit()]
            if len(front) >= fs - 2 and len(back) >= bs - 1:
                result[key] = {"front": front[:fs], "back": back[:bs]}

    max_back = {"dlt": 12, "ssq": 16}.get(lotid, 12)

    for pat in [
        rf'(\d+)\+(\d+)[^<]{{0,40}}{kw}[：:]\s*([0-9,\s+]+)',
        rf'(\d+)\+(\d+)[^<]{{0,40}}{kw}[：:][^<]*</strong>\s*([0-9,\s+]+)',
        rf'(\d+)\+(\d+)[^<]{{0,40}}{kw}[：:][^<]*</strong>\s*</div>\s*<div[^>]*c_mainTxt[^>]*>\s*([0-9,\s+]+)\s*<',
        rf'(\d+)\+(\d+)[^<]{{0,40}}大复式[：:][^<]*</strong>\s*([0-9,\s+]+)',
    ]:
        for m in re.finditer(pat, text):
            fs, bs = int(m.group(1)), int(m.group(2))
            if bs <= max_back:
                _add(fs, bs, m.group(3).strip())

    return result


def parse_dlt_predictions(html):
    return _parse_generic_predictions(html, "dlt")


def parse_ssq_predictions(html):
    return _parse_generic_predictions(html, "ssq")


def parse_kl8_predictions(html):
    result = {}
    seen = set()
    text = re.sub(r"\s+", " ", html)

    for m in re.finditer(r'(?:选[八九九十十]+|复式|胆拖|推荐)[：:]\s*([\d\s]{10,200})', text):
        nums = [int(x) for x in re.findall(r"\d{2}", m.group(1)) if 1 <= int(x) <= 80]
        if not nums:
            continue
        key = f"{len(nums)}+0"
        if key in seen:
            continue
        seen.add(key)
        result[key] = {"front": nums, "back": []}

    if not result:
        for m in re.finditer(r'([\d\s]{10,200}（可做选)', text):
            nums = [int(x) for x in re.findall(r"\d{2}", m.group(1)) if 1 <= int(x) <= 80]
            if 5 <= len(nums) <= 30:
                result[f"{len(nums)}+0"] = {"front": nums, "back": []}
                break

    return result


def _extract_avoid_numbers(html, total=80):
    """Extract explicit expert exclusions without treating ordinary prose as picks."""
    text = re.sub(r"\s+", " ", html)
    numbers = []
    for match in re.finditer(
        r"(?:杀号|排除|避开|不看好|不推荐|冷门杀号)[：: ]*([\d\s,，、-]{2,240})",
        text,
    ):
        for token in re.findall(r"\d{1,2}", match.group(1)):
            value = int(token)
            if 1 <= value <= total:
                numbers.append(value)
    return sorted(set(numbers))


LID_MAP = {
    "dlt": {"lid": 2550, "parser": parse_dlt_predictions, "label": "大乐透"},
    "ssq": {"lid": 2642, "parser": parse_ssq_predictions, "label": "双色球"},
    "kl8": {"lid": 2644, "parser": parse_kl8_predictions, "label": "快乐8"},
}


def get_expert_picks(lotid, target_period, max_articles=12, delay=0.3):
    info = LID_MAP.get(lotid)
    if info is None:
        return [], {}

    articles = get_articles_by_lid(info["lid"], target_period, num=30, max_pages=10)
    if lotid == "kl8":
        articles = [a for a in articles if "快乐8" in a.get("title", "")]

    matched = match_period(articles, target_period)
    if not matched:
        return [], {}

    experts = []
    all_picks = {"front": [], "back": []}

    for art in matched[:max_articles]:
        title = art["title"]
        url = art["wapurl"]
        try:
            html = fetch_article_detail(url)
            picks = info["parser"](html)
            if picks:
                entry = {
                    "name": _extract_name(title),
                    "picks": picks,
                    "avoid": _extract_avoid_numbers(html, 80 if lotid == "kl8" else 49),
                    "url": url,
                }
                experts.append(entry)
                for k in picks:
                    all_picks["front"].extend(picks[k].get("front", []))
                    all_picks["back"].extend(picks[k].get("back", []))
                if entry["avoid"]:
                    all_picks.setdefault("avoid_front", []).extend(entry["avoid"])
        except Exception:
            pass
        time.sleep(delay)

    return experts, all_picks
