import time
from . import telegram as tg
from .events import add_event
from .util import log

OUTBOX = []          # صف ارسال: پیام‌ها پشت سر هم و با فاصله فرستاده می‌شوند
_last_send = [0.0]


def targets(S, feature):
    chans = list(S["channels"].keys())
    r = S["routes"].get(feature, ["all"])
    t = chans if "all" in r else [c for c in r if c in S["channels"]]
    return t or [str(a) for a in tg.ADMINS]


def decorate(S, feature, text):
    """هشتگ و امضای قابل تنظیم را به انتهای پیام اضافه می‌کند."""
    t = S.get("texts", {})
    extra = [tg.esc(x.strip()) for x in (t.get("tag_" + feature, ""), t.get("footer", "")) if x and x.strip()]
    return text + ("\n\n" + "\n".join(extra) if extra else "")


def publish(S, feature, text, image=None, etype=None, title="", symbol=None, data=None, plain=""):
    """پیام را در صف می‌گذارد (و در فید اپ ثبت می‌کند). اگر ویژگی خاموش باشد کاری نمی‌کند."""
    if not S["features"].get(feature, True):
        return False
    if S["features"].get("app_feed", True) and etype:
        add_event(etype, title, plain or text, symbol, data)
    text = decorate(S, feature, text)
    for chat in targets(S, feature):
        OUTBOX.append(dict(chat=chat, text=text, image=image))
    return True


def drain(gap, flush=False, max_wait=240):
    """یک پیام از صف می‌فرستد (یا اگر flush باشد، همه را با فاصله)."""
    t0 = time.time()
    while OUTBOX:
        wait = gap - (time.time() - _last_send[0])
        if wait > 0:
            if not flush or time.time() - t0 + wait > max_wait:
                return
            time.sleep(wait)
        m = OUTBOX.pop(0)
        _last_send[0] = time.time()
        try:
            if m["image"]:
                tg.send_photo(m["chat"], m["image"], m["text"])
            else:
                tg.send(m["chat"], m["text"])
        except Exception as e:
            log.warning("send to %s failed: %s", m["chat"], e)
        if not flush:
            return
