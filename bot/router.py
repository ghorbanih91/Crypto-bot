from . import telegram as tg
from .events import add_event
from .util import log


def targets(S, feature):
    chans = list(S["channels"].keys())
    r = S["routes"].get(feature, ["all"])
    t = chans if "all" in r else [c for c in r if c in S["channels"]]
    return t or [str(a) for a in tg.ADMINS]


def publish(S, feature, text, image=None, etype=None, title="", symbol=None, data=None, plain=""):
    """ارسال به مقصدهای تنظیم‌شده + ثبت در فید اپ. اگر ویژگی خاموش باشد کاری نمی‌کند."""
    if not S["features"].get(feature, True):
        return False
    if S["features"].get("app_feed", True) and etype:
        add_event(etype, title, plain or text, symbol, data)
    for chat in targets(S, feature):
        try:
            if image:
                tg.send_photo(chat, image, text)
            else:
                tg.send(chat, text)
        except Exception as e:
            log.warning("send to %s failed: %s", chat, e)
    return True
