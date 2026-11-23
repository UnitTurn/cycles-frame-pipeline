# Cycles Frame Pipeline v0.5.1 — Bilingual Windows engine

[English installation guide](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/README.md#install) · [中文安装指南](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/README.zh-CN.md#安装) · [简体中文发行说明](https://github.com/UnitTurn/cycles-frame-pipeline/blob/b59a55f1de46c59b4c4ab48350328f16c924ea1f/release/notes.zh-CN.md)

Download one Windows engine and one extension. Run the installer with `-Language en` or `-Language zh-CN` to use the corresponding settings and extension profile. It lists the HIP, CUDA and OptiX kernel files it finds in official Blender 5.2.1 LTS for Windows x64 (build `9e2066aef7ef`).

| Download | Package |
|---|---|
| Shared Windows x64 engine | [Engine ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles-frame-pipeline-windows-x64-0.5.1.zip) |
| Blender extension | [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-en.zip) · [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-zh-CN.zip) |
| Corresponding project source and patches | [Source ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-source-0.5.1.zip) |

## Ruins performance after the first frame

On an RX 7800 XT at 1080p using HIP, timing starts when frame **624** finishes writing its PNG and ends when frame **633** finishes. The denominator is official Blender's **382.908 s** for those same nine frames.

| Mode | Frames 625–633 | Time saved | Measured time reduction | Main process below 10% GPU, estimated time (share) |
|---|---:|---:|---:|---:|
| Official Blender | 382.908 s | — | Baseline | 118.9 s (31.04%) |
| Host BVH Prepacking (default) | 271.873 s | 111.035 s | **29.00%** | 11.3 s (4.15%) |
| Eager GPU Upload | 260.416 s | 122.492 s | **31.99%** | 10.8 s (4.16%) |

Windows WDDM samples Blender’s busiest GPU engine for the main render process about once a second. Low GPU time counts the portion of each below-threshold interval inside the nine-frame window. The two pipeline modes differ by 0.45 s, less than one sample period. [Charts, samples and calculation](https://github.com/UnitTurn/cycles-frame-pipeline/blob/b59a55f1de46c59b4c4ab48350328f16c924ea1f/benchmarks/README.md)

Launch to first PNG took 193.164 s, 200.398 s and 216.408 s respectively. v0.5.1 carries the v0.5.0 native engine. These results use the existing Ruins measurements, one run per configuration, with the first frame excluded from both elapsed-time reductions.

## Public fixture and quality

The v0.5.1 Windows package passed the original three-frame RGBA comparison on HIP. On the longer 144 × 96 fixture, all nine BVH handoffs were observed. One blue channel in frame 9 differed from stock by 1/255. The other 138,239 pixels and all alpha values matched. The small fixture took **0.979415 s** in stock Blender and **1.440376 s** with prepacking over its final nine frames (**47.06% more time**). The public test supports HIP, CUDA and OptiX device selection. The data here was measured on the RX 7800 XT. [Commands and measurements](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/benchmarks/README.md#public-fixture)

Pull requests now build both extensions and exercise their UI in official Blender. Source archives include the Apache 2.0 text alongside the project GPL license.
