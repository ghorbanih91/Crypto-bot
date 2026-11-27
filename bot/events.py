"""فید رویدادها برای اپ (data/events.json). اپ می‌تواند این فایل را بخواند."""
import time, uuid
from .util import load, save

MAX = 500


def add_event(etype, title, text, symbol=None, data=None):
    ev = load("events.json", [])
    e = dict(id=uuid.uuid4().hex[:10], ts=int(time.time()), type=etype, symbol=symbol, title=title, text=text, data=data or {})
    ev.append(e)
    save("events.json", ev[-MAX:])
    return e
