"""همگام‌سازی settings.json با ریپوی گیت‌هاب (برای پنل وب). فقط داخل GitHub Actions فعال است."""
import base64, json, os
import requests
from .util import log

REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
URL = f"https://api.github.com/repos/{REPO}/contents/data/settings.json"


def enabled():
    return bool(REPO and TOKEN)


def _h():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}


def get_settings():
    try:
        r = requests.get(URL, params={"ref": BRANCH}, headers=_h(), timeout=20)
        if r.status_code != 200:
            return None
        return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except Exception as e:
        log.warning("remote get: %s", e)
        return None


def put_settings(S):
    try:
        r = requests.get(URL, params={"ref": BRANCH}, headers=_h(), timeout=20)
        body = {"message": "settings update (bot)", "branch": BRANCH,
                "content": base64.b64encode(json.dumps(S, ensure_ascii=False, indent=1).encode("utf-8")).decode()}
        if r.status_code == 200:
            body["sha"] = r.json()["sha"]
        r = requests.put(URL, headers=_h(), json=body, timeout=20)
        if r.status_code not in (200, 201):
            log.warning("remote put: %s %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("remote put: %s", e)
