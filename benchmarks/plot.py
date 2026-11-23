"""Render both language editions of the charts from the public CSV files."""

import argparse
import csv
from decimal import Decimal
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.ticker import FixedLocator


HERE = Path(__file__).resolve().parent
RUNS = ("official_blender", "cycles_frame_pipeline")
COLORS = ("#65778C", "#007D71")
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
        "names": ("Official Blender", "Cycles Frame Pipeline"),
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
        "projection_title": "Time saved across two sequence lengths",
        "projection_sub": "Launch to final PNG on the RX 7800 XT. Percentages use Official Blender's time at the same frame count.",
        "projection_rows": ("10 frames · measured", "1,000 frames · estimated"),
        "projection_cols": ("Sequence", "Official Blender", "Cycles Frame Pipeline", "Time reduction"),
        "projection_saving": "Estimated saving over 1,000 frames",
        "projection_note": "One measured first frame + 999 intervals at the mean of the nine measured PNG intervals.",
    },
    "zh": {
        "names": ("官方 Blender", "发布版"),
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
        "projection_title": "10 帧实测与 1,000 帧估算的耗时降幅",
        "projection_sub": "RX 7800 XT 单次启动至末张 PNG 写完，耗时降幅以同帧数的官方 Blender 耗时为分母。",
        "projection_rows": ("10 帧 · 实测", "1,000 帧 · 估算"),
        "projection_cols": ("渲染序列", "官方 Blender", "发布版", "耗时降幅"),
        "projection_saving": "1,000 帧预计节省",
        "projection_note": "实测首帧耗时 + 999 个出图间隔，每个间隔取实测后九帧的平均值。",
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
    baseline = rows[0]["projected_total_s"]
    for row in rows:
        saved = baseline - row["projected_total_s"]
        measured_baseline = rows[0]["measured_total_s"]
        row["measured_reduction_vs_official_pct"] = round(
            100 * (measured_baseline - row["measured_total_s"]) / measured_baseline, 6)
        row.update(projected_saved_vs_official_s=saved,
                   projected_reduction_vs_official_pct=round(100 * saved / baseline, 6))
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
    fig = plt.figure(figsize=(14, 5.6))
    fig.text(.052, .935, words["projection_title"], va="top", fontsize=24,
             fontweight="bold", color=INK)
    fig.text(.053, .826, words["projection_sub"], va="top", fontsize=11.4, color=MUTED)
    columns = (.053, .282, .462, .705)
    for col, label in zip(columns, words["projection_cols"]):
        fig.text(col, .677, label, fontsize=12, fontweight="bold", color=INK)
    ax = fig.add_axes([columns[3], .293, .245, .338])
    style_axis(ax)
    ax.set_yticks([])
    ax.set_ylim(1.5, -.5)
    ax.set_xlim(0, 39)
    ax.set_xticks((0, 10, 20, 30), ("0%", "10%", "20%", "30%"))
    ax.grid(axis="x", color=GRID, linewidth=.8)
    release = rows[1]
    for index, prefix in enumerate(("measured", "projected")):
        y = ax.get_position().y1 - ax.get_position().height * (index + .5) / 2
        fig.text(columns[0], y, words["projection_rows"][index], va="center", color=INK,
                 fontweight="bold", fontsize=13.2)
        for column, run in zip(columns[1:3], rows):
            total = run[f"{prefix}_total_s"]
            duration = (f"{total:.3f} {'秒' if language == 'zh' else 's'}" if prefix == "measured"
                        else duration_label(total, language))
            fig.text(column, y, duration, va="center", color=INK, fontsize=13.2)
        rate = release[f"{prefix}_reduction_vs_official_pct"]
        ax.barh(index, float(rate), height=.43, color=COLORS[1])
        ax.text(float(rate) + 1, index, f"{rate:.2f}%", va="center", color=INK,
                fontweight="bold", fontsize=12.5)
    saved = duration_label(release["projected_saved_vs_official_s"], language)
    fig.text(.053, .158, f"{words['projection_saving']}    {saved}",
             fontweight="bold", color=COLORS[1], fontsize=14.2)
    fig.text(.053, .077, words["projection_note"], color=MUTED, fontsize=11)
    fig.savefig(HERE / f"projection-{language}.png", dpi=150, facecolor="white")
    plt.close(fig)


def overview(language, summary):
    words = TEXT[language]
    fig, axes = plt.subplots(3, 2, figsize=(12.5, 8.5))
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
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.set_yticks([])
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
    fig, axes = plt.subplots(3, len(RUNS), sharex=True, sharey="row", figsize=(13, 8.1))
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
    projected_rows = project_1000_frames(summary_rows)
    for language in (("en", "zh") if args.language == "both" else (args.language,)):
        with plt.rc_context({"font.family": select_font(language), "axes.unicode_minus": False}):
            projection(language, projected_rows)
            overview(language, summary_rows)
            telemetry(language, summary_rows, timeline_rows)
