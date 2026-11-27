"""موتور تحلیل: ساختار بازار (BOS/CHoCH)، FVG، اوردر بلاک، نقدینگی، اندیکاتورها."""
import numpy as np


def ema(a, n):
    a = np.asarray(a, float)
    k = 2 / (n + 1)
    out = np.empty_like(a)
    out[0] = a[0]
    for i in range(1, len(a)):
        out[i] = a[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(c, n=14):
    c = np.asarray(c, float)
    d = np.diff(c, prepend=c[0])
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    ru, rd = np.zeros_like(c), np.zeros_like(c)
    for i in range(1, len(c)):
        ru[i] = (ru[i - 1] * (n - 1) + up[i]) / n
        rd[i] = (rd[i - 1] * (n - 1) + dn[i]) / n
    return 100 - 100 / (1 + ru / np.where(rd == 0, 1e-12, rd))


def atr(c, n=14):
    pc = np.roll(c.c, 1)
    pc[0] = c.o[0]
    tr = np.maximum(c.h - c.l, np.maximum(abs(c.h - pc), abs(c.l - pc)))
    out = np.empty_like(tr)
    out[0] = tr[0]
    for i in range(1, len(tr)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def swings(h, l, k=3):
    sh, sl = [], []
    for i in range(k, len(h) - k):
        w = h[i - k:i + k + 1]
        if h[i] == w.max() and (w == h[i]).sum() == 1:
            sh.append((i, float(h[i])))
        w = l[i - k:i + k + 1]
        if l[i] == w.min() and (w == l[i]).sum() == 1:
            sl.append((i, float(l[i])))
    return sh, sl


def structure(c, sh, sl, k=3):
    cl, n = c.c, len(c.c)
    shs = {j + k: (j, p) for j, p in sh}
    sls = {j + k: (j, p) for j, p in sl}
    events, trend = [], 0
    lastH = lastL = None
    hb = lb = True
    for i in range(n):
        if i in shs:
            lastH, hb = shs[i], False
        if i in sls:
            lastL, lb = sls[i], False
        if lastH and not hb and cl[i] > lastH[1]:
            kind = "CHoCH" if trend == -1 else "BOS"
            events.append(dict(i=i, kind=kind, dir=1, level=lastH[1], origin=lastL[0] if lastL else lastH[0]))
            trend, hb = 1, True
        if lastL and not lb and cl[i] < lastL[1]:
            kind = "CHoCH" if trend == 1 else "BOS"
            events.append(dict(i=i, kind=kind, dir=-1, level=lastL[1], origin=lastH[0] if lastH else lastL[0]))
            trend, lb = -1, True
    return events, trend


def fvgs(c, a, min_atr=0.15):
    out, n = [], len(c.t)
    for i in range(2, n):
        if c.l[i] > c.h[i - 2] and c.l[i] - c.h[i - 2] >= min_atr * a[i]:
            f = dict(i=i - 1, dir=1, top=float(c.l[i]), bot=float(c.h[i - 2]))
        elif c.h[i] < c.l[i - 2] and c.l[i - 2] - c.h[i] >= min_atr * a[i]:
            f = dict(i=i - 1, dir=-1, top=float(c.l[i - 2]), bot=float(c.h[i]))
        else:
            continue
        al, ah = c.l[i + 1:], c.h[i + 1:]
        if len(al):
            if f["dir"] == 1 and al.min() <= f["bot"]:
                continue
            if f["dir"] == -1 and ah.max() >= f["top"]:
                continue
        out.append(f)
    return out


def order_blocks(c, events):
    out = []
    for e in events[-10:]:
        s, i = e["origin"], e["i"]
        if i - s < 2:
            continue
        if e["dir"] == 1:
            cand = [j for j in range(s, i) if c.c[j] < c.o[j]]
            if not cand:
                continue
            j = min(cand, key=lambda x: c.l[x])
            z = dict(i=j, dir=1, top=float(c.h[j]), bot=float(c.l[j]), ev=i)
            if len(c.c) > i + 1 and (c.c[i + 1:] < z["bot"]).any():
                continue
        else:
            cand = [j for j in range(s, i) if c.c[j] > c.o[j]]
            if not cand:
                continue
            j = max(cand, key=lambda x: c.h[x])
            z = dict(i=j, dir=-1, top=float(c.h[j]), bot=float(c.l[j]), ev=i)
            if len(c.c) > i + 1 and (c.c[i + 1:] > z["top"]).any():
                continue
        out.append(z)
    return out


def liquidity(c, sh, sl):
    """سقف/کف‌های برابر (EQH/EQL) که هنوز جارو نشده‌اند."""
    pools = {"hi": [], "lo": []}
    for key, sw, hi in (("hi", sh[-30:], True), ("lo", sl[-30:], False)):
        used = set()
        for a_i, (ia, pa) in enumerate(sw):
            if a_i in used:
                continue
            grp = [a_i]
            for b_i in range(a_i + 1, len(sw)):
                if abs(sw[b_i][1] - pa) / pa <= 0.0012:
                    grp.append(b_i)
            if len(grp) >= 2:
                used.update(grp)
                lvl = max(sw[g][1] for g in grp) if hi else min(sw[g][1] for g in grp)
                last = max(sw[g][0] for g in grp)
                after = c.h[last + 1:] if hi else c.l[last + 1:]
                swept = len(after) and ((after.max() > lvl) if hi else (after.min() < lvl))
                if not swept:
                    pools[key].append(dict(level=float(lvl), n=len(grp)))
    return pools


def sweeps(c, sh, sl, lookback=12, k=3):
    """جارو شدن نقدینگی: شکستِ سایه + بسته شدن برگشتی."""
    n = len(c.c)
    res = []
    for i in range(max(0, n - lookback), n):
        for j, p in sh[-12:]:
            if j + k < i and c.h[i] > p and c.c[i] < p:
                res.append(dict(i=i, dir=-1, level=p, kind="Sweep"))
                break
        for j, p in sl[-12:]:
            if j + k < i and c.l[i] < p and c.c[i] > p:
                res.append(dict(i=i, dir=1, level=p, kind="Sweep"))
                break
    return res


def analyze(c):
    a = atr(c)
    sh, sl = swings(c.h, c.l)
    events, trend = structure(c, sh, sl)
    return dict(
        c=c, atr=a, sh=sh, sl=sl, events=events, trend=trend,
        fvg=fvgs(c, a), ob=order_blocks(c, events), liq=liquidity(c, sh, sl),
        sweeps=sweeps(c, sh, sl),
        ema50=ema(c.c, 50), ema200=ema(c.c, 200), rsi=rsi(c.c),
    )


def range_pos(an):
    """موقعیت قیمت در رنج آخر: 0 کف، 1 سقف (زیر 0.5 = دیسکانت)."""
    if not an["sh"] or not an["sl"]:
        return 0.5
    H, L = an["sh"][-1][1], an["sl"][-1][1]
    if H <= L:
        return 0.5
    return float((an["c"].c[-1] - L) / (H - L))
