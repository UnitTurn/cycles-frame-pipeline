# Cycles 帧间流水线 v0.5.1 · 中英文通用 Windows 引擎

[中文安装指南](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/README.zh-CN.md#安装) · [English guide](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/README.md#install) · [English release notes](https://github.com/UnitTurn/cycles-frame-pipeline/releases/tag/v0.5.1)

下载一份通用 Windows 引擎和一份所选语言的扩展。安装时传入 `-Language zh-CN` 或 `-Language en`，即可继续使用对应语言的独立配置。安装器会报告在 Windows x64 官方 Blender 5.2.1 LTS（构建 `9e2066aef7ef`）中找到的 HIP、CUDA 和 OptiX 内核文件。

| 下载内容 | 文件 |
|---|---|
| Windows x64 通用引擎 | [引擎 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles-frame-pipeline-windows-x64-0.5.1.zip) |
| Blender 扩展 | [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-zh-CN.zip) · [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-en.zip) |
| 对应工程源码和补丁 | [源码 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-source-0.5.1.zip) |

## Ruins 首帧之后的实测性能

在 RX 7800 XT 上使用 HIP 渲染 1080p 动画。从第 **624** 帧的 PNG 写完计时，到第 **633** 帧的 PNG 写完。实测降幅以官方 Blender 渲染相同后九帧的 **382.908 秒**为分母。

| 模式 | 第 625–633 帧 | 节省时间 | 实测耗时降幅 |
|---|---:|---:|---:|
| 官方 Blender | 382.908 秒 | — | 基准 |
| 主机端 BVH 预打包（默认） | 271.873 秒 | 111.035 秒 | **29.00%** |
| 提前上传 | 260.416 秒 | 122.492 秒 | **31.99%** |

从启动到首张 PNG 写完，三组分别为 193.164 秒、200.398 秒、216.408 秒。v0.5.1 沿用 v0.5.0 的原生引擎。以上结果根据已有 Ruins 实测记录重算，每种配置各跑一次，两个降幅都已扣除首帧。[原始数据、方法与估算](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/benchmarks/README.zh-CN.md)

## 公开样例与画质

v0.5.1 Windows 包在 HIP 上通过了原有三帧逐像素 RGBA 对照。将 144 × 96 样例延长至十帧后，九次切帧均提前打包并各取用一次。第 9 帧一个像素的蓝通道与官方相差 1/255，其余 138,239 个像素和全部 alpha 值一致。小样例后九帧官方用时 **0.979415 秒**，预打包用时 **1.440376 秒**（**多用时 47.06%**）。公开测试可选择 HIP、CUDA 或 OptiX。本组数据来自 RX 7800 XT。[复现命令与结果](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.1/benchmarks/README.zh-CN.md#公开样例)

普通 PR 会自动构建两种语言的扩展并在官方 Blender 中检查面板。源码包同时附带项目 GPL 许可证和 Apache 2.0 许可证正文。
