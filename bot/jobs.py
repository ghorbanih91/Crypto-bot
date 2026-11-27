import datetime as dt, time
from zoneinfo import ZoneInfo
from . import market, smc, signals as sg, chart, news, prices
from .router import publish
from .telegram import esc
from .util import DATA, fmt, log

TEH = ZoneInfo("Asia/Tehran")
IMG = DATA / "img"
IMG.mkdir(exist_ok=True)
TFS = ("15m", "1H", "4H", "1D")
DIS = {"1D": "روزانه", "4H": "۴ساعته", "1H": "۱ساعته", "15m": "۱۵دقیقه‌ای"}
TREND = {1: "صعودی 🟢", -1: "نزولی 🔴", 0: "نامشخص ⚪️"}


def pair(sym):
    return sym.replace("-", "/")


def load_all(sym):
    return {tf: smc.analyze(market.candles(sym, tf, 300)) for tf in TFS}


def sig_text(s, head=None):
    long_ = s["dir"] == 1
    t = [head or f"{'🟢 سیگنال خرید (LONG)' if long_ else '🔴 سیگنال فروش (SHORT)'} — <b>{pair(s['sym'])}</b>",
         f"⏱ تایم‌فریم: {s['tf']} | ⭐️ کیفیت: {s['score']}/{sg.MAX_SCORE}", "",
         f"📍 ورود: <code>{fmt(s['entry'])}</code>",
         f"🛑 حد ضرر: <code>{fmt(s['sl'])}</code>",
         f"🎯 هدف ۱: <code>{fmt(s['tp1'])}</code> (R {s['rr1']:.1f})",
         f"🎯 هدف ۲: <code>{fmt(s['tp2'])}</code> (R {s['rr2']:.1f})",
         f"⚖️ ریسک به ریوارد: 1:{s['rr2']:.1f}", "", "🔍 دلایل:"]
    t += [f"• {w}" for w in s["why"]]
    t += ["", "💡 پس از هدف ۱ نیمی از پوزیشن را ببندید و حد ضرر را روی ورود بگذارید.",
          "⚠️ توصیهٔ مالی نیست. ریسک هر معامله حداکثر ۱٪ سرمایه."]
    return "\n".join(t)


def _recent_events(an, bars=2):
    c = an["c"]; n = len(c)
    out = [e for e in an["events"] if e["i"] >= n - bars]
    out += [e for e in an["sweeps"] if e["i"] >= n - bars]
    return out


