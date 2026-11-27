"""اخبار مهم: RSS → فیلتر کلیدواژه → (اختیاری) ترجمه و امتیازدهی با Claude."""
import hashlib, json, os, re, time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import requests
from .util import log

FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outputfeeds/rss/",
    "https://decrypt.co/feed",
]
KW = {"etf": 3, "sec ": 3, "fed": 3, "fomc": 3, "rate cut": 3, "rate hike": 3, "cpi": 3, "inflation": 2, "hack": 3,
      "exploit": 3, "bankrupt": 3, "ban": 2, "approve": 2, "lawsuit": 2, "liquidat": 2, "record": 2, "crash": 3,
      "surge": 2, "plunge": 3, "halving": 3, "tariff": 2, "trump": 2, "blackrock": 3, "binance": 2, "tether": 2,
      "stablecoin": 2, "treasury": 2, "reserve": 2, "bitcoin": 1, "ethereum": 1, "whale": 1, "regulat": 2}
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def fetch():
    out = []
    for u in FEEDS:
        try:
            root = ET.fromstring(requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"}).content)
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                desc = re.sub("<[^>]+>", "", it.findtext("description") or "")[:400]
                try:
                    ts = parsedate_to_datetime(it.findtext("pubDate")).timestamp()
                except Exception:
                    ts = time.time()
                out.append(dict(id=hashlib.md5(link.encode()).hexdigest()[:12], title=title, link=link, desc=desc, ts=ts))
        except Exception as e:
            log.warning("feed %s: %s", u, e)
    return out


def kw_score(it):
    t = (it["title"] + " ").lower()
    return sum(w for k, w in KW.items() if k in t)


GEM_KEY = os.environ.get("GEMINI_API_KEY", "")
GEM_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _prompt(it):
    return ("You are a crypto news editor. For the news below return ONLY JSON: "
            '{"importance":1-10 (market-moving for BTC/ETH traders),"title_fa":"Persian headline","summary_fa":"1-2 sentence Persian summary"}\n\n'
            f"Title: {it['title']}\nText: {it['desc']}")


def _json(txt):
    return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))


PROMPT = ("You are a crypto news editor. For the news below return ONLY JSON: "
          '{"importance":1-10 (market-moving for BTC/ETH traders),"title_fa":"Persian headline","summary_fa":"1-2 sentence Persian summary"}\n\n')
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _parse(txt):
    return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))


def llm(it):
    """ترجمه + اهمیت ۱ تا ۱۰. اولویت: Gemini (رایگان) ← Claude ← None."""
    prompt = PROMPT + f"Title: {it['title']}\nText: {it['desc']}"
    if GEMINI_KEY:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                              headers={"x-goog-api-key": GEMINI_KEY, "content-type": "application/json"},
                              json={"contents": [{"parts": [{"text": prompt}]}],
                                    "generationConfig": {"responseMimeType": "application/json"}}, timeout=60)
            return _parse(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e:
            log.warning("gemini: %s", e)
    if KEY:
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]}, timeout=60)
            return _parse(r.json()["content"][0]["text"])
        except Exception as e:
            log.warning("claude: %s", e)
    return None


def pick(seen, min_importance=6, max_n=3):
    """خبرهای مهم جدید را برمی‌گرداند (با فیلد fa)."""
    items = [i for i in fetch() if i["id"] not in seen and time.time() - i["ts"] < 8 * 3600]
    items.sort(key=lambda i: -kw_score(i))
    res = []
    for it in items:
        s = kw_score(it)
        if s < 3:
            continue
        info = llm(it)
        if info is not None:
            if int(info.get("importance", 0)) < min_importance:
                seen.append(it["id"]); continue
            it["fa"] = info
        elif s < 5:  # بدون هوش مصنوعی فیلتر سخت‌تر
            continue
        res.append(it); seen.append(it["id"])
        if len(res) >= max_n:
            break
    return res
