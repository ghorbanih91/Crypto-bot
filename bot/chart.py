import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .util import fmt

BG, FG, UP, DN = "#0f1520", "#c8d1e0", "#26a69a", "#ef5350"


def _shape(t):
    try:  # برای واترمارک فارسی (اگر کتابخانه‌ها نصب باشند)
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(t))
    except Exception:
        return t


def _spread(items, ylo, yhi, gap):
    """جلوگیری از روی هم افتادن برچسب‌ها: (y, text, color) → موقعیت‌های جدید."""
    items = sorted(items, key=lambda x: x[0])
    pos = []
    for y, *_ in items:
        pos.append(y if not pos else max(y, pos[-1] + gap))
    over = pos[-1] - yhi if pos else 0
    if over > 0:
        pos = [p - over for p in pos]
        for i in range(len(pos) - 2, -1, -1):
            pos[i] = min(pos[i], pos[i + 1] - gap)
    return [(p, it) for p, it in zip(pos, items)]


def draw(an, path, title, sig=None, n=90, watermark=""):
    c = an["c"]
    N = len(c)
    s = max(0, N - n)
    price = float(c.c[-1])
    lo0, hi0 = c.l[s:].min(), c.h[s:].max()
    ys0 = [lo0, hi0] + ([sig["sl"], sig["tp2"]] if sig else [])
    pad0 = (max(ys0) - min(ys0)) * 0.05
    ylo, yhi = min(ys0) - pad0, max(ys0) + pad0
    inside = lambda y: ylo <= y <= yhi
    W, M = N - s, 17

    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=110)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for i in range(s, N):
        x = i - s
        col = UP if c.c[i] >= c.o[i] else DN
        ax.vlines(x, c.l[i], c.h[i], color=col, lw=0.8)
        ax.add_patch(Rectangle((x - 0.32, min(c.o[i], c.c[i])), 0.64, max(abs(c.c[i] - c.o[i]), 1e-9), color=col))

    labels = []  # (y, text, color) → در حاشیهٔ راست
    near = lambda lst, f: sorted([z for z in lst if inside(z["top"]) and inside(z["bot"]) and z["i"] >= s - 30],
                                 key=lambda z: abs((z["top"] + z["bot"]) / 2 - price))[:f]
    for f in near(an["fvg"], 3):
        x0 = max(0, f["i"] - s)
        col = UP if f["dir"] == 1 else DN
        ax.add_patch(Rectangle((x0, f["bot"]), W - x0, f["top"] - f["bot"], color=col, alpha=0.16, lw=0))
        labels.append(((f["top"] + f["bot"]) / 2, "FVG", col))
    for z in near(an["ob"], 2):
        x0 = max(0, z["i"] - s)
        ax.add_patch(Rectangle((x0, z["bot"]), W - x0, z["top"] - z["bot"], facecolor="none", edgecolor="#f0b90b", lw=1, ls="--"))
        labels.append(((z["top"] + z["bot"]) / 2, "OB", "#f0b90b"))
    pools = [(p["level"], "EQH") for p in an["liq"]["hi"] if inside(p["level"])] + \
            [(p["level"], "EQL") for p in an["liq"]["lo"] if inside(p["level"])]
    for lvl, lab in sorted(pools, key=lambda x: abs(x[0] - price))[:2]:
        ax.hlines(lvl, 0, W, color="#b388ff", lw=0.8, ls="-.", alpha=0.8)
        labels.append((lvl, lab, "#b388ff"))
    # ساختار بازار: فقط ۳ رویداد آخر، بدون هم‌پوشانی
    last_x = -99
    for e in [e for e in an["events"] if e["i"] >= s][-3:]:
        x = e["i"] - s
        ax.hlines(e["level"], max(0, x - 14), x, color="#8ab4f8", lw=0.9, ls=":")
        if x - last_x >= 9 and inside(e["level"]):
            dy = (yhi - ylo) * 0.012
            ax.text(x - 7, e["level"] + (dy if e["dir"] == 1 else -dy), e["kind"], color="#8ab4f8", fontsize=8, ha="center",
                    va="bottom" if e["dir"] == 1 else "top", clip_on=True)
            last_x = x
    sw = [e for e in an["sweeps"] if e["i"] >= s][-1:]
    for e in sw:
        y = c.h[e["i"]] if e["dir"] == -1 else c.l[e["i"]]
        ax.annotate("Sweep", (e["i"] - s, y), xytext=(0, 14 if e["dir"] == -1 else -14), textcoords="offset points",
                    color="#ffab40", fontsize=8, ha="center", arrowprops=dict(arrowstyle="-", color="#ffab40", lw=0.7))
    if sig:
        if sig.get("tl"):
            t = sig["tl"]
            x1, x2 = t["i1"] - s, t["i2"] - s
            slope = (t["p2"] - t["p1"]) / max(1, t["i2"] - t["i1"])
            ax.plot([x1, W - 1], [t["p1"], t["p1"] + slope * (W - 1 - x1)], color="#ffd54f", lw=1.2)
            labels.append((t["y"], "Trendline", "#ffd54f"))
        for key, col in (("entry", "#ffffff"), ("sl", DN), ("tp1", UP), ("tp2", UP)):
            ax.hlines(sig[key], 0, W, color=col, lw=1.1, ls="--")
            labels.append((sig[key], f"{key.upper()} {fmt(sig[key])}", col))
    gap = (yhi - ylo) * 0.038
    for p, (y, text, col) in _spread(labels, ylo, yhi, gap):
        ax.plot([W, W + 0.8], [y, p], color=col, lw=0.6, alpha=0.7, clip_on=False)
        ax.text(W + 1.0, p, text, color=col, fontsize=8, va="center", ha="left")
    ax.axhline(price, color="#8aa0c0", lw=0.5, ls=":")
    ax.set_xlim(-1, W + M)
    ax.set_ylim(ylo, yhi)
    ax.set_title(title, color=FG, fontsize=12)
    ax.tick_params(colors=FG, labelsize=8)
    ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_color("#2a3345")
    ax.grid(color="#1c2535", lw=0.5)
    if watermark:
        wm = _shape(watermark)
        fig.text(0.46, 0.5, wm, fontsize=46, color="white", alpha=0.07, ha="center", va="center", rotation=22)
        fig.text(0.015, 0.012, wm, fontsize=9, color="white", alpha=0.45, ha="left", va="bottom")
    fig.tight_layout()
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path
