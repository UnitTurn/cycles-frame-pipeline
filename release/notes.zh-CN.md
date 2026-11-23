# Cycles 帧间流水线 0.4.0

[English release notes](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.4.0/release/notes.md)

Windows x64 引擎现在提供 AMD HIP、NVIDIA CUDA 和 NVIDIA OptiX。CUDA 沿用软件 BVH2 的校验和复用逻辑。OptiX 在准备下一帧的会话中构建原生加速结构。满足场景条件时，三个后端都可以在 GPU 采样时，用 CPU 为已完成的帧执行 Open Image Denoise 并输出 PNG。

请使用官方 Windows x64 Blender 5.2.1 LTS（提交 `9e2066aef7ef`），下载同一种语言的扩展和引擎包。在 Cycles 偏好设置中选择后端并勾选显卡，渲染设备选择 GPU 计算，插件配置选择沿用场景设置。

| 下载 | 简体中文 | English |
|---|---|---|
| Blender 扩展 | [中文 ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-0.4.0-zh-CN.zip) | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-0.4.0-en.zip) |
| Windows x64 引擎 | [中文 ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles-frame-pipeline-windows-x64-0.4.0-zh-CN.zip) | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles-frame-pipeline-windows-x64-0.4.0-en.zip) |

已实机验证 RX 7800 XT 的 HIP，以及 RTX 3090 的 CUDA 和 OptiX。两种 NVIDIA 后端均在回归场景中连续出图。在较大的 Ruins 工程中，CUDA 开启两项优化后输出了部分帧，随后触及 Windows 系统提交内存上限。该卡的 Ruins 优化版完整序列尚待验证。准备双帧时需同时留出显存和系统提交内存。

[安装和理论支持范围](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.4.0/README.zh-CN.md#显卡与-blender-兼容范围) · [项目源码 ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-source-0.4.0.zip)
