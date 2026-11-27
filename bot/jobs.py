import datetime as dt, itertools, time
from zoneinfo import ZoneInfo
from . import market, smc, signals as sg, chart, news, prices, llm
from .router import publish
from .telegram import esc
from .util import DATA, fmt, log

TEH = ZoneInfo("Asia/Tehran")
IMG = DATA / "img"
IMG.mkdir(exist_ok=True)
TFS = ("15m", "1H", "4H", "1D")
TF_FA = {"15m": "۱۵ دقیقه", "1H": "۱ ساعته", "4H": "۴ ساعته", "1D": "روزانه"}
NAME = {"BTC": "بیت‌کوین", "ETH": "اتریوم"}
TW = {1: "صعودی", -1: "نزولی", 0: "خنثی"}
RLM = "\u200f"   # علامت راست‌به‌چپ برای جلوگیری از به‌هم‌ریختگی فارسی/انگلیسی
_n = itertools.count()


def coin(sym):
    return sym.split("-")[0]


def rtl(lines):
    return "\n".join((RLM + l) if l else "" for l in lines)


def img(kind, sym, tf):
    return str(IMG / f"{kind}_{sym}_{tf}_{next(_n)}.png")


def wm(S):
    return S.get("texts", {}).get("watermark", "")


def load_all(sym):
    return {tf: smc.analyze(market.candles(sym, tf, 300)) for tf in TFS}


def sig_text(s, S):
    long_ = s["dir"] == 1
    TAGS = ("کلاسیک:", "ICT:", "RTM:")
    tagged = [w for w in s["why"] if w.startswith(TAGS)]
    other = [w for w in s["why"] if not w.startswith(TAGS) and not w.startswith("RSI") and not w.startswith("ناحیه")]
    reasons = other[:3] + tagged[:3]
    t = [f"{'🟢' if long_ else '🔴'} <b>سیگنال {'خرید' if long_ else 'فروش'} | #{coin(s['sym'])}USDT</b>",
         f"⏱ {TF_FA[s['tf']]}  ·  ⭐ کیفیت {s['score']} از {sg.MAX_SCORE}", "",
         f"📍 ورود: <code>{fmt(s['entry'])}</code>",
         f"🛑 حد ضرر: <code>{fmt(s['sl'])}</code>",
         f"🎯 هدف ۱: <code>{fmt(s['tp1'])}</code>",
         f"🎯 هدف ۲: <code>{fmt(s['tp2'])}</code>",
         f"⚖️ ریسک به ریوارد: <code>1:{s['rr2']:.1f}</code>", "",
         "📌 " + " • ".join(reasons)]
    d = S.get("texts", {}).get("disclaimer", "").strip()
    if d:
        t += ["", esc(d)]
    return rtl(t)


def _recent_events(an, bars=2):
    n = len(an["c"])
    return [e for e in an["events"] if e["i"] >= n - bars] + [e for e in an["sweeps"] if e["i"] >= n - bars]


def event_line(e):
    up = e["dir"] == 1
    lvl = f"<code>{fmt(e['level'])}</code>"
    if e["kind"] == "Sweep":
        return f"🧲 جارو شدن نقدینگی {'کف‌ها' if up else 'سقف‌ها'} در {lvl} — احتمال حرکت {'صعودی' if up else 'نزولی'}"
    name = "تغییر ساختار (CHoCH)" if e["kind"] == "CHoCH" else "شکست ساختار (BOS)"
    return f"{'🟢' if up else '🔴'} {name} {'صعودی' if up else 'نزولی'} — کندل {'بالای' if up else 'زیر'} {lvl}" + (" ⚠️" if e["kind"] == "CHoCH" else "")


