import html, json, os
import requests
from .util import log

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMINS = {int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()}


def api(method, files=None, timeout=60, **params):
    for k, v in list(params.items()):
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v, ensure_ascii=False)
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=params, files=files, timeout=timeout)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"{method}: {j.get('description')}")
    return j["result"]


esc = html.escape


def send(chat, text, markup=None):
    p = dict(chat_id=chat, text=text[:4000], parse_mode="HTML", disable_web_page_preview=True)
    if markup:
        p["reply_markup"] = markup
    return api("sendMessage", **p)


def send_photo(chat, path, caption=""):
    with open(path, "rb") as f:
        if len(caption) <= 1000:
            return api("sendPhoto", files={"photo": f}, chat_id=chat, caption=caption, parse_mode="HTML")
        api("sendPhoto", files={"photo": f}, chat_id=chat)
    return send(chat, caption)


def edit(chat, mid, text, markup=None):
    p = dict(chat_id=chat, message_id=mid, text=text, parse_mode="HTML")
    if markup:
        p["reply_markup"] = markup
    try:
        api("editMessageText", **p)
    except RuntimeError as e:
        if "not modified" not in str(e):
            log.warning("edit: %s", e)


def updates(offset, timeout=25):
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                      data=dict(offset=offset, timeout=timeout,
                                allowed_updates=json.dumps(["message", "callback_query", "my_chat_member"])),
                      timeout=timeout + 15)
    return r.json().get("result", [])
