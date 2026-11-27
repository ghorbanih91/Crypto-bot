import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from .util import DATA

BG, FG, UP, DN = "#0f1520", "#c8d1e0", "#26a69a", "#ef5350"


def draw(an, path, title, sig=None, n=110):
    c = an["c"]
    N = len(c)
    s = max(0, N - n)
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=110)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for i in range(s, N):
        x = i - s
        col = UP if c.c[i] >= c.o[i] else DN
        ax.vlines(x, c.l[i], c.h[i], color=col, lw=0.8)
        ax.add_patch(Rectangle((x - 0.32, min(c.o[i], c.c[i])), 0.64, max(abs(c.c[i] - c.o[i]), 1e-9), color=col))
    W = N - s + 8
    lo0, hi0 = c.l[s:].min(), c.h[s:].max()
    ys0 = [lo0, hi0] + ([sig["sl"], sig["tp2"]] if sig else [])
    pad0 = (hi0 - lo0) * 0.06
    ylo, yhi = min(ys0) - pad0, max(ys0) + pad0
    inside = lambda y: ylo <= y <= yhi
    for f in an["fvg"][-6:]:
        if f["i"] >= s - 20 and inside(f["top"]) and inside(f["bot"]):
            ax.add_patch(Rectangle((max(0, f["i"] - s), f["bot"]), W - max(0, f["i"] - s), f["top"] - f["bot"],
                                   color=UP if f["dir"] == 1 else DN, alpha=0.18, lw=0))
            ax.text(W - 0.5, (f["top"] + f["bot"]) / 2, "FVG", color=FG, fontsize=7, ha="right", va="center")
    for z in an["ob"][-4:]:
        if z["i"] >= s - 20 and inside(z["top"]) and inside(z["bot"]):
            ax.add_patch(Rectangle((max(0, z["i"] - s), z["bot"]), W - max(0, z["i"] - s), z["top"] - z["bot"],
                                   facecolor="none", edgecolor="#f0b90b", lw=1, ls="--"))
            ax.text(W - 0.5, z["top"], "OB", color="#f0b90b", fontsize=7, ha="right", va="bottom")
    for e in an["events"][-6:]:
        if e["i"] >= s:
            ax.hlines(e["level"], max(0, e["i"] - s - 12), e["i"] - s, color="#8ab4f8", lw=0.9, ls=":")
            ax.text(e["i"] - s - 6, e["level"], e["kind"] + (" ▲" if e["dir"] == 1 else " ▼"),
                    color="#8ab4f8", fontsize=8, ha="center", va="bottom" if e["dir"] == 1 else "top")
    for key, lab in (("hi", "EQH"), ("lo", "EQL")):
        for p in [q for q in an["liq"][key][-3:] if inside(q["level"])]:
            ax.axhline(p["level"], color="#b388ff", lw=0.8, ls="-.", alpha=0.8)
            ax.text(0.5, p["level"], lab, color="#b388ff", fontsize=7, va="bottom")
    for e in an["sweeps"][-2:]:
        if e["i"] >= s:
            ax.annotate("Sweep", (e["i"] - s, c.h[e["i"]] if e["dir"] == -1 else c.l[e["i"]]),
                        color="#ffab40", fontsize=8, ha="center")
    if sig:
        for key, col in (("entry", "#ffffff"), ("sl", DN), ("tp1", UP), ("tp2", UP)):
            ax.axhline(sig[key], color=col, lw=1.1, ls="--")
            ax.text(W - 0.5, sig[key], key.upper(), color=col, fontsize=8, ha="right", va="bottom")
    ax.set_xlim(-1, W)
    ax.set_ylim(ylo, yhi)
    ax.set_title(title, color=FG, fontsize=12)
    ax.tick_params(colors=FG, labelsize=8)
    ax.yaxis.tick_right()
    ax.set_xticks([])
    for sp in ax.spines.values():
        sp.set_color("#2a3345")
    ax.grid(color="#1c2535", lw=0.5)
    fig.tight_layout()
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return path
