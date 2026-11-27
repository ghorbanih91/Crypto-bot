import os
import requests
from .util import log

GEMINI = os.environ.get("GEMINI_API_KEY", "")
GMODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CLAUDE = os.environ.get("ANTHROPIC_API_KEY", "")
CMODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")


def ask(prompt, max_tokens=500):
    """متن آزاد از Gemini یا Claude؛ بدون کلید None."""
    if GEMINI:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GMODEL}:generateContent",
                              headers={"x-goog-api-key": GEMINI, "content-type": "application/json"},
                              json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            log.warning("gemini: %s", e)
    if CLAUDE:
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": CLAUDE, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                              json={"model": CMODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}, timeout=60)
            return r.json()["content"][0]["text"].strip()
        except Exception as e:
            log.warning("claude: %s", e)
    return None
