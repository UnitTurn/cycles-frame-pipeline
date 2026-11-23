# Ruins benchmark · Host BVH Prepacking and Eager Upload

English · [简体中文](README.zh-CN.md)

On a Radeon RX 7800 XT, official Blender took **576.072 s** to render ten consecutive Ruins frames, measured from launch to the final PNG. Host BVH Prepacking, the v0.5.0 default, took **472.271 s** and used **8.46 GiB** of dedicated VRAM at peak. Eager Upload took **476.824 s** and peaked at **12.40 GiB**. After the first PNG, Eager Upload produced a frame every **28.935 s** on average, compared with **30.208 s** for prepacking.

## Ten measured frames and a 1,000-frame estimate

| Mode | 10 frames · measured | Time saved vs. official | 1,000 frames · projected | Time saved vs. official |
|---|---:|---:|---:|---:|
| Official Blender | 576.072 s | — | 11 h 51 m 36 s | — |
| Host BVH Prepacking (default) | 472.271 s | 103.801 s (**18.02%**) | 8 h 26 m 18 s | 3 h 25 m 18 s (**28.85%**) |
| Eager Upload | 476.824 s | 99.248 s (**17.23%**) | 8 h 05 m 23 s | 3 h 46 m 13 s (**31.79%**) |

![Ten-frame measurements and 1,000-frame projections for official Blender, Host BVH Prepacking and Eager Upload](projection-en.png)

The estimate counts startup and the first PNG once. It adds 999 intervals at the average pace of the nine measured intervals, using `T₁₀₀₀ = T₁ + 999 × (T₁₀ − T₁) / 9`. All reductions use official Blender’s time at the same frame count as the denominator. Actual savings over a longer sequence depend on later frames having similar geometry, sampling and output costs. [Projection inputs and results](data/projection.csv)

## Test conditions

| Setting | Value |
|---|---|
| Platform | Windows x64, Blender 5.2.1 LTS, upstream revision `9e2066aef7ef` |
| Hardware | One Radeon RX 7800 XT, 15.96 GiB dedicated VRAM and 31.95 GiB physical RAM visible to Windows |
| Scene | Ruins production animation, frames 624–633 in order, 1920 × 1080, 8-bit RGBA PNG |
| Cycles | HIP, software BVH2, persistent data, up to 256 adaptive samples with a 0.01 threshold |

Each configuration rendered the entire sequence once in a fresh process. Official Blender used the production worker's synchronous output. Both pipeline modes used a six-thread CPU output worker. The Eager Upload measurements come from the earlier run of the dual-session candidate, with the same scene, render settings and official baseline. This mode is selected with `--eager-upload` in v0.5.0. Host BVH Prepacking was timed on its release candidate. The final package adds checks for UV and motion pass changes and preserves the scene during a mid-animation switch to serial output. Ruins kept the same passes and preparation mode throughout.

## Timing, GPU and memory

| Measurement | Official Blender | Host BVH Prepacking (default) | Eager Upload |
|---|---:|---:|---:|
| Launch to first PNG | 193.164 s | 200.398 s | 216.408 s |
| Launch to final PNG | 576.072 s | 472.271 s | 476.824 s |
| Launch to process exit | 591.002 s | 488.001 s | 499.010 s |
| Mean interval between PNGs | 42.545 s | 30.208 s | 28.935 s |
| Mean GPU utilization between first and final PNG | 71.39% | 91.52% | 94.86% |
| Time below 10% GPU utilization in that window | 3.007 s | 10.267 s | 0.000 s |
| Peak dedicated VRAM | 8.53 GiB | 8.46 GiB | 12.40 GiB |
| Peak physical RAM in use | 31.95 GiB | 31.95 GiB | 31.95 GiB |
| Peak system commit | 73.89 GiB | 76.31 GiB | 87.49 GiB |

![Timing, GPU utilization and memory for official Blender and both pipeline modes](overview-en.png)

The GPU activity sensor (AMD ADL) and dedicated VRAM counter (Windows WDDM) cover the entire card. Physical RAM and commit cover the entire system. Commit measures memory Windows has committed to back with RAM or the page file. Before launch, in table order, dedicated VRAM was **2.65 / 2.71 / 2.53 GiB** and system commit was **28.38 / 30.42 / 28.57 GiB**.

The monitor sampled approximately once per second. Mean GPU utilization and time below 10% weight each reading by its duration between publication of the first and final PNG. Memory peaks cover launch through process exit. The two vertical lines in each timeline mark the first and final PNG. [Telemetry samples](data/telemetry.csv) · [Run summaries](data/summary.csv)

![One-second GPU, VRAM, physical RAM and system commit traces for the three runs](telemetry-en.png)

## What happened at each handoff

In Host BVH Prepacking mode, Cycles evaluated the next frame and verified and packed its software BVH2 during the preceding frame’s GPU sampling window at all **nine** handoffs. The CPU-side BVH package was ready **19.875–25.575 s** before the preceding frame finished sampling. Once that frame released the device, the same Cycles session began the device update and consumed the prepared package exactly once. The gap from the last sampling batch of one frame to the first batch of the next ranged from **1.347 to 1.679 s**, with a **1.472 s** median.

With Eager Upload, a second Cycles session also uploaded the next frame’s device data during the current frame’s sampling window. The median sampling gap was **0.147 s**. The per-frame CSV includes PNG timestamps for all three configurations and sampling windows and gaps for both pipeline modes, in seconds from launch. [Frame timings](data/frames.csv)

## Historical image comparison · v0.4.0 Eager Upload versus official Blender

The pixel comparison decodes each prepared PNG and compares it with the official PNG for the same frame. Of 20,736,000 pixels, **5,343** differed in RGB, with a maximum absolute difference of **1/255** in every frame. All alpha values matched. The mean absolute difference over RGB channels was **0.00008644** on the 0–255 scale.

[Original v0.4.0 report](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.4.0/benchmarks/README.md) · [Original per-frame results](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.4.0/benchmarks/data/frames.csv)

## Redrawing the charts

From the repository root, run the following commands. The Chinese charts require a supported Chinese font such as Microsoft YaHei or Noto Sans CJK SC. Use `--language en` to generate only the English edition.

```console
python -m pip install matplotlib
python benchmarks/plot.py
```

The Ruins production scene is private. The repository includes a procedural integration fixture for exercising frame handoffs on a distributable scene. [Procedural fixture](../engine/lookahead/check_stock_pipeline.py)
