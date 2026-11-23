# Cycles 帧间流水线 v0.5.0 — 主机端 BVH 预打包

[English release notes](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/release/notes.md)

GPU 为当前帧采样时，Blender 按动画顺序求值下一帧。在符合条件的 HIP 和 CUDA 场景中，Cycles 提前在 CPU 上校验并打包下一帧用于光线追踪的软件 BVH2。前一帧释放 GPU 后，Cycles 直接上传打包结果并开始采样。Ruins 动画的九次切帧均直接使用了各自预先打好的 BVH，每份使用一次。前帧结束采样到后帧开始采样的中位间隔为 **1.47 秒**。

## Radeon RX 7800 XT 实测

Ruins 工程使用单张 RX 7800 XT，以 HIP 连续渲染第 624–633 帧。分辨率为 1920 × 1080，开启持久数据，最高 256 个自适应采样，噪声阈值为 0.01。每种配置完整运行一次，出图耗时从进程启动开始计算。

| 指标 | 官方 Blender 5.2.1 LTS | v0.5.0 主机端预打包 |
|---|---:|---:|
| 首张 PNG 耗时 | 193.16 秒 | 200.40 秒 |
| 第十张 PNG 耗时 | 576.07 秒 | **472.27 秒** |
| 首张之后九个出图间隔的均值 | 42.55 秒 | 30.21 秒 |
| 上述九个间隔的整卡平均 GPU 利用率 | 71.39% | 91.52% |
| 整卡专用显存峰值 | 8.53 GiB | 8.46 GiB |
| Windows 整机提交内存峰值 | 73.89 GiB | 76.31 GiB |
| 第 1,000 张 PNG 耗时（推算） | 11 小时 51 分 36 秒 | **8 小时 26 分 18 秒** |

实测十帧节省 **103.80 秒（18.02%）**。按首帧启动一次、随后 999 个出图间隔沿用本次九个间隔的均值推算，1,000 帧可节省 **3 小时 25 分 18 秒（28.85%）**。计时使用发布候选引擎。最终包还处理了动画中途变更 UV 或运动通道、回退至串行输出两种情况。Ruins 的通道设置固定，十帧均走预打包路径。[基准数据与图表](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/benchmarks/README.zh-CN.md)

## 安装与使用

安装官方 **Blender 5.2.1 LTS Windows x64**，构建提交号为 `9e2066aef7ef`。选择同一语言的 Blender 扩展和 Windows 引擎覆盖包。覆盖包中的安装脚本会从该版本的官方 Blender 获取运行库和 GPU 内核。[安装指南](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.zh-CN.md#安装)

| 下载项 | 简体中文 | English |
|---|---|---|
| Blender 扩展 | [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-0.5.0-zh-CN.zip) | [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-0.5.0-en.zip) |
| Windows x64 引擎覆盖包 | [中文 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles-frame-pipeline-windows-x64-0.5.0-zh-CN.zip) | [English ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles-frame-pipeline-windows-x64-0.5.0-en.zip) |

命令行原生模式默认在符合条件的场景中启用主机端 BVH 预打包。加上 `--eager-upload` 可使用第二个 GPU 会话，提前上传下一帧。在面板中取消勾选「主机端 BVH 预打包」也可切换到提前上传。[渲染方法](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.zh-CN.md#渲染动画) · [项目源码 ZIP](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.0/cycles_frame_pipeline-source-0.5.0.zip)

## 显卡支持范围

上表为 AMD HIP 与软件 BVH2 在生产工程上的实测。引擎的 CUDA 后端也支持此次新增的软件 BVH2 预打包。OptiX 使用 NVIDIA 原生加速结构，由所选 GPU 会话构建。此前已在 RTX 3090 上分别用 CUDA 和 OptiX 跑通连续三帧动画。v0.5.0 在 NVIDIA 上的生产工程耗时仍待实测。[显卡与 Blender 兼容范围](https://github.com/UnitTurn/cycles-frame-pipeline/blob/v0.5.0/README.zh-CN.md#显卡与-blender-兼容范围)