def job_scan(S, state):
    mins = S["params"]
    for sym in S["symbols"]:
        try:
            A = load_all(sym)
        except Exception as e:
            log.warning("load %s: %s", sym, e); continue
        # ردیابی سیگنال‌های باز
        for s in state.setdefault("signals", []):
            if s["sym"] == sym and s.get("status", "open") in ("open", "tp1"):
                if sg.resolve(s, A[s["tf"]]["c"]):
                    names = {"sl": "❌ حد ضرر خورد", "tp1": "✅ هدف ۱ رسید (حد ضرر را روی ورود بگذارید)",
                             "tp2": "🏆 هدف ۲ رسید", "be": "➖ با سود هدف ۱ بسته شد (حد ضرر در ورود)", "expired": "⌛️ منقضی شد"}
                    publish(S, "signals", f"{names[s['status']]}\n{pair(sym)} {s['tf']} {'LONG' if s['dir'] == 1 else 'SHORT'} @ {fmt(s['entry'])}",
                            etype="signal_update", title=f"{pair(sym)} {s['status']}", symbol=sym, data=s)
        # رویدادهای چارت
        for tf in (("1H", "4H", "1D") if S["features"].get("events", True) else ()):
            an = A[tf]
            for e in _recent_events(an):
                key = f"{sym}|{tf}|{e['kind']}|{e['dir']}|{int(an['c'].t[e['i']])}"
                if key in state.setdefault("sent_events", []):
                    continue
                state["sent_events"] = (state["sent_events"] + [key])[-400:]
                up = e["dir"] == 1
                if e["kind"] == "Sweep":
                    msg = f"🧲 جارو شدن نقدینگی {'کف‌ها' if up else 'سقف‌ها'} در {pair(sym)} ({tf})\nسطح: {fmt(e['level'])} — برگشت قیمت، احتمال حرکت {'صعودی' if up else 'نزولی'}"
                else:
                    msg = (f"{'🟢' if up else '🔴'} <b>{e['kind']} {'صعودی' if up else 'نزولی'}</b> — {pair(sym)} ({tf})\n"
                           f"بسته شدن کندل {'بالای' if up else 'زیر'} {fmt(e['level'])}")
                    if e["kind"] == "CHoCH":
                        msg += "\n⚠️ تغییر ساختار (شروع احتمالی تغییر روند)"
                img = chart.draw(an, IMG / f"ev_{sym}_{tf}.png", f"{pair(sym)} {tf} — {e['kind']}")
                publish(S, "events", msg, image=str(img), etype="chart_event", title=f"{pair(sym)} {tf} {e['kind']}",
                        symbol=sym, data=dict(tf=tf, kind=e["kind"], dir=e["dir"], level=e["level"]), plain=msg)
        # سیگنال جدید
        keys = state.setdefault("sig_keys", {})
        for tf in (("15m", "1H") if S["features"].get("signals", True) else ()):
            s = sg.find_signal(sym, tf, A[tf], A["4H"], A["1D"], mins["min_rr"])
            if not s or s["score"] < mins["min_score"]:
                continue
            key = f"{sym}|{s['dir']}|{round(s['entry'] / (A[tf]['atr'][-1] * 3))}"
            if time.time() - keys.get(key, 0) < 6 * 3600:
                continue
            keys[key] = time.time()
            s["id"] = f"{int(time.time())}{sym[:3]}{tf}"
            state["signals"].append(s)
            state["signals"] = state["signals"][-300:]
            img = chart.draw(A[tf], IMG / f"sig_{sym}_{tf}.png", f"{pair(sym)} {tf} — {'LONG' if s['dir'] == 1 else 'SHORT'} (score {s['score']})", sig=s)
            publish(S, "signals", sig_text(s), image=str(img), etype="signal", title=f"{pair(sym)} {tf} {'LONG' if s['dir'] == 1 else 'SHORT'}",
                    symbol=sym, data=s, plain=sig_text(s))
        state["sig_keys"] = {k: v for k, v in keys.items() if time.time() - v < 86400}


def _near(levels, price, above=True, k=2):
    ls = sorted({round(x, 2) for x in levels if (x > price) == above}, key=lambda x: abs(x - price))[:k]
    return ls


def job_daily(S, state, force=False):
    now = dt.datetime.now(TEH)
    today = now.strftime("%Y-%m-%d")
    if not force and (now.hour < S["params"]["daily_hour"] or state.get("daily_date") == today):
        return
    state["daily_date"] = today
    for sym in S["symbols"]:
        try:
            A = load_all(sym)
            price, chg = market.last_price(sym)
        except Exception as e:
            log.warning("daily %s: %s", sym, e); continue
        a4, a1 = A["4H"], A["1D"]
        res = _near([p for _, p in a4["sh"][-10:]] + [x["level"] for x in a4["liq"]["hi"]], price, True)
        sup = _near([p for _, p in a4["sl"][-10:]] + [x["level"] for x in a4["liq"]["lo"]], price, False)
        t = [f"📊 <b>تحلیل روزانه {pair(sym)}</b>", f"💰 قیمت: <code>{fmt(price)}</code> ({chg:+.1f}٪ در ۲۴ساعت)", "",
             f"📈 روند روزانه: {TREND[a1['trend']]}", f"📈 روند ۴ساعته: {TREND[a4['trend']]}"]
        if a4["events"]:
            e = a4["events"][-1]
            t.append(f"🧱 آخرین ساختار ۴ساعته: {e['kind']} {'صعودی' if e['dir'] == 1 else 'نزولی'} در {fmt(e['level'])}")
        t.append(f"📉 RSI(4H): {a4['rsi'][-1]:.0f} | EMA50 {'بالای' if a4['ema50'][-1] > a4['ema200'][-1] else 'زیر'} EMA200")
        if res: t.append("🔺 مقاومت: " + " ، ".join(fmt(x) for x in res))
        if sup: t.append("🔻 حمایت: " + " ، ".join(fmt(x) for x in sup))
        liq = [f"EQH {fmt(x['level'])}" for x in a4["liq"]["hi"][-2:]] + [f"EQL {fmt(x['level'])}" for x in a4["liq"]["lo"][-2:]]
        if liq: t.append("🧲 نقدینگی: " + " | ".join(liq))
        fv = [f for f in a4["fvg"] if abs((f["top"] + f["bot"]) / 2 - price) / price < 0.03]
        if fv: t.append("🕳 FVG باز نزدیک: " + " | ".join(f"{'↑' if f['dir'] == 1 else '↓'} {fmt(f['bot'])}-{fmt(f['top'])}" for f in fv[:3]))
        t.append("")
        if res: t.append(f"🟢 سناریو صعودی: تثبیت بالای {fmt(res[0])} ← هدف {fmt(res[1]) if len(res) > 1 else 'سقف بعدی'}")
        if sup: t.append(f"🔴 سناریو نزولی: بسته شدن زیر {fmt(sup[0])} ← هدف {fmt(sup[1]) if len(sup) > 1 else 'کف بعدی'}")
        t.append("\n⚠️ توصیهٔ مالی نیست.")
        img = chart.draw(a4, IMG / f"daily_{sym}.png", f"{pair(sym)} 4H")
        publish(S, "daily_analysis", "\n".join(t), image=str(img), etype="daily_analysis", title=f"تحلیل روزانه {pair(sym)}",
                symbol=sym, data=dict(price=price, trend_1d=a1["trend"], trend_4h=a4["trend"]), plain="\n".join(t))


