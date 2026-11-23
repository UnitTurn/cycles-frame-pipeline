# Cycles Frame Pipeline 0.4.0

[简体中文发布说明](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.4.0/release/notes.zh-CN.md)

This Windows x64 release adds NVIDIA CUDA and OptiX to the engine alongside AMD HIP. CUDA uses the existing software BVH2 validation and reuse path. OptiX builds native acceleration structures in the session preparing the next frame. All three backends can overlap GPU sampling with CPU Open Image Denoise and PNG output for supported scenes.

Use the official Blender 5.2.1 LTS installation (upstream commit `9e2066aef7ef`) and download an extension and engine overlay in the same language. In Cycles preferences select the GPU backend and the card, set the render device to GPU Compute, and choose the extension's scene settings profile.

| Download | English | 简体中文 |
|---|---|---|
| Blender extension | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-0.4.0-en.zip) | [中文 ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-0.4.0-zh-CN.zip) |
| Windows x64 engine | [English ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles-frame-pipeline-windows-x64-0.4.0-en.zip) | [中文 ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles-frame-pipeline-windows-x64-0.4.0-zh-CN.zip) |

The RX 7800 XT has been tested with HIP and the RTX 3090 with CUDA and OptiX. Both NVIDIA backends produced consecutive frames in the regression scene. On the larger Ruins project, CUDA produced frames with both optimizations enabled before Windows reached its system commit limit. A full optimized Ruins sequence on the RTX 3090 remains unverified. Both device memory and available Windows system commit matter when preparing two frames.

[Installation and theoretical GPU coverage](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.4.0/README.md#gpu-and-blender-compatibility) · [Project source ZIP](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.4.0/cycles_frame_pipeline-source-0.4.0.zip)
