"""همگام‌سازی تنظیمات با پنل وب از طریق فایل data/settings.json در ریپو (با فیلد _rev)."""
import base64, json, os
import requests
from .util import log

API = "https://api.github.com/repos/{}/contents/data/settings.json"


def _h(raw=False):
    h = {"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return h


def enabled():
    return bool(os.environ.get("GITHUB_REPOSITORY") and os.environ.get("GITHUB_TOKEN"))


def get_settings():
    try:
        r = requests.get(API.format(os.environ["GITHUB_REPOSITORY"]), headers=_h(True), timeout=20)
        return r.json() if r.ok else None
    except Exception as e:
        log.warning("remote get: %s", e)
        return None


def put_settings(S):
    """تغییرات پنل تلگرام را به ریپو می‌فرستد تا پنل وب هم ببیند."""
    url = API.format(os.environ["GITHUB_REPOSITORY"])
    try:
        sha = None
        r = requests.get(url, headers=_h(), timeout=20)
        if r.ok:
            sha = r.json().get("sha")
        body = {"message": "settings (telegram panel)",
                "content": base64.b64encode(json.dumps(S, ensure_ascii=False, indent=1).encode()).decode()}
        if sha:
            body["sha"] = sha
        requests.put(url, headers=_h(), json=body, timeout=20)
    except Exception as e:
        log.warning("remote put: %s", e)
