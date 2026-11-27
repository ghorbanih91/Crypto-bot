import argparse, time, traceback
from . import telegram as tg, jobs, panel, remote
from .util import load, save, load_settings, merge_defaults, log

INTERVALS = {"scan": 300, "news": 1800, "prices": 600, "daily": 300}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=55)
    args = ap.parse_args()
    if not tg.TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    S, state = load_settings(), load("state.json", {})
    def save_s():  # تغییر از پنل تلگرام: ذخیره محلی + ارسال به ریپو (تا پنل وب هم ببیند)
        S["_rev"] = time.time()
        save("settings.json", S)
        if remote.enabled():
            remote.put_settings(S)
    end = time.time() + args.minutes * 60
    last = state.setdefault("last", {})
    log.info("bot started; admins=%s channels=%d", tg.ADMINS, len(S["channels"]))
    last_remote = 0
    while time.time() < end:
        if remote.enabled() and time.time() - last_remote > 90:  # تغییرات پنل وب
            last_remote = time.time()
            R = remote.get_settings()
            if R and R.get("_rev", 0) > S.get("_rev", 0):
                S.clear(); S.update(merge_defaults(R)); save("settings.json", S)
                log.info("settings reloaded from repo")
        try:
            for u in tg.updates(state.get("offset", 0), timeout=20 if end - time.time() > 40 else 1):
                state["offset"] = u["update_id"] + 1
                try:
                    panel.handle(u, S, state, save_s)
                except Exception:
                    log.warning("panel: %s", traceback.format_exc())
        except Exception as e:
            log.warning("poll: %s", e); time.sleep(5)
        force = state.pop("force", [])
        tasks = [
            ("scan", lambda: jobs.job_scan(S, state), bool({"events", "signals"} & set(force))),
            ("news", lambda: jobs.job_news(S, state), "news" in force),
            ("prices", lambda: jobs.job_prices(S, state, "prices" in force), "prices" in force),
            ("daily", lambda: jobs.job_daily(S, state, "daily_analysis" in force), "daily_analysis" in force),
        ]
        for name, fn, forced in tasks:
            if forced or time.time() - last.get(name, 0) >= INTERVALS[name]:
                last[name] = time.time()
                try:
                    fn()
                except Exception:
                    log.warning("%s: %s", name, traceback.format_exc())
        save("state.json", state)
        save("settings.json", S)
    log.info("done")


if __name__ == "__main__":
    main()
