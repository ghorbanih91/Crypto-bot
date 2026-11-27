"""بک‌تست: python -m bot.backtest BTC-USDT 30 [min_score]
نتیجه نشان می‌دهد این منطق روی گذشته چه وین‌ریتی داشته (تضمینی برای آینده نیست)."""
import sys
import numpy as np
from . import market, smc, signals as sg
from .market import TF_SEC


def run(sym, days, min_score=10, min_rr=2.0, data=None):
    D = data or {tf: market.history(sym, tf, days if tf in ("15m", "1H") else days + 120) for tf in ("15m", "1H", "4H", "1D")}
    res, last_key, busy = [], {}, {}
    for tf in ("15m", "1H"):
        c = D[tf]
        start = max(300, len(c) - int(days * 86400 / TF_SEC[tf]))
        cache = {}
        for i in range(start, len(c)):
            now = c.t[i] + TF_SEC[tf]
            ltf = c.sl(max(0, i - 299), i + 1)
            def htf(name):
                h = D[name].closed_at(now)
                k = (name, len(h))
                if k not in cache:
                    cache[k] = smc.analyze(h.sl(-300))
                return cache[k]
            a4, a1 = htf("4H"), htf("1D")
            if len(a4["c"]) < 60 or len(a1["c"]) < 30:
                continue
            s = sg.find_signal(sym, tf, smc.analyze(ltf), a4, a1, min_rr)
            if not s or s["score"] < min_score:
                continue
            key = (s["dir"], round(s["entry"] / (a4["atr"][-1])))
            if now - last_key.get(key, 0) < 6 * 3600 or now < busy.get(s["dir"], 0):
                continue
            last_key[key] = now
            sg.resolve(s, c.sl(i + 1))
            busy[s["dir"]] = s.get("last_t", now)
            if s.get("status", "open") in ("open", "tp1"):
                continue
            s["tf"] = tf
            res.append(s)
    return res


def report(res):
    st = sg.stats(res)
    print(f"سیگنال‌ها: {st['total']} | برد: {st['wins']} | باخت: {st['losses']} | وین‌ریت: {st['winrate']:.1f}% | میانگین R: {st['avg_r']:+.2f}")
    for lo in (10, 11, 12):
        sub = [s for s in res if s["score"] >= lo]
        if sub:
            x = sg.stats(sub)
            print(f"  امتیاز ≥{lo}: {x['total']} سیگنال، وین‌ریت {x['winrate']:.0f}%، میانگین R {x['avg_r']:+.2f}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "BTC-USDT"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    ms = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    report(run(sym, days, ms))
