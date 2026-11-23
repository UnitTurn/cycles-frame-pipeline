# Ruins benchmark · Host BVH Prepacking and Eager Upload

English · [简体中文](README.zh-CN.md)

## Ruins frames 625–633

The measured percentage uses the nine PNG intervals after frame 624. Start the clock when frame 624 is written and stop when frame 633 is written. For each mode, `nine-frame time = tenth PNG timestamp − first PNG timestamp`. The reduction is `100 × (stock nine-frame time − mode nine-frame time) / stock nine-frame time`.

| Mode on RX 7800 XT | Nine measured frames | Time saved | Measured time reduction | 1,000 frames, estimated total |
|---|---:|---:|---:|---:|
| Official Blender | 382.908 s | — | Baseline | 11 h 51 m 36 s |
| Host BVH Prepacking (default) | 271.873 s | 111.035 s | **29.00%** | 8 h 26 m 18 s |
| Eager GPU Upload | 260.416 s | 122.492 s | **31.99%** | 8 h 05 m 23 s |

![Measured elapsed time and reduction for frames 625–633, with a separate 1,000-frame estimate](projection-en.png)

Launch to first PNG took 193.164 s in official Blender, 200.398 s with prepacking and 216.408 s with eager upload. These times are reported separately from the measured percentage. The 1,000-frame estimate counts startup and first output once, then adds 999 intervals at the measured mean. Later frames must have similar costs for this estimate to hold. [Inputs and estimates](data/projection.csv)

## Test conditions

| Setting | Value |
|---|---|
| Platform | Windows x64, Blender 5.2.1 LTS, upstream revision `9e2066aef7ef` |
| Hardware | One Radeon RX 7800 XT, 15.96 GiB dedicated VRAM and 31.95 GiB physical RAM visible to Windows |
| Scene | Ruins production animation, frames 624–633 in order, 1920 × 1080, 8-bit RGBA PNG |
| Cycles | HIP, software BVH2, persistent data, up to 256 adaptive samples with a 0.01 threshold |

Each configuration rendered the entire sequence once in a fresh process. Official Blender used the production worker's synchronous output. Both pipeline modes used a six-thread CPU output worker. The Eager Upload measurements come from the earlier run of the dual-session candidate, with the same scene, render settings and official baseline. This mode is selected with `--eager-upload` in v0.5.0. Host BVH Prepacking was timed on its release candidate. The final package adds checks for UV and motion pass changes and preserves the scene during a mid-animation switch to serial output. Ruins kept the same passes and preparation mode throughout. The v0.5.1 release repackages the same native engine. The Ruins figures above are recalculated from these recorded runs.

## Timing, GPU and memory

| Measurement | Official Blender | Host BVH Prepacking (default) | Eager Upload |
|---|---:|---:|---:|
| Launch to first PNG | 193.164 s | 200.398 s | 216.408 s |
| Launch to final PNG | 576.072 s | 472.271 s | 476.824 s |
| Launch to process exit | 591.002 s | 488.001 s | 499.010 s |
| Mean interval between PNGs | 42.545 s | 30.208 s | 28.935 s |
| Mean whole-card GPU activity (AMD ADL) | 71.39% | 91.52% | 94.86% |
| Blender main process below 10% GPU, estimated time | 118.9 s | 11.3 s | 10.8 s |
| Share of each run’s nine-frame time below 10% | 31.04% | 4.15% | 4.16% |
| Peak dedicated VRAM | 8.53 GiB | 8.46 GiB | 12.40 GiB |
| Peak physical RAM in use | 31.95 GiB | 31.95 GiB | 31.95 GiB |
| Peak system commit | 73.89 GiB | 76.31 GiB | 87.49 GiB |

![Timing, GPU utilization and memory for official Blender and both pipeline modes](overview-en.png)

**Low GPU time** counts intervals when the busiest GPU engine attributed to Blender’s main render process averaged strictly below 10%. Windows WDDM provides this rate in `wddm_render_gpu_pct`. Work attributed to other processes, including the separate output worker, is outside the counter’s scope. The window runs from frame 624’s completed PNG to frame 633’s completed PNG, including time spent finishing the last output. [PNG timestamps](data/frames.csv)

