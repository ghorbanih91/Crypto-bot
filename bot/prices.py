"""قیمت تتر (تومان) و طلای ۱۸ عیار (تومان/گرم)."""
import requests
from .util import log


def usdt_toman():
    errs = []
    try:  # نوبیتکس
        j = requests.get("https://api.nobitex.ir/market/stats",
                         params={"srcCurrency": "usdt", "dstCurrency": "rls"}, timeout=20).json()
        return float(j["stats"]["usdt-rls"]["latest"]) / 10, "Nobitex"
    except Exception as e:
        errs.append(f"nobitex: {e}")
    try:  # والکس
        j = requests.get("https://api.wallex.ir/v1/markets", timeout=20).json()
        return float(j["result"]["symbols"]["USDTTMN"]["stats"]["lastPrice"]), "Wallex"
    except Exception as e:
        errs.append(f"wallex: {e}")
    log.warning("usdt_toman failed: %s", errs)
    return None, None


def gold18_toman(usdt_t, adjust_pct=0.0):
    """تخمین: قیمت جهانی طلا (XAUT) ÷ 31.1035 × 0.75 × قیمت تتر. برای بازار ایران حباب را با gold_adjust_pct تنظیم کنید."""
    try:
        j = requests.get("https://www.okx.com/api/v5/market/ticker", params={"instId": "XAUT-USDT"}, timeout=20).json()
        ounce = float(j["data"][0]["last"])
        return ounce / 31.1035 * 0.75 * usdt_t * (1 + adjust_pct / 100)
    except Exception as e:
        log.warning("gold failed: %s", e)
        return None
