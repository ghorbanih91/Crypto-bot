"""دریافت کندل از OKX (از سرورهای گیت‌هاب بدون مشکل کار می‌کند)."""
import time
from dataclasses import dataclass
import numpy as np
import requests

BASE = "https://www.okx.com/api/v5/market"
TF_SEC = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400, "1D": 86400}


@dataclass
class C:
    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    tf: str = "15m"

    def __len__(self):
        return len(self.t)

    def sl(self, a, b=None):
        s = slice(a, b)
        return C(self.t[s], self.o[s], self.h[s], self.l[s], self.c[s], self.v[s], self.tf)

    def closed_at(self, now):
        """فقط کندل‌هایی که تا زمان now بسته شده‌اند."""
        m = self.t + TF_SEC[self.tf] <= now
        return C(self.t[m], self.o[m], self.h[m], self.l[m], self.c[m], self.v[m], self.tf)


def _to_c(rows, tf):
    rows = sorted(rows, key=lambda r: int(r[0]))
    a = np.array([[float(x) for x in r[:6]] for r in rows])
    a[:, 0] /= 1000.0
    return C(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5], tf)


def candles(sym, tf, limit=300):
    r = requests.get(f"{BASE}/candles", params={"instId": sym, "bar": tf, "limit": limit}, timeout=30)
    j = r.json()
    if j.get("code") != "0":
        raise RuntimeError(f"OKX {sym} {tf}: {j}")
    c = _to_c(j["data"], tf)
    return c.closed_at(time.time())


def history(sym, tf, days):
    """دادهٔ تاریخی برای بک‌تست."""
    need = int(days * 86400 / TF_SEC[tf]) + 400
    rows, after = [], None
    while len(rows) < need:
        p = {"instId": sym, "bar": tf, "limit": 100}
        if after:
            p["after"] = after
        j = requests.get(f"{BASE}/history-candles", params=p, timeout=30).json()
        if j.get("code") != "0" or not j["data"]:
            break
        rows += j["data"]
        after = j["data"][-1][0]
        time.sleep(0.15)
    return _to_c(rows, tf)


def last_price(sym):
    j = requests.get(f"{BASE}/ticker", params={"instId": sym}, timeout=30).json()
    d = j["data"][0]
    last, open24 = float(d["last"]), float(d["open24h"])
    return last, (last / open24 - 1) * 100
