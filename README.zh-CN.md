# Cycles 帧间流水线

[English](README.md) · 简体中文

Cycles 帧间流水线默认使用**主机端 BVH 预打包**。对支持的软件 BVH2 场景，GPU 采样第 **N** 帧时，Blender 按原帧序求值第 **N+1** 帧，Cycles 在 CPU 上正式校验几何输入、完成 BVH 打包，将结果留在系统内存。切帧时，同一个 Cycles 会话直接取包上传并开始采样。前一帧的处理与 PNG 输出由后台 CPU 进程完成。

Windows 引擎包含 AMD HIP、NVIDIA CUDA 和 NVIDIA OptiX。本页的主机端 BVH 预打包基准来自 RX 7800 XT 的 HIP 实测。[显卡与 Blender 兼容范围](#显卡与-blender-兼容范围) · [Ruins 基准](benchmarks/README.zh-CN.md)

<a id="渲染性能基准"></a><a id="实测与成片对照"></a>

**Ruins 动画，Radeon RX 7800 XT。** 从第 624 帧 PNG 写完计时，到第 633 帧 PNG 写完，官方 Blender 渲染后九帧用时 382.908 秒，主机端 BVH 预打包用时 271.873 秒（**耗时降低 29.00%**），提前上传用时 260.416 秒（**降低 31.99%**）。启动与首帧耗时单列。[逐帧数据、硬件、估算与画质对照](benchmarks/README.zh-CN.md)

[安装](#安装) · [渲染动画](#渲染动画) · [从源码构建并验证](#从源码构建并验证)

## 适用场景

- **作业类型。** 适用于相邻帧 GPU 采样之间有明显空档的 Cycles 动画。上一帧的采样时间越能覆盖下一帧的 BVH 准备时间，越能缩短切帧等待。系统内存需容纳下一帧打好的包，显卡只保留当前设备场景。首帧仍要加载场景和初始化。
- **场景与输出。** 启用单个视图层、单视图、Combined 通道和 PNG 输出，在场景和视图层上均开启最终渲染降噪，使用 CPU Open Image Denoise。仅使用 Combined 图像和 alpha、且依赖受支持的合成器可在后台重放。多视图、参与输出的视频序列、带动画的合成节点树、局部渲染边框、自定义色彩曲线等设置需要串行处理。默认的自动模式可回退到串行输出。需要强制使用指定流水线时，传入 `--fallback error`。[兼容条件](pipeline/composition.py)

## 显卡与 Blender 兼容范围

配套引擎使用官方 **Blender 5.2.1 LTS Windows x64**，提交号 `9e2066aef7ef`。安装程序从该版本取得运行库和 GPU 内核。其他 Blender 版本（包括其他 5.2.x 构建）、Linux 和 macOS 均需单独适配和验证引擎。

| 后端 | 项目实机验证 | Windows x64 理论范围 |
|---|---|---|
| AMD HIP | Radeon RX 7800 XT，软件 BVH2 | RDNA 1 及更新架构，例如 Radeon RX 5000、6000、7000 和 9000 系列。Blender 列出的 Windows 最低驱动为 Radeon Software 24.9.1 或 Radeon PRO Software 24.Q4。 |
| NVIDIA CUDA | v0.4.0 已在 RTX 3090 上验证渲染。0.5.0 的软件 BVH2 路径在设计上支持主机端预打包。 | 计算能力 5.0 及以上，驱动能加载对应的 Blender CUDA 内核。 |
| NVIDIA OptiX | v0.4.0 已在 RTX 3090 上验证渲染。OptiX 使用自己的原生加速结构。 | 计算能力 5.0 及以上，NVIDIA 驱动 575 或更新。RTX 显卡可使用 RT 核心。 |

理论范围依据本项目固定的 Blender 5.2 运行时要求。Windows 包提供单卡 HIP、CUDA 和 OptiX。公开耗时来自下方指定的 AMD 配置。[Blender 5.2 官方 GPU 要求](https://docs.blender.org/manual/zh-hans/5.2/render/cycles/gpu_rendering.html) · [NVIDIA 显卡计算能力查询](https://developer.nvidia.com/cuda/gpus)

在符合条件的场景中，HIP 和 CUDA 提前校验并打包原生软件 BVH2。使用默认上传策略时，OptiX 在切帧时构建自己的设备加速结构。也可显式选择提前上传，由第二个 Cycles 会话准备下一帧的设备数据，需要更多显存。

## 安装

1. 安装[官方 Blender 5.2.1 LTS Windows x64 版](https://download.blender.org/release/Blender5.2/)。配套引擎使用构建 `9e2066aef7ef` 的运行库和 GPU 内核。
2. 下载[通用 Windows 引擎包](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles-frame-pipeline-windows-x64-0.5.1.zip)和[中文扩展](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-zh-CN.zip)。将引擎解压到 `.\downloads\engine`，从工作目录运行以下命令。

   ```powershell
   .\downloads\engine\install_backend.ps1 -Language zh-CN -Destination .\backend
   .\backend\open_blender.ps1
   ```

   目标须为新目录。官方 Blender 位于其他位置时，再传入 `-BlenderInstall 'C:\路径\Blender 5.2'`。安装器会分别报告是否找到 HIP、CUDA 和 OptiX 内核文件。使用同一引擎包传入 `-Language en` 可创建英文配置。
3. 在刚打开的 Blender 窗口选择「编辑 → 偏好设置 → 获取扩展 → 菜单 → 从磁盘安装」，选择中文扩展 ZIP，在默认用户仓库中启用。启动器将中文配置放在 `%LOCALAPPDATA%\CyclesFramePipeline\5.2\zh_HANS`，首次运行会导入现有启动设置和默认用户扩展。若从官方 Blender 提交任务，可在那里安装扩展，将「定制 Blender 程序」指向新的 `backend\blender.exe`。直接打开这个程序会使用常规 Blender 配置。

## 渲染动画

**选择显卡。** 在用于渲染的 Blender 配置中打开「编辑 → 偏好设置 → 系统 → Cycles 渲染设备」，选择 **HIP**、**CUDA** 或 **OptiX**，只勾选目标显卡并保存偏好设置。在源场景的「渲染属性 → Cycles → 设备」中选择「GPU 计算」。最终渲染降噪选择 **OpenImageDenoise**，关闭降噪的「使用 GPU」。从磁盘提交时先保存场景。

**通过 Blender 界面。** 在「渲染属性 → Cycles 帧间流水线」选择当前场景或磁盘上的 `.blend`，选择「使用场景设置」，设置 PNG 输出目录，点击「启动流水线渲染」。新配置默认使用「主机端 BVH 预打包」。千帧示例将场景帧范围设为 1–1000，步长设为 1。大型场景可从空白 Blender 窗口提交磁盘文件。

**通过命令行。** 在项目根目录运行，把 `.\scene.blend` 换成自己的场景。下例使用已保存的渲染设置，输出 `0001.png` 到 `1000.png`。后台进程读取其启动时所用 Blender 配置中的渲染设备偏好。

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 1000 --step 1 `
    --post-threads 6
```

| 参数 | 用途 |
|---|---|
| `--host-bvh-prepacking` | 显式选择默认的原生预打包模式。也接受别名 `--defer-upload`。 |
| `--eager-upload` | 当前帧采样时，由第二个 Cycles 会话提前准备下一帧并上传显存。 |
| `--profile scene` / `ruins-hip256` | HIP、CUDA 和 OptiX 均可沿用场景设置。可选的 Ruins 预设会指定 RX 7800 XT 和 HIP，最多 256 采样，自适应阈值 0.01。 |
| `--existing error` / `skip` / `replace` | 遇到已有 PNG 时退出（默认）、跳过或覆盖。 |

提前打包要求后台画面只有一个渲染块。启用逐批像素抖动、需要按需加载纹理瓦片，或几何需要 GPU 真置换时，引擎仍在切帧后完成相应更新。日志中的 `host_bvh_ready` 表示下一帧的包已在系统内存就绪，`bvh_pack_consumed` 表示切帧后已取用。OptiX 使用自己的加速结构构建路径。


## 从源码构建并验证

构建需要 Python 3.11+、Git 和 Git LFS、CMake、Ninja、LLVM **20.1.0**（`clang-cl`）、x64 MSVC **14.44** 头文件、库与可再发行组件、Windows SDK **10.0.26100.0**，以及匹配的官方 Blender。脚本会取得固定提交的 Blender 源码和 Windows 依赖，应用补丁，并将官方 HIP、CUDA 和 OptiX 内核复制到配套构建中。构建 OptiX 后端时，脚本会获取固定版本的 NVIDIA OptiX 8.0.0 头文件。如已安装对应 SDK，可传入 `-OptixDir <SDK 根目录>`。在选好对应 MSVC 工具和可再发行组件的 Visual Studio Developer PowerShell 中，从项目根目录执行以下命令。LLVM 路径按本机安装位置填写。

```powershell
.\engine\build_backend.ps1 -ClangDir 'C:\Program Files\LLVM' `
    -MsvcDir $env:VCToolsInstallDir -RedistDir $env:VCToolsRedistDir -InstallDir .\backend
python tools/package.py
```

两个语言版本的插件 ZIP 和公共源码 ZIP 输出到 `dist/`。省略 `-InstallDir` 时，配套引擎默认安装到 `work/clang-release/`。源码与依赖已就绪后，使用 `-Offline` 可复用本地检出目录。[构建脚本](engine/build_backend.ps1) · [Cycles 补丁](engine/patches)

每个 PR 会打包两种语言的扩展，并用官方 Blender 检查其面板。公开动画样例可在 HIP、CUDA 或 OptiX 上与官方 Blender 对照。[切帧测试与运行命令](engine/lookahead/README.zh-CN.md) · [发行引擎的实测耗时和画质](benchmarks/README.zh-CN.md#公开样例)

## 许可证

项目采用 [GPL-3.0-or-later](COPYING)。标注 `SPDX-License-Identifier: Apache-2.0` 的 Cycles 文件和测试代码采用 [Apache 2.0 许可证](LICENSES/Apache-2.0.txt)。上游文件保留各自的许可声明。[OptiX 声明](engine/OptiX-NOTICE.md)
