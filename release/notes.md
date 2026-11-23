# Cycles Frame Pipeline v0.5.0 — Host BVH Prepacking

[简体中文发布说明](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/release/notes.zh-CN.md)

While the GPU samples one frame, Blender evaluates the next frame in animation order. For eligible HIP and CUDA scenes, Cycles validates and packs that frame’s software BVH2 on the CPU. Once the GPU releases the previous frame, Cycles uploads the prepared data and starts sampling. On the Ruins animation, all nine frame transitions used their prepared BVH exactly once. The median time between sampling frames was **1.47 seconds**.

## Performance on the Radeon RX 7800 XT

Ruins frames 624–633 ran in sequence at 1920 × 1080 on a single RX 7800 XT using HIP, persistent data, up to 256 adaptive samples and a noise threshold of 0.01. Each configuration ran once. Time to PNG starts at process launch.

| Metric | Official Blender 5.2.1 LTS | v0.5.0 host prepacking |
|---|---:|---:|
| First PNG | 193.16 s | 200.40 s |
| Tenth PNG | 576.07 s | **472.27 s** |
| Mean interval between PNGs after the first | 42.55 s | 30.21 s |
| Mean whole-GPU utilization across those nine intervals | 71.39% | 91.52% |
| Peak dedicated GPU memory, whole card | 8.53 GiB | 8.46 GiB |
| Peak Windows committed memory, whole system | 73.89 GiB | 76.31 GiB |
| Time to the 1,000th PNG, projected | 11 h 51 min 36 s | **8 h 26 min 18 s** |

Time to the tenth PNG fell by **103.80 seconds (18.02%)**. Counting startup once and extending the nine measured intervals to 999 gives an estimated **3 h 25 min 18 s (28.85%)** saved over 1,000 frames at the same pace. The timings come from the release candidate. The packaged engine also handles changes to UV and motion passes and preserves the scene when switching to serial output mid-animation. Ruins used the same passes and preparation mode throughout. [Benchmark data and charts](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/benchmarks/README.md)

## Installation and use

Install official Blender **5.2.1 LTS for Windows x64**, build `9e2066aef7ef`. Select the extension and Windows engine overlay in the same language. The overlay installer uses the runtime and GPU kernels from that Blender installation. [Installation guide](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.md#install)

| Package | English | 简体中文 |
|---|---|---|
| Blender extension | [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-0.5.0-en.zip) | [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-0.5.0-zh-CN.zip) |
| Windows x64 engine overlay | [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles-frame-pipeline-windows-x64-0.5.0-en.zip) | [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles-frame-pipeline-windows-x64-0.5.0-zh-CN.zip) |

The native command-line mode uses host BVH prepacking by default on eligible scenes. Add `--eager-upload` to prepare the next frame in a second GPU session. In the panel, clear **Host BVH Prepacking** to select early upload. [Render instructions](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.md#render-an-animation) · [Project source ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-source-0.5.0.zip)

## GPU coverage

The AMD production benchmark above covers HIP with software BVH2. CUDA also supports the new software BVH2 path in the engine. OptiX uses NVIDIA’s native acceleration structures and builds them through the selected GPU session. Earlier RTX 3090 tests completed a three-frame animation on both CUDA and OptiX. Production timings for v0.5.0 on NVIDIA remain unmeasured. [GPU and Blender compatibility](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.md#gpu-and-blender-compatibility)
