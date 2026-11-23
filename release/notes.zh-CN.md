# Cycles Frame Pipeline 0.3.1 发布说明

请选择同一种语言的插件和 Windows 引擎包。中文版插件使用中文控件、提示和运行状态。中文版引擎包提供中文安装说明和提示。中英文插件共用同一个扩展 ID，两种引擎包使用相同的渲染程序。

安装后，在新的引擎目录运行 `open_blender.ps1` 打开中文 Blender，在该窗口从磁盘安装中文插件 ZIP。每种语言分别保存偏好设置和启用的扩展，下次打开时继续使用。

[中文版 Blender 插件](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles_frame_pipeline-0.3.1-zh-CN.zip) · [中文版 Windows x64 引擎包](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles-frame-pipeline-windows-x64-0.3.1-zh-CN.zip) · [通用项目源码包](https://github.com/expitau-one/cycles-frame-pipeline/releases/download/v0.3.1/cycles_frame_pipeline-source-0.3.1.zip)

需要官方 Windows x64 Blender 5.2.1 LTS，提交 `9e2066aef7ef`。在 Blender 中从磁盘安装插件 ZIP，按引擎包内说明创建独立运行目录。[安装和使用](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.1/README.zh-CN.md)

### 十帧实测与千帧推算

| 帧数 | 官方 Blender | 发布版 | 总耗时减少 |
|---|---:|---:|---:|
| 10 帧实测 | 560.25 秒 | 466.03 秒 | 94.22 秒（16.82%） |
| 1,000 帧推算 | 11 小时 29 分 41 秒 | 8 小时 00 分 15 秒 | 3 小时 29 分 26 秒（30.37%） |

RX 7800 XT 上，首张 PNG 写完之后的整卡 GPU 平均利用率从 69.91% 提升到 94.85%，专用显存峰值从 8.62 GiB 升至 12.29 GiB。十帧相对官方的最大 RGB 通道差均为 1/255，透明通道全部一致。千帧推算分别采用两组实测首帧耗时，加上 999 个后九帧平均出图间隔，假设后续帧的渲染复杂度相近。两行的降幅都以相同帧数下的官方总耗时为分母。

![十帧实测与千帧推算的耗时降幅](https://raw.githubusercontent.com/expitau-one/cycles-frame-pipeline/v0.3.1/benchmarks/projection-zh.png)

[实测图表、逐秒数据与推算方法](https://github.com/expitau-one/cycles-frame-pipeline/blob/v0.3.1/benchmarks/README.zh-CN.md)
