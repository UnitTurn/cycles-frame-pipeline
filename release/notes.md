## English

Cycles Frame Pipeline 0.3.0 overlaps the next frame's scene evaluation, BVH preparation and upload with the current frame's GPU sampling. On the tested RX 7800 XT, 10 frames took 466.03 s versus 560.25 s with stock Blender. Peak dedicated GPU memory reached 12.29 GiB. Every decoded frame was within one 8-bit RGB level of the stock render.

- **Blender extension** — install `cycles_frame_pipeline-0.3.0.zip` from disk in Blender.
- **Windows x64 engine overlay** — extract `cycles-frame-pipeline-windows-x64-0.3.0.zip` and follow the included installation instructions. Requires official Blender 5.2.1 LTS for Windows x64, upstream build `9e2066aef7ef`.
- **Corresponding project sources** — `cycles_frame_pipeline-source-0.3.0.zip` includes the pinned build recipe, patch series, tests, documentation and benchmark data. The source tag also contains the release workflow.

[Installation and usage](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.0/README.md) · [Benchmark charts and measurements](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.0/benchmarks/README.md)

## 简体中文

0.3.0 支持在当前帧 GPU 采样期间完成下一帧的正式场景求值、BVH 准备和上传。RX 7800 XT 十帧实测从官方的 560.25 秒缩短到 466.03 秒，专用显存峰值为 12.29 GiB。每帧相对官方成片的最大 RGB 通道差均为 1/255。

- **Blender 插件** — 在 Blender 中从磁盘安装 `cycles_frame_pipeline-0.3.0.zip`。
- **Windows x64 配套引擎** — 解压 `cycles-frame-pipeline-windows-x64-0.3.0.zip`，按包内说明将引擎安装到独立目录。需要官方 Windows x64 Blender 5.2.1 LTS，提交 `9e2066aef7ef`。
- **对应项目源码** — `cycles_frame_pipeline-source-0.3.0.zip` 含固定版本的构建脚本、补丁、测试、中英说明和基准数据。仓库的源代码标签另含发布工作流。

[中文版安装和用法](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.0/README.zh-CN.md) · [性能图表和测量数据](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.0/benchmarks/README.zh-CN.md)
