#!/usr/bin/env python3
"""
Draw the timing and hardware charts on the main README, in light and dark.

Every measured number below comes from a run recorded in this repository
(the example READMEs, frames.json, motion.json and environment/hardware-matrix.md).
The bigger-hardware numbers are estimates from the scaling model in
scaling_estimates(); docs/performance.md explains it.

Needs matplotlib, which the kit itself does not:
    pip install matplotlib        (or: uv pip install matplotlib)
    python tools/make_charts.py   writes docs/images/charts/*-light.svg and *-dark.svg
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator, NullLocator  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "images", "charts")

THEMES = {
    "light": {"bg": "#ffffff", "fg": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0", "track": "#eff2f5"},
    "dark": {"bg": "#0d1117", "fg": "#e6edf3", "muted": "#9198a1", "grid": "#30363d", "track": "#161b22"},
}
# Okabe-Ito colors: distinguishable with the common kinds of color blindness.
STAGE = {
    "Writing": "#E69F00",
    "Previs": "#56B4E9",
    "Keyframes": "#009E73",
    "Motion": "#CC79A7",
    "Sound, captions, cut, QC": "#0072B2",
}
REDO = "#D55E00"

# --------------------------------------------------------------------------
# Measured on this machine: RTX 2070 SUPER 8 GB, Threadripper PRO 3975WX, 109 GB RAM
# --------------------------------------------------------------------------

# Machine time for each complete example, in minutes, failures and retakes included.
EXAMPLES = [
    # Workshop stack: brief 58 s, shots 14 s, previs 23 s, 12 SDXL renders (about 4.5 min),
    # scratch voice, Whisper base.en 4 s, animatic 17 s, QC and audit.
    ("Ember & Oak\nworkshop models", (58 + 14 + 23 + 270 + 5 + 4 + 17 + 2) / 60),
    # glm-4.7-flash brief 63 s and shots 90 s, FLUX.2 klein: 3 renders, about 2.5 min.
    ("Ember & Oak\nbigger models", (63 + 90 + 23 + 150 + 5 + 4 + 17 + 2) / 60),
    # glm-4.7-flash 58 s + 108 s, two previs renders, 7 FLUX.2 klein renders (frames*.json).
    ("Grand Cru Car Wash\nbigger models", (58 + 108 + 46 + 37.1 * 6 + 47.1 + 5 + 4 + 17 + 2) / 60),
    # 3 FLUX.2 klein frames at 36.8 s (frames.json); text, previs and post as the workshop stack.
    ("Summit pitch\nversion 1", (58 + 14 + 23 + 36.8 * 3 + 5 + 4 + 17 + 2) / 60),
    # See LIMIT below.
    ("Summit pitch\npushing the limit", None),
]

# The pushing-the-limit run, in minutes: (first pass, redone).
LIMIT = {
    "Writing": (4.6 + 30.5, 35.5),            # brief, shot list; the context-overflow run
    "Previs": (1.0, 0.0),                     # six grey renders, under a minute
    "Keyframes": (35 + 28 + 34 + 28 + 34 + 34, 28 + 34),   # FLUX.2 dev; shots 4 and 6 retaken
    "Motion": (24.2 + 24.1 + 24.0 + 24.1 + 24.1 + 24.0, 24.1),  # Wan 2.2 5B; shot 6 retaken
    "Sound, captions, cut, QC": (3.0, 0.0),   # Kokoro, Whisper turbo, ffmpeg, QC, pre-audit
}

# Weights each part of the kit loads, in GB on disk.
MODELS = [
    ("Whisper turbo (captions)", 1.6),
    ("llama3.2:3b (workshop writing)", 2.0),
    ("Qwen3-TTS 1.7B (voice clone)", 4.3),
    ("SDXL + depth ControlNet (workshop frames)", 6.6 + 0.3),
    ("MusicGen stereo large (music)", 13.0),
    ("FLUX.2 klein 4B + text encoder", 7.4 + 7.7 + 0.3),
    ("Wan 2.2 5B + text encoder + VAE (motion)", 9.5 + 6.4 + 1.3),
    ("glm-4.7-flash (bigger writing)", 19.0),
    ("FLUX.2 dev 32B + text encoder", 33.8 + 17.2 + 0.3),
    ("gpt-oss-120b (pushing-the-limit writing)", 63.0),
]

# --------------------------------------------------------------------------
# Scaling model for bigger hardware (estimates, not measurements)
# --------------------------------------------------------------------------

# Dense tensor throughput in TFLOPS from the vendors' spec sheets: FP16 with FP32
# accumulate (what PyTorch uses), and FP8 where the card has it. Memory in GB,
# host link in GB/s (practical PCIe), memory bandwidth in GB/s.
HARDWARE = [
    {"name": "This machine\nRTX 2070 SUPER 8 GB", "short": "RTX 2070 SUPER", "fp16": 36.2, "fp8": None,
     "vram": 8, "link": 12, "measured": True},
    {"name": "RTX 4090\n24 GB", "short": "RTX 4090", "fp16": 165.2, "fp8": 330.3, "vram": 24, "link": 25},
    {"name": "RTX 5090\n32 GB", "short": "RTX 5090", "fp16": 209.5, "fp8": 419.0, "vram": 32, "link": 50},
    {"name": "H100 SXM\n80 GB", "short": "H100", "fp16": 989.4, "fp8": 1978.9, "vram": 80, "link": 50},
]
BASE = HARDWARE[0]

# Writing with gpt-oss-120b is limited by memory bandwidth, not compute. On the 24
# and 32 GB cards most of its 63 GB stays in system RAM with only part of the
# work on the GPU; on the 80 GB card all of it fits in fast memory.
WRITING_SPEEDUP = {"RTX 4090": (1.5, 2.5), "RTX 5090": (1.7, 3.0), "H100": (6.0, 12.0)}


def diffusion_minutes(per_step_s, steps, weights_gb, hw, fixed_s, efficiency):
    """Minutes per render for a compute-bound diffusion model, (fast, slow)."""
    # Remove the 2070 SUPER's own weight-streaming time, which is inside the measurement.
    base_stream = max(0.0, weights_gb - BASE["vram"]) / BASE["link"]
    compute = per_step_s - base_stream
    over = max(0.0, weights_gb - hw["vram"]) / hw["link"]
    fast = compute * BASE["fp16"] / (hw["fp8"] or hw["fp16"]) + over * 0.5
    slow = compute * BASE["fp16"] / hw["fp16"] / efficiency + over
    # Text encoding, VAE decode and file writes: faster too, but never free.
    fixed_fast = max(5.0, fixed_s * BASE["fp16"] / hw["fp16"])
    fixed_slow = max(10.0, fixed_s * BASE["fp16"] / hw["fp16"] / efficiency)
    return ((fast * steps + fixed_fast) / 60, (slow * steps + fixed_slow) / 60)


def scaling_estimates():
    """First-pass minutes per stage for each hardware tier: {short: {stage: (fast, slow)}}."""
    first = {k: v[0] for k, v in LIMIT.items()}
    out = {}
    for hw in HARDWARE:
        if hw.get("measured"):
            out[hw["short"]] = {k: (v, v) for k, v in first.items()}
            continue
        # FLUX.2 dev: 72 s per step, 28 steps, 34 GB transformer; text encoder and VAE about 20 s.
        kf = diffusion_minutes(72.0, 28, 34.0, hw, 20, 0.7)
        # Wan 2.2 5B: 36 s per step, 20 steps, 9.5 GB transformer; text encoder and VAE about 60 s.
        mo = diffusion_minutes(36.0, 20, 9.5, hw, 60, 0.7)
        lo, hi = WRITING_SPEEDUP[hw["short"]]
        w = first["Writing"]
        out[hw["short"]] = {
            "Writing": (w / hi, w / lo),
            "Previs": (first["Previs"] * 0.5, first["Previs"]),
            "Keyframes": (kf[0] * 6, kf[1] * 6),
            "Motion": (mo[0] * 6, mo[1] * 6),
            "Sound, captions, cut, QC": (first["Sound, captions, cut, QC"], first["Sound, captions, cut, QC"]),
        }
    return out


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

def hm(minutes):
    if minutes < 1:
        return "under 1 min"
    if minutes < 60:
        return f"{minutes:.0f} min"
    h, m = divmod(round(minutes), 60)
    return f"{h} h {m:02d} min" if m else f"{h} h"


def setup(theme, w, h):
    t = THEMES[theme]
    plt.rcParams.update({
        "font.family": ["Noto Sans", "DejaVu Sans"], "font.size": 12.5, "svg.fonttype": "path",
        "text.color": t["fg"], "axes.labelcolor": t["fg"], "xtick.color": t["muted"], "ytick.color": t["fg"],
        "axes.edgecolor": t["grid"], "figure.facecolor": t["bg"], "axes.facecolor": t["bg"],
    })
    fig, ax = plt.subplots(figsize=(w, h), dpi=100)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(axis="y", length=0, pad=10)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax, t


def title(fig, ax, t, head, sub):
    fig.text(0.012, 0.975, head, fontsize=17, fontweight="bold", color=t["fg"], va="top")
    fig.text(0.012, 0.975 - 0.42 / fig.get_figheight(), sub, fontsize=12, color=t["muted"], va="top")


def save(fig, name, theme):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}-{theme}.svg")
    fig.savefig(path, facecolor=fig.get_facecolor(), metadata={"Date": None})
    plt.close(fig)
    return path


def chart_examples(theme):
    total_limit = sum(a + b for a, b in LIMIT.values())
    rows = [(n, total_limit if v is None else v) for n, v in EXAMPLES]
    fig, ax, t = setup(theme, 10, 4.6)
    names = [r[0] for r in rows][::-1]
    vals = [r[1] for r in rows][::-1]
    colors = [REDO if v > 60 else STAGE["Keyframes"] for v in vals]
    bars = ax.barh(names, vals, color=colors, height=0.62)
    ax.set_xscale("log")
    ticks = [1, 3, 10, 30, 60, 180, 600]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: {1: "1 min", 3: "3 min", 10: "10 min", 30: "30 min",
                                                             60: "1 h", 180: "3 h", 600: "10 h"}.get(round(x), "")))
    ax.set_xlim(1, 1200)
    for b, v in zip(bars, vals):
        ax.text(b.get_width() * 1.08, b.get_y() + b.get_height() / 2, hm(v), va="center",
                fontsize=12.5, fontweight="bold", color=t["fg"])
    ax.set_xlabel("Machine time for a finished 30-second spot (log scale), failures and retakes included",
                  color=t["muted"], fontsize=11.5, labelpad=10)
    title(fig, ax, t, "End to end, on one 8 GB graphics card",
          "Every example in this kit, measured on an RTX 2070 SUPER with 109 GB of system RAM")
    fig.subplots_adjust(left=0.2, right=0.97, top=0.8, bottom=0.17)
    return save(fig, "e2e-examples", theme)


def chart_breakdown(theme):
    fig, ax, t = setup(theme, 10, 4.4)
    stages = list(LIMIT)[::-1]
    first = [LIMIT[s][0] for s in stages]
    redo = [LIMIT[s][1] for s in stages]
    ax.barh(stages, first, color=[STAGE[s] for s in stages], height=0.62, label="First pass")
    ax.barh(stages, redo, left=first, color=REDO, height=0.62, hatch="///", edgecolor=t["bg"], linewidth=0,
            label="Failed runs and retakes")
    for i, (f, r) in enumerate(zip(first, redo)):
        label = hm(f) + (f"  +  {hm(r)} redone" if r else "")
        ax.text(f + r + 4, i, label, va="center", fontsize=12, color=t["fg"])
    ax.set_xlim(0, 380)
    ax.xaxis.set_major_locator(MultipleLocator(60))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: hm(x) if x else "0"))
    leg = ax.legend(handles=[Patch(facecolor=REDO, hatch="///", edgecolor=t["bg"], label="Failed runs and retakes")],
                    loc="lower right", frameon=False, fontsize=11.5)
    for txt in leg.get_texts():
        txt.set_color(t["fg"])
    total_first = sum(first)
    total_redo = sum(redo)
    title(fig, ax, t, "Where the 8 hours went: summit pitch, pushing the limit",
          f"{hm(total_first)} of first-pass work, plus {hm(total_redo)} redone after a gate said no "
          f"({total_redo / (total_first + total_redo):.0%} of the run)")
    fig.subplots_adjust(left=0.25, right=0.97, top=0.8, bottom=0.1)
    return save(fig, "limit-breakdown", theme)


def chart_memory(theme):
    fig, ax, t = setup(theme, 11, 5.8)
    rows = sorted(MODELS, key=lambda r: r[1])
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [STAGE["Keyframes"] if v <= 8 else (STAGE["Writing"] if v <= 32 else REDO) for v in vals]
    ax.barh(names, vals, color=colors, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 0.8, i, f"{v:.1f} GB", va="center", fontsize=11.5, color=t["fg"])
    for gb, label, ha, row in ((8, "8 GB: this card", "left", 1), (24, "24 GB: RTX 4090", "right", 0),
                               (32, "32 GB: RTX 5090", "left", 1), (80, "80 GB: H100", "right", 0)):
        ax.axvline(gb, color=t["muted"], linestyle=(0, (4, 3)), linewidth=1.2)
        ax.text(gb + (0.6 if ha == "left" else -0.6), len(rows) - 0.25 + row * 0.62, label, ha=ha, va="bottom",
                fontsize=10.5, color=t["muted"])
    ax.set_xlim(0, 86)
    ax.set_ylim(-0.6, len(rows) + 1.0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f} GB"))
    title(fig, ax, t, "Why it is slow here: almost nothing fits in 8 GB",
          "Model weights on disk. Green fits this card; orange fits a 24 to 32 GB card; red needs 80 GB or system RAM")
    fig.subplots_adjust(left=0.4, right=0.97, top=0.8, bottom=0.07)
    return save(fig, "model-memory", theme)


def chart_scaling(theme):
    est = scaling_estimates()
    fig, ax, t = setup(theme, 10, 5.0)
    hws = HARDWARE[::-1]
    y = range(len(hws))
    left = [0.0] * len(hws)
    for stage, color in STAGE.items():
        vals = [est[h["short"]][stage][1] for h in hws]
        ax.barh(list(y), vals, left=left, color=color, height=0.6, label=stage)
        left = [a + b for a, b in zip(left, vals)]
    fast = [sum(v[0] for v in est[h["short"]].values()) for h in hws]
    slow = left
    for i, (f, s, h) in enumerate(zip(fast, slow, hws)):
        if h.get("measured"):
            label = f"{hm(s)}  measured"
        else:
            ax.plot([f, s], [i + 0.42, i + 0.42], color=t["fg"], linewidth=2, solid_capstyle="butt")
            ax.plot([f, f], [i + 0.32, i + 0.52], color=t["fg"], linewidth=2)
            ax.plot([s, s], [i + 0.32, i + 0.52], color=t["fg"], linewidth=2)
            label = f"about {hm(f)} to {hm(s)}"
        ax.text(s + 5, i, label, va="center", fontsize=12.5, fontweight="bold", color=t["fg"])
    ax.set_yticks(list(y), [h["name"] for h in hws])
    ax.set_xlim(0, 540)
    ax.xaxis.set_major_locator(MultipleLocator(60))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: hm(x) if x else "0"))
    leg = ax.legend(loc="lower right", frameon=False, fontsize=10.5, ncol=1)
    for txt in leg.get_texts():
        txt.set_color(t["fg"])
    title(fig, ax, t, "The same first pass on bigger hardware (estimates)",
          "Six shots, no retakes. Each bar is the slower estimate; the line above it spans faster to slower")
    fig.subplots_adjust(left=0.2, right=0.97, top=0.8, bottom=0.08)
    return save(fig, "scaling", theme)


def main():
    for theme in THEMES:
        for chart in (chart_examples, chart_breakdown, chart_memory, chart_scaling):
            print(chart(theme))
    est = scaling_estimates()
    print("\nFirst-pass minutes, (faster, slower):")
    for hw in HARDWARE:
        e = est[hw["short"]]
        tot = (sum(v[0] for v in e.values()), sum(v[1] for v in e.values()))
        print(f"  {hw['short']:15s} total {tot[0]:6.1f} to {tot[1]:6.1f} | "
              + " | ".join(f"{k.split(',')[0]} {v[0]:.1f}-{v[1]:.1f}" for k, v in e.items()))


if __name__ == "__main__":
    main()
