"""Render both language editions of the charts from the public CSV files."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FixedLocator


HERE = Path(__file__).resolve().parent
RUNS = ("official", "previous", "prepared")
COLORS = ("#65778C", "#C16D2D", "#007D71")
INK, MUTED, GRID = "#132D3D", "#475F70", "#DDE5E9"
METRICS = (
    ("launch_to_last_png_s", 600, (0, 200, 400, 600), "s"),
    ("warm_average_png_interval_s", 45, (0, 15, 30, 45), "s"),
    ("warm_card_gpu_pct", 100, (0, 25, 50, 75, 100), "%"),
    ("warm_card_gpu_below_10_s", 90, (0, 30, 60, 90), "s"),
    ("vram_peak_gib", 16, (0, 4, 8, 12, 16), "GiB"),
    ("system_commit_peak_gib", 100, (0, 25, 50, 75, 100), "GiB"),
)
TEXT = {
    "en": {
        "names": ("Official", "Previous", "Prepared"),
        "overview": "Ten consecutive animation frames",
        "subtitle": "Blender 5.2.1 LTS   /   Radeon RX 7800 XT   /   HIP   /   1920 × 1080   /   Frames 624–633",
        "metrics": ("Launch to final PNG", "Mean interval between PNGs", "Mean GPU utilization",
                    "Time with GPU below 10%", "Peak dedicated VRAM", "Peak system commit"),
        "windows": ("All ten frames", "Nine warm intervals", "Nine warm intervals",
                    "Nine warm intervals", "Launch to process exit", "Launch to process exit"),
        "traces": "GPU and memory over time",
        "trace_labels": ("GPU utilization", "Dedicated VRAM", "Physical RAM"),
        "time": "Seconds since launch",
        "notes": "Each column shows one complete run. Dashed lines mark publication of the first and last PNG.",
    },
    "zh": {
        "names": ("官方", "上一版", "正式帧交接"),
        "overview": "连续十帧动画渲染",
        "subtitle": "Blender 5.2.1 LTS   /   Radeon RX 7800 XT   /   HIP   /   1920 × 1080   /   第 624–633 帧",
        "metrics": ("启动至最后一张 PNG 写完", "相邻 PNG 平均出图间隔", "GPU 平均利用率",
                    "GPU 利用率低于 10% 的时长", "专用显存峰值", "系统提交内存峰值"),
        "windows": ("全部十帧", "后九个出图间隔", "后九个出图间隔",
                    "后九个出图间隔", "从启动到进程退出", "从启动到进程退出"),
        "traces": "GPU 与内存使用时间线",
        "trace_labels": ("GPU 利用率", "专用显存", "物理内存"),
        "time": "距启动时间（秒）",
        "notes": "每列对应一组完整测试。两条虚线依次标出首张和末张 PNG 写完的时间。",
    },
}


def read_data(name):
    with (HERE / "data" / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def select_font(lang):
    candidates = ("Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", "PingFang SC",
                  "Source Han Sans SC") if lang == "zh" else ("DejaVu Sans",)
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            return name
    raise SystemExit("Install Noto Sans CJK SC to render the Chinese charts, or use --language en.")


def style_axis(ax):
    ax.set_axisbelow(True)
    ax.spines[:].set_visible(False)
    ax.tick_params(axis="both", length=0, colors=MUTED, labelsize=10, pad=6)


def heading(fig, title, subtitle):
    fig.text(.065, .966, title, va="top", fontsize=25, fontweight="bold", color=INK)
    fig.text(.066, .907, subtitle, va="top", fontsize=10.5, color=MUTED)


def overview(language, summary):
    words = TEXT[language]
    fig, axes = plt.subplots(3, 2, figsize=(12.5, 8.5))
    fig.subplots_adjust(left=.145, right=.968, bottom=.08, top=.80, wspace=.39, hspace=.86)
    heading(fig, words["overview"], words["subtitle"])
    for i, (ax, (key, limit, ticks, unit)) in enumerate(zip(axes.flat, METRICS)):
        values = [float(summary[run][key]) for run in RUNS]
        ax.barh([0, 1, 2], values, color=COLORS, height=.47)
        ax.set_ylim(2.62, -.65)
        ax.set_xlim(0, limit * 1.12)
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.set_yticks([0, 1, 2], words["names"])
        style_axis(ax)
        ax.grid(axis="x", color=GRID, linewidth=.8)
        ax.set_title(words["metrics"][i], loc="left", color=INK, fontsize=14.5,
                     fontweight="bold", pad=16)
        ax.text(0, 1.004, words["windows"][i], transform=ax.transAxes, va="bottom",
                color=MUTED, fontsize=9.2)
        for pos, value in enumerate(values):
            ax.text(value + limit * .017, pos, f"{value:.2f}{'' if unit == '%' else ' '}{unit}",
                    va="center", ha="left", fontsize=10.5, color=INK)
    fig.savefig(HERE / f"overview-{language}.png", dpi=150, facecolor="white")
    plt.close(fig)


def telemetry(language, summary, rows):
    words = TEXT[language]
    fig, axes = plt.subplots(3, 3, sharex=True, sharey="row", figsize=(13, 8.1))
    fig.subplots_adjust(left=.083, right=.976, bottom=.14, top=.775, hspace=.31, wspace=.10)
    heading(fig, words["traces"], words["subtitle"])
    y_metrics = (("gpu_busy_pct", "%", (0, 50, 100)), ("vram_used_gib", "GiB", (0, 8, 16)),
                 ("ram_used_gib", "GiB", (0, 16, 32)))
    for column, run in enumerate(RUNS):
        series = [r for r in rows if r["run"] == run and
                  0 <= float(r["seconds_from_launch"]) <= float(summary[run]["launch_to_exit_s"])]
        for index, (key, unit, ticks) in enumerate(y_metrics):
            ax = axes[index, column]
            style_axis(ax)
            valid = [(float(r["seconds_from_launch"]), float(r[key])) for r in series if r[key]]
            x, y = zip(*valid)
            ax.plot(x, y, lw=1.1, color=COLORS[column])
            for event in ("launch_to_first_png_s", "launch_to_last_png_s"):
                ax.axvline(float(summary[run][event]), color=MUTED, lw=.9, dashes=(3, 3), zorder=1)
            ax.set_yticks(ticks)
            ax.set_ylim(-ticks[-1] * .04, ticks[-1] * 1.06)
            ax.set_xlim(0, 580)
            ax.set_xticks((0, 150, 300, 450))
            ax.grid(color=GRID, linewidth=.7)
            if column == 0:
                ax.set_ylabel(f"{words['trace_labels'][index]}\n({unit})", color=INK, fontsize=10)
            if index == 0:
                ax.set_title(words["names"][column], fontsize=16, fontweight="bold",
                             color=COLORS[column], loc="left", pad=11)
    fig.supxlabel(words["time"], y=.070, color=INK, fontsize=11)
    fig.text(.066, .025, words["notes"], fontsize=10, color=MUTED)
    fig.savefig(HERE / f"telemetry-{language}.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("en", "zh", "both"), default="both")
    args = parser.parse_args()
    summary_rows = {r["run"]: r for r in read_data("summary.csv")}
    timeline_rows = read_data("telemetry.csv")
    for language in (("en", "zh") if args.language == "both" else (args.language,)):
        with plt.rc_context({"font.family": select_font(language), "axes.unicode_minus": False}):
            overview(language, summary_rows)
            telemetry(language, summary_rows, timeline_rows)