def job_scan(S, state):
    mins = S["params"]
    first = "sent_events" not in state          # اولین اجرا: فقط وضعیت فعلی را ثبت کن، پیام نده
    sent = state.setdefault("sent_events", [])
    last_ev = state.setdefault("event_last", {})
    state.setdefault("signals", [])
    msgs = 0
    for sym in S["symbols"]:
        try:
            A = load_all(sym)
        except Exception as e:
            log.warning("load %s: %s", sym, e); continue
        # ردیابی سیگنال‌های باز
        for s in state["signals"]:
            if s["sym"] == sym and s.get("status", "open") in ("open", "tp1"):
                if sg.resolve(s, A[s["tf"]]["c"]):
                    names = {"sl": "❌ حد ضرر فعال شد", "tp1": "✅ هدف ۱ رسید — حد ضرر را روی ورود ببرید",
                             "tp2": "🏆 هدف ۲ رسید", "be": "➖ با سود هدف ۱ بسته شد", "expired": "⌛️ سیگنال منقضی شد"}
                    msg = rtl([names[s["status"]], f"#{coin(sym)}USDT · {TF_FA[s['tf']]} · {'خرید' if s['dir'] == 1 else 'فروش'} از <code>{fmt(s['entry'])}</code>"])
                    publish(S, "signals", msg, etype="signal_update", title=f"{coin(sym)} {s['status']}", symbol=sym, data=s, plain=msg)
        # رویدادهای چارت: یک پیام و یک تصویر برای هر تایم‌فریم
        for tf in (("4H", "1D", "1H") if S["features"].get("events", True) else ()):
            an, items = A[tf], []
            for e in _recent_events(an):
                key = f"{sym}|{tf}|{e['kind']}|{e['dir']}|{int(an['c'].t[e['i']])}"
                if key in sent:
                    continue
                sent.append(key)
                if not first:
                    items.append(e)
            seen_l, uniq = set(), []
            for e in items:                      # حذف موارد تکراری (همان سطح)
                kk = (e["kind"], e["dir"], round(e["level"], 1))
                if kk not in seen_l:
                    seen_l.add(kk); uniq.append(e)
            items = uniq
            state["sent_events"] = sent = sent[-500:]
            k = f"{sym}|{tf}"
            if not items or msgs >= 3 or time.time() - last_ev.get(k, 0) < market.TF_SEC[tf]:
                continue
            last_ev[k] = time.time(); msgs += 1
            lines = [f"🔔 <b>#{coin(sym)}USDT | تایم‌فریم {TF_FA[tf]}</b>"] + [event_line(e) for e in items]
            msg = rtl(lines)
            im = chart.draw(an, img("ev", sym, tf), f"{sym.replace('-', '/')} {tf}", watermark=wm(S))
            publish(S, "events", msg, image=im, etype="chart_event", title=f"{coin(sym)} {tf} " + "/".join(e["kind"] for e in items),
                    symbol=sym, data=dict(tf=tf, events=[dict(kind=e["kind"], dir=e["dir"], level=e["level"]) for e in items]), plain=msg)
        # سیگنال جدید
        keys = state.setdefault("sig_keys", {})
        for tf in (("15m", "1H") if S["features"].get("signals", True) else ()):
            s = sg.find_signal(sym, tf, A[tf], A["4H"], A["1D"], mins["min_rr"])
            if not s or s["score"] < mins["min_score"]:
                continue
            if sg.blocked(state["signals"], sym, s["dir"], tf):   # سیگنال قبلی هنوز به هدف/استاپ نخورده
                continue
            key = f"{sym}|{s['dir']}|{round(s['entry'] / (A[tf]['atr'][-1] * 3))}"
            if time.time() - keys.get(key, 0) < 6 * 3600:
                continue
            keys[key] = time.time()
            s["id"] = f"{int(time.time())}{coin(sym)}{tf}"
            state["signals"] = (state["signals"] + [s])[-300:]
            im = chart.draw(A[tf], img("sig", sym, tf), f"{sym.replace('-', '/')} {tf} — {'LONG' if s['dir'] == 1 else 'SHORT'} ({s['score']}/{sg.MAX_SCORE})", sig=s, watermark=wm(S))
            txt = sig_text(s, S)
            publish(S, "signals", txt, image=im, etype="signal", title=f"{coin(sym)} {tf} {'LONG' if s['dir'] == 1 else 'SHORT'}",
                    symbol=sym, data=s, plain=txt)
        state["sig_keys"] = {k: v for k, v in keys.items() if time.time() - v < 86400}


def _near(levels, price, above=True, k=2):
    return sorted({round(x, 2) for x in levels if (x > price) == above}, key=lambda x: abs(x - price))[:k]