The monitor sampled about once a second. Each WDDM reading describes the interval ending at its timestamp. For readings below 10%, we sum the portion of that interval inside the PNG window, then divide by that run’s window duration to get its share. A numeric zero counts. Empty readings mean missing data. All three windows have complete coverage. The two pipeline modes differ by 0.45 s, less than one sample period. [Samples](data/telemetry.csv) · [Calculation](plot.py) · [Run summaries](data/summary.csv) · [Windows rate counter sampling](https://learn.microsoft.com/en-us/windows/win32/perfctrs/collecting-performance-data)

Mean whole-card activity uses the AMD ADL sensor. The summary retains the earlier whole-card estimate in `warm_card_gpu_below_10_s`. Dedicated VRAM covers the entire card. Physical RAM and commit cover the entire system from launch to exit. Commit measures memory Windows has committed to back with RAM or the page file. Before launch, in table order, dedicated VRAM was **2.65 / 2.71 / 2.53 GiB** and system commit was **28.38 / 30.42 / 28.57 GiB**.

![Whole-card and Blender main-process GPU activity, VRAM, physical RAM and system commit for each run](telemetry-en.png)

## What happened at each handoff

In Host BVH Prepacking mode, Cycles evaluated the next frame and verified and packed its software BVH2 during the preceding frame’s GPU sampling window at all **nine** handoffs. The CPU-side BVH package was ready **19.875–25.575 s** before the preceding frame finished sampling. Once that frame released the device, the same Cycles session began the device update and consumed the prepared package exactly once. The gap from the last sampling batch of one frame to the first batch of the next ranged from **1.347 to 1.679 s**, with a **1.472 s** median.

With Eager Upload, a second Cycles session also uploaded the next frame’s device data during the current frame’s sampling window. The median sampling gap was **0.147 s**. The per-frame CSV includes PNG timestamps for all three configurations and sampling windows and gaps for both pipeline modes, in seconds from launch. [Frame timings](data/frames.csv)

## Public fixture

The v0.5.1 Windows engine also rendered a distributable 144 × 96 animation on the RX 7800 XT using HIP, a fixed sample subset and CPU OIDN. The original three-frame regression matched stock Blender in all RGBA channels. With the animation stretched to ten frames, all nine handoffs prepared and consumed their BVH once. Frame 9 had one blue channel value of 218 where stock and the patched engine's serial path gave 219. The other 138,239 pixels and all alpha values matched.

On this small fixture, the nine intervals after the first PNG took **0.979415 s** in official Blender and **1.440376 s** with prepacking, a **47.06% increase in elapsed time**. Both engines rendered the sequence once. Times come from the frame-written log markers. [Per-frame measurements and pixel differences](data/public-fixture-v0.5.1.csv) · [Reproduction commands](../engine/lookahead/README.md)

## Historical image comparison · v0.4.0 Eager Upload versus official Blender

The pixel comparison decodes each prepared PNG and compares it with the official PNG for the same frame. Of 20,736,000 pixels, **5,343** differed in RGB, with a maximum absolute difference of **1/255** in every frame. All alpha values matched. The mean absolute difference over RGB channels was **0.00008644** on the 0–255 scale.

[Original v0.4.0 report](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.4.0/benchmarks/README.md) · [Original per-frame results](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.4.0/benchmarks/data/frames.csv)

## Redrawing the charts

Run these commands from the repository root to recalculate low GPU time and its share in `benchmarks/data/summary.csv` from the published samples and redraw the charts. The Chinese charts require a supported Chinese font such as Microsoft YaHei or Noto Sans CJK SC. Use `--language en` to generate only the English edition.

```console
python -m pip install matplotlib
python benchmarks/plot.py
```

The Ruins production scene is private. The repository includes a procedural integration fixture for exercising frame handoffs on a distributable scene. [Procedural fixture](../engine/lookahead/check_stock_pipeline.py)
