import json, logging, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("bot")

FEATURES = {
    "daily_analysis": "📊 تحلیل روزانه",
    "events": "🔔 رویدادهای چارت (BOS/CHoCH/FVG/نقدینگی)",
    "signals": "🎯 سیگنال معاملاتی",
    "news": "📰 اخبار مهم",
    "prices": "💵 قیمت تتر و طلا",
}

DEFAULT_SETTINGS = {
    "features": {k: True for k in FEATURES} | {"app_feed": True},
    "routes": {k: ["all"] for k in FEATURES},
    "channels": {},
    "symbols": ["BTC-USDT", "ETH-USDT"],
    "params": {
        "min_score": 7,            # حداقل امتیاز سیگنال از 11
        "min_rr": 2.0,             # حداقل ریسک به ریوارد
        "daily_hour": 8,           # ساعت تحلیل روزانه (وقت تهران)
        "price_hour": 9,           # ساعت ارسال قیمت روزانه (وقت تهران)
        "price_move_pct": 1.0,     # حرکت شدید قیمت تتر/طلا (درصد)
        "price_every_hours": 0,    # 0 = فقط روزانه / حرکت شدید ؛ عدد > 0 = هر چند ساعت
        "gold_adjust_pct": 0.0,    # تنظیم اختلاف طلای جهانی با بازار ایران
        "news_min_importance": 6,  # حداقل اهمیت خبر از 10
        "news_max_per_run": 3,
    },
}


def load(name, default):
    p = DATA / name
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception as e:  # noqa
            log.warning("bad json %s: %s", name, e)
    return default


def save(name, obj):
    p = DATA / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, p)


def merge_defaults(s):
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    for k, v in s.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def load_settings():
    return merge_defaults(load("settings.json", {}))


def fmt(x):
    x = float(x)
    if abs(x) >= 1000:
        return f"{x:,.1f}"
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:.5f}"
