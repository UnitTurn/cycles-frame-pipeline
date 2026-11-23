# Cycles Frame Pipeline 0.3.1

[简体中文发布说明](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.1/release/notes.zh-CN.md)

Choose the matching English or Simplified Chinese extension and Windows engine package. Each package uses one language. The two extensions share a Blender extension ID, and both engine packages contain the same rendering executable.

After installation, use `open_blender.ps1` in the new runtime directory to open Blender in the selected language. Install the matching extension ZIP in that window. Each language edition keeps its own preferences and enabled extensions between launches.

| Download | English | Simplified Chinese |
|---|---|---|
| Blender extension | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles_frame_pipeline-0.3.1-en.zip) | [Chinese ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles_frame_pipeline-0.3.1-zh-CN.zip) |
| Windows x64 engine | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles-frame-pipeline-windows-x64-0.3.1-en.zip) | [Chinese ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles-frame-pipeline-windows-x64-0.3.1-zh-CN.zip) |

The overlay requires official Blender 5.2.1 LTS for Windows x64, upstream build `9e2066aef7ef`. Install the extension from disk in Blender. [Installation and usage](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.1/README.md) · [Project source archive](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles_frame_pipeline-source-0.3.1.zip)

### Ten measured frames and a 1,000-frame projection

| Frame count | Official Blender | Cycles Frame Pipeline | Time saved |
|---|---:|---:|---:|
| 10 measured | 560.25 s | 466.03 s | 94.22 s (16.82%) |
| 1,000 projected | 11 h 29 min 41 s | 8 h 00 min 15 s | 3 h 29 min 26 s (30.37%) |

The test used one RX 7800 XT. After the first PNG, average whole-card GPU utilization increased from 69.91% to 94.85%. Peak dedicated GPU memory rose from 8.62 to 12.29 GiB. All ten images were within one 8-bit RGB level of official Blender, with identical alpha. The projection charges each configuration for its first frame once, followed by 999 intervals at its measured average cadence over the next nine images. It assumes subsequent frames have similar rendering costs.

![Measured and projected render-time reductions](https://raw.githubusercontent.com/expitau-one/cycles-frame-pipeline/v0.3.1/benchmarks/projection-en.png)

[Benchmark charts, measurements and calculation](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.1/benchmarks/README.md)