def job_news(S, state):
    p = S["params"]
    seen = state.setdefault("news_seen", [])
    for it in news.pick(seen, p["news_min_importance"], p["news_max_per_run"]):
        fa = it.get("fa")
        if fa:
            msg = f"📰 <b>{esc(fa['title_fa'])}</b>\n\n{esc(fa['summary_fa'])}\n\n🔗 <a href=\"{esc(it['link'])}\">منبع</a>"
        else:
            msg = f"📰 <b>{esc(it['title'])}</b>\n(ترجمهٔ فارسی نیاز به ANTHROPIC_API_KEY دارد)\n\n🔗 <a href=\"{esc(it['link'])}\">منبع</a>"
        publish(S, "news", msg, etype="news", title=(fa or it).get("title_fa", it["title"]), data=dict(link=it["link"]), plain=msg)
    state["news_seen"] = seen[-300:]


def job_prices(S, state, force=False):
    p = S["params"]
    usdt, src = prices.usdt_toman()
    if not usdt:
        return
    gold = prices.gold18_toman(usdt, p["gold_adjust_pct"])
    now = dt.datetime.now(TEH)
    ref = state.get("price_ref")
    reason = None
    if force:
        reason = "درخواست دستی"
    elif now.hour >= p["price_hour"] and state.get("price_date") != now.strftime("%Y-%m-%d"):
        reason = "گزارش روزانه"
    elif p["price_every_hours"] and time.time() - state.get("price_ts", 0) >= p["price_every_hours"] * 3600:
        reason = "گزارش دوره‌ای"
    elif ref:
        mv = max(abs(usdt / ref["usdt"] - 1), abs(gold / ref["gold"] - 1) if gold and ref.get("gold") else 0) * 100
        if mv >= p["price_move_pct"]:
            reason = f"حرکت شدید ({mv:.1f}٪)"
    if not reason:
        return
    chg = lambda a, b: f" ({(a / b - 1) * 100:+.1f}٪)" if b else ""
    t = [f"💵 <b>قیمت‌ها</b> — {reason}", f"💲 تتر: <code>{usdt:,.0f}</code> تومان{chg(usdt, ref['usdt']) if ref else ''}"]
    if gold:
        t.append(f"🥇 طلای ۱۸ عیار: <code>{gold:,.0f}</code> تومان/گرم (تخمینی){chg(gold, ref.get('gold')) if ref else ''}")
    publish(S, "prices", "\n".join(t), etype="prices", title="قیمت تتر و طلا", data=dict(usdt=usdt, gold18=gold, src=src), plain="\n".join(t))
    state.update(price_ref=dict(usdt=usdt, gold=gold), price_date=now.strftime("%Y-%m-%d"), price_ts=time.time())