def narrative(sym, price, chg, A):
    a1, a4 = A["1D"], A["4H"]
    nm = NAME.get(coin(sym), coin(sym))
    res = _near([p for _, p in a4["sh"][-10:]] + [x["level"] for x in a4["liq"]["hi"]], price, True)
    sup = _near([p for _, p in a4["sl"][-10:]] + [x["level"] for x in a4["liq"]["lo"]], price, False)
    p1 = f"قیمت {nm} در حدود {fmt(price)} دلار معامله می‌شود ({chg:+.1f}٪ در ۲۴ ساعت). روند روزانه {TW[a1['trend']]} و روند ۴ساعته {TW[a4['trend']]} است"
    if a4["events"]:
        e = a4["events"][-1]
        p1 += f"؛ آخرین رویداد ساختاری ۴ساعته، {'تغییر ساختار' if e['kind'] == 'CHoCH' else 'شکست ساختار'} {TW[e['dir']]} در {fmt(e['level'])} بوده است"
    p1 += f". RSI در ۴ساعته {a4['rsi'][-1]:.0f} است."
    p2 = []
    if res:
        p2.append(f"در سمت صعودی، نخستین مقاومت در {fmt(res[0])}" + (f" و سپس {fmt(res[1])}" if len(res) > 1 else "") + " قرار دارد؛ تثبیت بالای آن می‌تواند حرکت صعودی را تقویت کند.")
    if sup:
        p2.append(f"در سمت نزولی، حمایت مهم در {fmt(sup[0])}" + (f" و پس از آن {fmt(sup[1])}" if len(sup) > 1 else "") + " است؛ از دست رفتن آن احتمال ادامهٔ ریزش را بالا می‌برد.")
    eqh, eql = a4["liq"]["hi"][-1:], a4["liq"]["lo"][-1:]
    if eqh or eql:
        p2.append("نقدینگی (سقف/کف‌های برابر) " + " و ".join(([f"بالای {fmt(eqh[0]['level'])}"] if eqh else []) + ([f"زیر {fmt(eql[0]['level'])}"] if eql else [])) + " قرار دارد و می‌تواند هدف حرکت‌های بعدی باشد.")
    fv = [f for f in a4["fvg"] if abs((f["top"] + f["bot"]) / 2 - price) / price < 0.03]
    if fv:
        f = fv[0]
        p2.append(f"یک FVG باز {'صعودی' if f['dir'] == 1 else 'نزولی'} در محدودهٔ {fmt(f['bot'])} تا {fmt(f['top'])} دیده می‌شود که می‌تواند محل واکنش قیمت باشد.")
    if a1["trend"] == a4["trend"] == 1 and sup:
        p2.append(f"تا زمانی که قیمت بالای {fmt(sup[0])} بماند، سناریوی صعودی ارجح است.")
    elif a1["trend"] == a4["trend"] == -1 and res:
        p2.append(f"تا زمانی که قیمت زیر {fmt(res[0])} بماند، سناریوی نزولی ارجح است.")
    else:
        p2.append("ساختار روزانه و ۴ساعته هم‌جهت نیست؛ صبر برای تأیید بهتر است.")
    text = p1 + "\n\n" + " ".join(p2)
    pol = llm.ask("متن تحلیل زیر را به یک تحلیل روان، محتاطانه و حرفه‌ای فارسی در دو پاراگراف کوتاه (حداکثر ۱۳۰ کلمه) بازنویسی کن. "
                  "فقط از همین اعداد استفاده کن، عدد جدید نساز، توصیهٔ مالی نکن و فقط متن نهایی را بنویس.\n\n" + text)
    return (pol if pol and len(pol) > 80 else text), res, sup


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
        text, res, sup = narrative(sym, price, chg, A)
        lines = [f"📊 <b>تحلیل روزانه #{coin(sym)}USDT</b>", ""]
        lines += [esc(x) if x else "" for x in text.split("\n")]
        if res or sup:
            lines.append("")
            if res: lines.append("🔺 مقاومت: " + " ، ".join(f"<code>{fmt(x)}</code>" for x in res))
            if sup: lines.append("🔻 حمایت: " + " ، ".join(f"<code>{fmt(x)}</code>" for x in sup))
        msg = rtl(lines)
        im = chart.draw(A["4H"], img("daily", sym, "4H"), f"{sym.replace('-', '/')} 4H", watermark=wm(S))
        publish(S, "daily_analysis", msg, image=im, etype="daily_analysis", title=f"تحلیل روزانه {coin(sym)}",
                symbol=sym, data=dict(price=price, trend_1d=A["1D"]["trend"], trend_4h=A["4H"]["trend"]), plain=msg)


def job_news(S, state):
    p = S["params"]
    seen = state.setdefault("news_seen", [])
    for it in news.pick(seen, p["news_min_importance"], p["news_max_per_run"]):
        fa = it.get("fa")
        if fa:
            msg = rtl([f"📰 <b>{esc(fa['title_fa'])}</b>", "", esc(fa['summary_fa']), "", f"🔗 <a href=\"{esc(it['link'])}\">منبع خبر</a>"])
        else:
            msg = f"📰 <b>{esc(it['title'])}</b>\n\n" + rtl(["(ترجمهٔ فارسی نیاز به GEMINI_API_KEY دارد)", f"🔗 <a href=\"{esc(it['link'])}\">منبع خبر</a>"])
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
    msg = rtl(t)
    publish(S, "prices", msg, etype="prices", title="قیمت تتر و طلا", data=dict(usdt=usdt, gold18=gold, src=src), plain=msg)
    state.update(price_ref=dict(usdt=usdt, gold=gold), price_date=now.strftime("%Y-%m-%d"), price_ts=time.time())
