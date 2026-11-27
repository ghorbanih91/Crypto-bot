"""پنل مدیریت داخل تلگرام (دکمه‌های شیشه‌ای) + دستورات."""
import json
from . import telegram as tg
from .signals import stats
from .util import FEATURES, DEFAULT_SETTINGS, TEXT_KEYS, save, log

ROUTABLE = list(FEATURES)


def kb(rows):
    return {"inline_keyboard": rows}


def main_menu(S):
    rows = []
    for k, name in FEATURES.items():
        on = S["features"].get(k, True)
        rows.append([{"text": f"{'✅' if on else '⛔️'} {name}", "callback_data": f"t:{k}"},
                     {"text": "📍 مقصد", "callback_data": f"r:{k}"}])
    rows.append([{"text": f"{'✅' if S['features'].get('app_feed', True) else '⛔️'} 📱 فید اپ", "callback_data": "t:app_feed"}])
    rows.append([{"text": "📡 کانال‌ها", "callback_data": "ch"}, {"text": "📈 آمار سیگنال‌ها", "callback_data": "st"}])
    rows.append([{"text": "⚙️ پارامترها", "callback_data": "pm"}, {"text": "▶️ اجرای فوری", "callback_data": "run"}])
    return "🎛 <b>پنل مدیریت بات</b>\nروی هر گزینه بزنید تا روشن/خاموش شود.", kb(rows)


def route_menu(S, feat):
    r = S["routes"].get(feat, ["all"])
    rows = [[{"text": f"{'✅' if 'all' in r else '▫️'} همهٔ کانال‌ها", "callback_data": f"ra:{feat}"}]]
    for cid, title in S["channels"].items():
        rows.append([{"text": f"{'✅' if cid in r else '▫️'} {title}", "callback_data": f"rc:{feat}:{cid}"}])
    rows.append([{"text": "⬅️ بازگشت", "callback_data": "home"}])
    return f"📍 مقصد «{FEATURES[feat]}»\nیک یا چند کانال انتخاب کنید:", kb(rows)


def channels_menu(S):
    rows = [[{"text": f"🗑 حذف {t}", "callback_data": f"cd:{c}"}] for c, t in S["channels"].items()]
    rows.append([{"text": "⬅️ بازگشت", "callback_data": "home"}])
    txt = "📡 <b>کانال‌های ثبت‌شده</b>\n" + ("\n".join(f"• {t} (<code>{c}</code>)" for c, t in S["channels"].items()) or "هنوز کانالی ثبت نشده.")
    txt += "\n\nبرای افزودن: بات را در کانال <b>ادمین</b> کنید (خودکار ثبت می‌شود) یا بنویسید:\n<code>/addchannel @username</code>"
    return txt, kb(rows)


def params_text(S):
    lines = [f"<code>{k}</code> = {v}" for k, v in S["params"].items()]
    tl = [f"<code>{k}</code> ({n}) = {tg.esc(str(S['texts'].get(k, '')) or '—')}" for k, n in TEXT_KEYS.items()]
    return ("⚙️ <b>پارامترها</b>\n" + "\n".join(lines) + "\n\n✏️ <b>متن‌ها</b>\n" + "\n".join(tl) +
            "\n\nتغییر عدد: <code>/set نام مقدار</code> (مثال: <code>/set min_score 11</code>)\n"
            "تغییر متن: <code>/text نام متن</code> (مثال: <code>/text tag_signals #سیگنال #بیتکوین</code>)\nبرای پاک کردن: <code>/text نام -</code>",
            kb([[{"text": "⬅️ بازگشت", "callback_data": "home"}]]))


def stats_text(state):
    s = stats(state.get("signals", []))
    return (f"📈 <b>آمار سیگنال‌ها</b>\nکل: {s['total']} | برد: {s['wins']} | باخت: {s['losses']} | باز: {s['open']}\n"
            f"وین‌ریت: {s['winrate']:.0f}% | میانگین R: {s['avg_r']:+.2f}")


