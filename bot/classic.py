"""ابزارهای سبک کلاسیک: حمایت/مقاومت و خط روند."""
import numpy as np


def sr_levels(an, tol=0.0015, min_touch=3):
    pts = sorted([p for _, p in an["sh"][-40:]] + [p for _, p in an["sl"][-40:]])
    out, i = [], 0
    while i < len(pts):
        grp, j = [pts[i]], i + 1
        while j < len(pts) and (pts[j] - grp[0]) / grp[0] <= tol:
            grp.append(pts[j]); j += 1
        if len(grp) >= min_touch:
            out.append(float(np.mean(grp)))
        i = j
    return out


def trendline(an, d):
    """خط روند صعودی (از کف‌ها) برای d=1 و نزولی (از سقف‌ها) برای d=-1؛ اگر شکسته شده باشد None."""
    sw = an["sl"] if d == 1 else an["sh"]
    if len(sw) < 2:
        return None
    (i1, p1), (i2, p2) = sw[-2], sw[-1]
    if i2 == i1 or (d == 1 and p2 <= p1) or (d == -1 and p2 >= p1):
        return None
    slope = (p2 - p1) / (i2 - i1)
    c, n = an["c"], len(an["c"])
    line = p2 + slope * (np.arange(i2, n) - i2)
    cl = c.c[i2:]
    if ((cl < line).any() if d == 1 else (cl > line).any()):
        return None
    return dict(i1=int(i1), p1=float(p1), i2=int(i2), p2=float(p2), y=float(line[-1]))
