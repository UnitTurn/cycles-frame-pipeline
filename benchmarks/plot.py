"""Render both language editions of the charts from the public CSV files."""

import argparse
import csv
from decimal import Decimal
from math import ceil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch


HERE = Path(__file__).resolve().parent
RUNS = ("official_blender", "cycles_frame_pipeline", "eager")
COLORS = ("#65778C", "#007D71", "#A65116")
INK, MUTED, GRID = "#132D3D", "#475F70", "#DDE5E9"
METRICS = (
    ("measured_nine_intervals_s", 400, (0, 100, 200, 300, 400), "s"),
    ("warm_average_png_interval_s", 45, (0, 15, 30, 45), "s"),
    ("warm_card_gpu_pct", 100, (0, 25, 50, 75, 100), "%"),
    ("warm_card_gpu_below_10_s", 12, (0, 4, 8, 12), "s"),
    ("vram_peak_gib", 16, (0, 4, 8, 12, 16), "GiB"),
    ("system_commit_peak_gib", 100, (0, 25, 50, 75, 100), "GiB"),
)
TEXT = {
    "en": {
        "names": ("Official Blender", "Host BVH prepacking · default", "Eager GPU upload · optional"),
        "overview": "Ten consecutive animation frames",
        "subtitle": "Blender 5.2.1 LTS   /   Radeon RX 7800 XT   /   HIP   /   1920 × 1080   /   Frames 624–633",
        "metrics": ("Time for frames 625–633", "Mean interval between PNGs", "Mean GPU utilization",
                    "Time with GPU below 10%", "Peak dedicated VRAM", "Peak system commit"),
        "windows": ("First PNG to tenth PNG", "Nine warm intervals", "Nine warm intervals",
                    "Nine warm intervals", "Launch to process exit", "Launch to process exit"),
        "traces": "GPU and memory over time",
        "trace_labels": ("GPU utilization", "Dedicated VRAM", "Physical RAM", "System commit"),
        "time": "Seconds since launch",
        "notes": "Each column shows one complete run. Dashed lines mark publication of the first and last PNG.",
        "projection_title": "Nine measured frames after the first PNG",
        "projection_sub": "Ruins · Radeon RX 7800 XT · Elapsed time from publication of frame 624 to publication of frame 633",
        "projection_cols": ("Render mode", "Frames 625–633", "Time reduction vs stock", "1,000 frames · estimate"),
        "reference": "Reference",
        "projection_note": "Only the estimate includes startup and the first PNG, followed by 999 intervals at the measured mean.",
    },
    "zh": {
        "names": ("官方 Blender", "主机端 BVH 预打包 · 默认", "提前上传显存 · 可选"),
        "overview": "连续十帧动画渲染",
        "subtitle": "Blender 5.2.1 LTS   /   Radeon RX 7800 XT   /   HIP   /   1920 × 1080   /   第 624–633 帧",
        "metrics": ("第 625–633 帧出图耗时", "相邻 PNG 平均出图间隔", "GPU 平均利用率",
                    "GPU 利用率低于 10% 的时长", "专用显存峰值", "系统提交内存峰值"),
        "windows": ("首张至第十张 PNG 写完", "后九个出图间隔", "后九个出图间隔",
                    "后九个出图间隔", "从启动到进程退出", "从启动到进程退出"),
        "traces": "GPU 与内存使用时间线",
        "trace_labels": ("GPU 利用率", "专用显存", "物理内存", "系统提交内存"),
        "time": "距启动时间（秒）",
        "notes": "每列对应一组完整测试。两条虚线依次标出首张和末张 PNG 写完的时间。",
        "projection_title": "首帧之后连续九帧的实测耗时",
        "projection_sub": "Ruins · Radeon RX 7800 XT · 从第 624 帧 PNG 写完计时，至第 633 帧 PNG 写完",
        "projection_cols": ("渲染模式", "第 625–633 帧", "相对官方耗时降幅", "1,000 帧总耗时估算"),
        "reference": "基准",
        "projection_note": "千帧估算单独计入启动与首帧，再加上 999 个按后九帧均值计算的出图间隔。",
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


def project_1000_frames(summary):
    rows = []
    for run in RUNS:
        first = Decimal(summary[run]["launch_to_first_png_s"])
        measured_total = Decimal(summary[run]["launch_to_last_png_s"])
        measured_nine = measured_total - first
        estimate = first + measured_nine * 999 / 9
        rows.append(dict(run=run, measured_frames=10, measured_total_s=measured_total,
                         measured_first_png_s=first, measured_nine_intervals_s=measured_nine,
                         measured_interval_count=9, projected_frames=1000, projected_total_s=estimate))
    baseline = rows[0]["measured_nine_intervals_s"]
    for row in rows:
        saved = baseline - row["measured_nine_intervals_s"]
        row["measured_nine_saved_vs_official_s"] = saved
        row["measured_nine_reduction_vs_official_pct"] = round(100 * saved / baseline, 6)
        row["projected_saved_vs_official_s"] = rows[0]["projected_total_s"] - row["projected_total_s"]
    with (HERE / "data" / "projection.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def duration_label(seconds, language):
    hours, remaining = divmod(round(seconds), 3600)
    minutes, seconds = divmod(remaining, 60)
    if language == "zh":
        return f"{hours} 小时 {minutes:02} 分 {seconds:02} 秒"
    return f"{hours} h {minutes:02} m {seconds:02} s"


def projection(language, rows):
    words = TEXT[language]
    fig = plt.figure(figsize=(14.5, 5.8))
    fig.text(.04, .94, words["projection_title"], va="top", fontsize=24,
             fontweight="bold", color=INK)
    fig.text(.041, .83, words["projection_sub"], va="top", fontsize=11, color=MUTED)
    for x, label in zip((.041, .32, .495, .75), words["projection_cols"]):
        fig.text(x, .655, label, fontsize=12, fontweight="bold", color=MUTED)
    bottom, height = .215, .374
    row_centers = [bottom + height * (1 - (i + .5) / len(rows)) for i in range(len(rows))]
    ax = fig.add_axes([.495, bottom, .20, height])
    style_axis(ax)
    ax.set_yticks([])
    ax.set_ylim(len(rows) - .5, -.5)
    ax.set_xlim(0, 36)
    ax.set_xticks((0, 10, 20, 30), ("0%", "10%", "20%", "30%"))
    ax.grid(axis="x", color=GRID, linewidth=.8)
    for index, (run, name, color, y) in enumerate(zip(rows, words["names"], COLORS, row_centers)):
        fig.text(.041, y, name, va="center", color=color, fontsize=12.5, fontweight="bold")
        elapsed = f"{run['measured_nine_intervals_s']:.3f} {'秒' if language == 'zh' else 's'}"
        fig.text(.32, y, elapsed, va="center", color=INK, fontsize=12)
        fig.text(.75, y, duration_label(run["projected_total_s"], language), va="center", color=INK, fontsize=12)
        if index == 0:
            ax.text(1, index, words["reference"], va="center", color=MUTED, fontsize=10)
        else:
            rate = float(run["measured_nine_reduction_vs_official_pct"])
            ax.barh(index, rate, height=.35, color=color)
            ax.text(rate - .9, index, f"{rate:.2f}%", ha="right", va="center", color="white",
                    fontsize=10, fontweight="bold")
    fig.text(.041, .067, words["projection_note"], color=MUTED, fontsize=11)
    fig.savefig(HERE / f"projection-{language}.png", dpi=150, facecolor="white")
    plt.close(fig)


def overview(language, summary):
    words = TEXT[language]
    fig, axes = plt.subplots(3, 2, figsize=(13, 9.2))
    fig.subplots_adjust(left=.067, right=.96, bottom=.075, top=.748, wspace=.25, hspace=.92)
    heading(fig, words["overview"], words["subtitle"])
    handles = [Patch(facecolor=color, label=name) for name, color in zip(words["names"], COLORS)]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.065, .873),
               ncol=len(RUNS), frameon=False, borderaxespad=0, fontsize=11, handlelength=1.3)
    for i, (ax, (key, limit, ticks, unit)) in enumerate(zip(axes.flat, METRICS)):
        values = [float(summary[run][key]) for run in RUNS]
        ax.barh(range(len(RUNS)), values, color=COLORS, height=.46)
        ax.set_ylim(len(RUNS) - .4, -.6)
        ax.set_xlim(0, limit * 1.12)
        ax.set_xticks(ticks)
        ax.set_yticks([])
        style_axis(ax)
        ax.grid(axis="x", color=GRID, linewidth=.8)
        ax.set_title(words["metrics"][i], loc="left", color=INK, fontsize=14.5,
                     fontweight="bold", pad=16)
        ax.text(0, 1.004, words["windows"][i], transform=ax.transAxes, va="bottom",
                color=MUTED, fontsize=9.2)
        precision = 3 if unit == "s" else 2
        for pos, value in enumerate(values):
            ax.text(value + limit * .017, pos, f"{value:.{precision}f}{'' if unit == '%' else ' '}{unit}",
                    va="center", ha="left", fontsize=10.5, color=INK)
    fig.savefig(HERE / f"overview-{language}.png", dpi=150, facecolor="white")
    plt.close(fig)


def telemetry(language, summary, rows):
    words = TEXT[language]
    fig, axes = plt.subplots(4, len(RUNS), sharex=True, sharey="row", figsize=(14.5, 9))
    fig.subplots_adjust(left=.083, right=.976, bottom=.13, top=.79, hspace=.35, wspace=.10)
    heading(fig, words["traces"], words["subtitle"])
    y_metrics = (("gpu_busy_pct", "%", (0, 50, 100)), ("vram_used_gib", "GiB", (0, 8, 16)),
                 ("ram_used_gib", "GiB", (0, 16, 32)), ("commit_gib", "GiB", (0, 50, 100)))
    end = 150 * ceil(max(float(summary[run]["launch_to_exit_s"]) for run in RUNS) / 150)
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
            ax.set_xlim(0, end)
            ax.set_xticks(range(0, end + 1, 150))
            ax.grid(color=GRID, linewidth=.7)
            if column == 0:
                ax.set_ylabel(f"{words['trace_labels'][index]}\n({unit})", color=INK, fontsize=10)
            if index == 0:
                ax.set_title(words["names"][column], fontsize=13, fontweight="bold",
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
    projected_rows = project_1000_frames(summary_rows)
    for row in projected_rows:
        summary_rows[row["run"]]["measured_nine_intervals_s"] = row["measured_nine_intervals_s"]
    for language in (("en", "zh") if args.language == "both" else (args.language,)):
        with plt.rc_context({"font.family": select_font(language), "axes.unicode_minus": False}):
            projection(language, projected_rows)
            overview(language, summary_rows)
            telemetry(language, summary_rows, timeline_rows)