def handle(u, S, state, save_settings):
    """یک آپدیت تلگرام را پردازش می‌کند."""
    if "my_chat_member" in u:
        m = u["my_chat_member"]; chat = m["chat"]
        if chat["type"] in ("channel", "supergroup", "group"):
            cid = str(chat["id"])
            if m["new_chat_member"]["status"] in ("administrator", "member"):
                S["channels"][cid] = chat.get("title", cid); save_settings()
                for a in tg.ADMINS:
                    try: tg.send(a, f"✅ کانال «{tg.esc(chat.get('title', cid))}» ثبت شد.")
                    except Exception: pass
            elif m["new_chat_member"]["status"] in ("left", "kicked"):
                S["channels"].pop(cid, None)
                for k in S["routes"]:
                    S["routes"][k] = [x for x in S["routes"][k] if x != cid] or ["all"]
                save_settings()
        return

    if "callback_query" in u:
        q = u["callback_query"]; uid = q["from"]["id"]
        if uid not in tg.ADMINS:
            return tg.api("answerCallbackQuery", callback_query_id=q["id"], text="دسترسی ندارید")
        chat, mid, d = q["message"]["chat"]["id"], q["message"]["message_id"], q["data"]
        tg.api("answerCallbackQuery", callback_query_id=q["id"])
        parts = d.split(":", 2)
        a = parts[0]
        if a == "t":
            S["features"][parts[1]] = not S["features"].get(parts[1], True)
        elif a == "ra":
            S["routes"][parts[1]] = ["all"]
        elif a == "rc":
            r = [x for x in S["routes"].get(parts[1], []) if x != "all"]
            r = [x for x in r if x != parts[2]] if parts[2] in r else r + [parts[2]]
            S["routes"][parts[1]] = r or ["all"]
        elif a == "cd":
            S["channels"].pop(parts[1], None)
            for k in S["routes"]:
                S["routes"][k] = [x for x in S["routes"][k] if x != parts[1]] or ["all"]
        elif a == "run":
            state["force"] = list(FEATURES)
            tg.send(chat, "▶️ همهٔ بخش‌ها در چرخهٔ بعدی (چند ثانیه دیگر) اجرا می‌شوند.")
        save_settings()
        if a == "r":
            txt, mk = route_menu(S, parts[1])
        elif a == "rc" or a == "ra":
            txt, mk = route_menu(S, parts[1])
        elif a in ("ch", "cd"):
            txt, mk = channels_menu(S)
        elif a == "pm":
            txt, mk = params_text(S)
        elif a == "st":
            txt, mk = stats_text(state), kb([[{"text": "⬅️ بازگشت", "callback_data": "home"}]])
        else:
            txt, mk = main_menu(S)
        return tg.edit(chat, mid, txt, mk)

    m = u.get("message")
    if not m or "text" not in m:
        return
    uid, chat, text = m["from"]["id"], m["chat"]["id"], m["text"].strip()
    if m["chat"]["type"] != "private":
        return
    cmd = text.split()[0].split("@")[0].lower()
    if cmd in ("/start", "/id") and uid not in tg.ADMINS:
        return tg.send(chat, f"شناسه عددی شما: <code>{uid}</code>\nاین عدد را در تنظیمات ADMIN_IDS قرار دهید تا بتوانید بات را مدیریت کنید.")
    if uid not in tg.ADMINS:
        return
    if cmd in ("/start", "/panel", "/menu"):
        txt, mk = main_menu(S); tg.send(chat, txt, mk)
    elif cmd == "/stats":
        tg.send(chat, stats_text(state))
    elif cmd == "/addchannel" and len(text.split()) > 1:
        ref = text.split()[1]
        try:
            info = tg.api("getChat", chat_id=ref)
            S["channels"][str(info["id"])] = info.get("title", ref); save_settings()
            tg.send(chat, f"✅ «{tg.esc(info.get('title', ref))}» ثبت شد. (مطمئن شوید بات در آن ادمین است)")
        except Exception as e:
            tg.send(chat, f"❌ نشد: {tg.esc(str(e))}\nبات باید در کانال ادمین باشد.")
    elif cmd == "/text":
        parts = text.split(None, 2)
        if len(parts) < 2 or parts[1] not in TEXT_KEYS:
            return tg.send(chat, "نام‌های مجاز:\n" + "\n".join(f"<code>{k}</code> — {n}" for k, n in TEXT_KEYS.items()))
        S["texts"][parts[1]] = "" if len(parts) < 3 or parts[2].strip() == "-" else parts[2].strip()
        save_settings(); tg.send(chat, f"✅ {parts[1]} ذخیره شد.")
    elif cmd == "/set" and len(text.split()) == 3:
        k, v = text.split()[1:]
        if k not in S["params"]:
            return tg.send(chat, "پارامتر نامعتبر. لیست: /panel ← پارامترها")
        try:
            S["params"][k] = type(DEFAULT_SETTINGS["params"][k])(float(v) if "." in v else int(v))
            save_settings(); tg.send(chat, f"✅ {k} = {S['params'][k]}")
        except ValueError:
            tg.send(chat, "مقدار باید عدد باشد.")
