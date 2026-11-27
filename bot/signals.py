"""تولید سیگنال با امتیازدهی هم‌پوشانی (confluence) + ردیابی نتیجه."""
import numpy as np
from .smc import range_pos

MAX_SCORE = 11


def find_signal(sym, tf, an, an4, an1d, min_rr=2.0):
    d = an4["trend"]
    if d == 0:
        return None
    c = an["c"]
    n = len(c)
    price = float(c.c[-1])
    a = float(an["atr"][-1])
    evs = [e for e in an["events"] if e["dir"] == d and n - 1 - e["i"] <= 40]
    if not evs:
        return None
    ev = evs[-1]

    zones = []
    for f in an["fvg"]:
        if f["dir"] == d and f["i"] >= ev["origin"] - 1:
            zones.append(dict(kind="FVG", **{k: f[k] for k in ("top", "bot", "i")}))
    for z in an["ob"]:
        if z["dir"] == d and z["ev"] == ev["i"]:
            zones.append(dict(kind="OB", **{k: z[k] for k in ("top", "bot", "i")}))
    near = [z for z in zones if z["bot"] - 0.25 * a <= price <= z["top"] + 0.25 * a]
    if not near:
        return None
    z = max(near, key=lambda x: x["i"])
    overlap = any(o is not z and o["kind"] != z["kind"] and o["bot"] <= z["top"] and o["top"] >= z["bot"] for o in near)

    # حد ضرر
    if d == 1:
        sl = min(z["bot"] - 0.3 * a, price - 1.0 * a)
    else:
        sl = max(z["top"] + 0.3 * a, price + 1.0 * a)
    risk = abs(price - sl)
    if risk <= 0:
        return None

    # اهداف: سوئینگ‌ها و نقدینگی در جهت معامله
    levels = []
    for src in (an, an4):
        sw = src["sh"] if d == 1 else src["sl"]
        levels += [p for _, p in sw]
    pools = an["liq"]["hi" if d == 1 else "lo"] + an4["liq"]["hi" if d == 1 else "lo"]
    levels += [p["level"] for p in pools]
    levels = sorted(set(levels)) if d == 1 else sorted(set(levels), reverse=True)
    ahead = [x for x in levels if (x - price) * d >= 1.2 * risk]
    tp1 = ahead[0] if ahead else price + d * 1.5 * risk
    far = [x for x in ahead if (x - price) * d >= 2.5 * risk and x != tp1]
    tp2 = far[0] if far else price + d * 3.0 * risk
    rr1, rr2 = abs(tp1 - price) / risk, abs(tp2 - price) / risk
    if rr2 < min_rr:
        return None

    # امتیازدهی
    score, why = 2, ["جهت ۴ساعته هم‌راستا با معامله"]
    t1d = an1d["trend"]
    if t1d == d:
        score += 1; why.append("روند روزانه هم‌جهت")
    elif t1d == -d:
        score -= 2; why.append("⚠️ روند روزانه مخالف")
    e50, e200 = an4["ema50"][-1], an4["ema200"][-1]
    if (e50 > e200) == (d == 1):
        score += 1; why.append("EMA50/200 در ۴ساعته هم‌جهت")
    score += 2
    why.append(f"{ev['kind']} {'صعودی' if d == 1 else 'نزولی'} در {tf}")
    if any(s["dir"] == d for s in an["sweeps"] if n - 1 - s["i"] <= 25):
        score += 1; why.append("جارو شدن نقدینگی قبل از حرکت")
    if overlap:
        score += 1; why.append("هم‌پوشانی FVG و اوردر بلاک")
    pos = range_pos(an)
    if (d == 1 and pos <= 0.5) or (d == -1 and pos >= 0.5):
        score += 1; why.append("قیمت در ناحیهٔ " + ("دیسکانت" if d == 1 else "پرمیوم"))
    r = float(an["rsi"][-1])
    if (d == 1 and 25 < r < 65) or (d == -1 and 35 < r < 75):
        score += 1; why.append(f"RSI مناسب ({r:.0f})")
    vol = c.v
    if ev["i"] >= 20 and vol[ev["i"]] > 1.3 * vol[ev["i"] - 20:ev["i"]].mean():
        score += 1; why.append("حجم بالا در شکست ساختار")
    why.append(f"ناحیه ورود: {z['kind']}")

    return dict(sym=sym, tf=tf, dir=d, entry=price, sl=float(sl), tp1=float(tp1), tp2=float(tp2),
                rr1=float(rr1), rr2=float(rr2), score=int(score), why=why,
                zone=[z["bot"], z["top"]], zone_kind=z["kind"], t=float(c.t[-1]))


def resolve(sig, c):
    """به‌روزرسانی وضعیت سیگنال با کندل‌های جدید. تغییر وضعیت را برمی‌گرداند."""
    d = sig["dir"]
    sig.setdefault("status", "open")
    status0 = sig["status"]
    stop = sig["sl"] if sig.get("status", "open") == "open" else sig["entry"]
    for i in range(len(c.t)):
        if c.t[i] <= sig.get("last_t", sig["t"]):
            continue
        hi, lo = c.h[i], c.l[i]
        st = sig.get("status", "open")
        stop = sig["sl"] if st == "open" else sig["entry"]
        hit_stop = lo <= stop if d == 1 else hi >= stop
        hit1 = hi >= sig["tp1"] if d == 1 else lo <= sig["tp1"]
        hit2 = hi >= sig["tp2"] if d == 1 else lo <= sig["tp2"]
        if st == "open":
            if hit_stop:
                sig.update(status="sl", r=-1.0)
            elif hit1:
                sig["status"] = "tp1"
                if hit2:
                    sig.update(status="tp2", r=0.5 * sig["rr1"] + 0.5 * sig["rr2"])
        elif st == "tp1":
            if hit_stop:
                sig.update(status="be", r=0.5 * sig["rr1"])
            elif hit2:
                sig.update(status="tp2", r=0.5 * sig["rr1"] + 0.5 * sig["rr2"])
        sig["last_t"] = float(c.t[i])
        if sig["status"] in ("sl", "be", "tp2"):
            break
        if c.t[i] - sig["t"] > 72 * 3600:
            if sig["status"] == "tp1":
                sig.update(status="be", r=0.5 * sig["rr1"])
            else:
                sig.update(status="expired", r=0.0)
            break
    return sig["status"] != status0


def stats(sigs):
    done = [s for s in sigs if s.get("status") in ("sl", "be", "tp2", "tp1") and s.get("status") != "expired"]
    closed = [s for s in sigs if s.get("status") in ("sl", "be", "tp2")]
    wins = [s for s in sigs if s.get("status") in ("tp1", "be", "tp2")]
    n = len([s for s in sigs if s.get("status") != "expired"])
    return dict(total=n, wins=len(wins), losses=len([s for s in sigs if s.get("status") == "sl"]),
                open=len([s for s in sigs if s.get("status") in (None, "open", "tp1")]),
                winrate=(len(wins) / max(1, len(wins) + len([s for s in sigs if s.get("status") == "sl"])) * 100),
                avg_r=float(np.mean([s["r"] for s in closed])) if closed else 0.0)
