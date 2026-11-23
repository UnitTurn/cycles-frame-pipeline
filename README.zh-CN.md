# Cycles 帧间流水线

[English](README.md) · 简体中文

让一张显卡连续渲染 Blender 动画。GPU 采样第 **N** 帧时，Blender 先对第 **N+1** 帧做正式场景求值，第二个 Cycles 会话校验 BVH、打包场景并上传显存。轮到该帧时，已经准备好的会话直接开始采样。后台 CPU 进程同时为完成采样的帧降噪并输出编号 PNG。

**RX 7800 XT 的 1,000 帧耗时估算。** 如果一段 1080p 动画的出图节拍与 Ruins 第 624–633 帧实测相同，流水线预计节省 **3 小时 29 分 26 秒**。下表统一比较从启动到末张 PNG 写完的耗时，降幅按 `（官方耗时 − 流水线耗时）/ 官方耗时` 计算。

| 帧数与数据来源 | 官方 Blender | 发布版 | 耗时降幅 |
|---|---:|---:|---:|
| 10 帧 · 实测 | 560.25 秒 | 466.03 秒 | **16.82%** |
| 1,000 帧 · 推算 | 11 小时 29 分 41 秒 | 8 小时 00 分 15 秒 | **30.37%** |

![RX 7800 XT 十帧实测耗时降幅与一千帧推算耗时降幅](benchmarks/projection-zh.png)

估算只计一次启动耗时，用实测的九个出图间隔推算其余帧。`千帧耗时 = 首张 PNG 耗时 + 999 × (第十张 PNG 耗时 − 首张 PNG 耗时) / 9`。以启动为起点，官方的两项原始读数为 189.144 和 560.246 秒，发布版为 208.306 和 466.027 秒。镜头的几何复杂度或采样负担变化时，实际出图间隔也会变化。

[安装](#安装) · [渲染动画](#渲染动画) · [实测与成片对照](#实测与成片对照) · [从源码构建并验证](#从源码构建并验证)

## 适用场景

- **作业类型。** 按顺序渲染 Cycles 动画，前一帧采样结束与下一帧采样开始之间有明显空档。几何、相机、运动模糊和材质均按原帧序求值。两个会话同时持有设备数据，需要额外显存和系统内存。首帧仍要承担加载场景和初始化的耗时。
- **已测配置。** Windows x64、Blender **5.2.1 LTS** 提交 `9e2066aef7ef`、AMD Radeon **RX 7800 XT**、普通 HIP 和软件 BVH2。配套构建关闭了 HIP RT，下文实测均在此配置完成。
- **场景与输出。** 启用单个视图层、单视图、Combined 通道和 PNG 输出，在场景和视图层上均开启最终渲染降噪，使用 CPU Open Image Denoise。仅使用 Combined 图像和 alpha、且依赖受支持的合成器可在后台重放。多视图、参与输出的视频序列、带动画的合成节点树、局部渲染边框、自定义色彩曲线等设置需要串行处理。「并行准备下一正式帧」遇到不支持的设置会在提交时报告原因。[兼容条件](pipeline/composition.py)

## 安装

1. 安装官方 **Blender 5.2.1 LTS Windows x64**。配套程序使用同一版本的 Blender 运行库和 HIP 内核，安装脚本会检查官方构建的提交号。
2. 从[最新发行版](https://github.com/expitau-one/cycles-frame-pipeline/releases/latest)下载简体中文版的 Windows 引擎覆盖包 `cycles-frame-pipeline-windows-x64-0.3.1-zh-CN.zip`（含中文安装程序）和扩展 `cycles_frame_pipeline-0.3.1-zh-CN.zip`。两种语言的扩展使用相同的扩展 ID 和引擎，选择其中一种安装。按下例将引擎覆盖包解压到 `.\downloads\engine`，从工作目录打开 PowerShell，运行包内的中文安装脚本。按实际情况填写官方 Blender 安装位置，并为配套引擎选择一个尚不存在的目标目录。

   ```powershell
   .\downloads\engine\install_backend.ps1 `
       -PatchedExe '.\downloads\engine\blender.exe' `
       -BlenderInstall 'C:\Program Files\Blender Foundation\Blender 5.2' `
       -Destination '.\backend'
   ```

3. 运行安装到引擎目录的启动脚本，打开简体中文 Blender 窗口。

   ```powershell
   .\backend\open_blender.ps1
   ```

4. **在刚打开的窗口中**进入「编辑 → 偏好设置 → 获取扩展」，打开菜单，选择「从磁盘安装」。选中 `cycles_frame_pipeline-0.3.1-zh-CN.zip`，使用默认用户扩展仓库，启用 **Cycles 帧间流水线**。下次使用同一脚本启动。简体中文版的偏好设置和默认扩展保存在 `%LOCALAPPDATA%\CyclesFramePipeline\5.2\zh_HANS`。首次启动时会继承已有的启动配置和默认用户扩展。

**使用平时的 Blender 配置。** 直接启动 `backend\blender.exe` 时，会沿用原有 Blender 语言与偏好设置。也可以在官方 Blender 窗口中安装简体中文扩展，将「定制 Blender 程序」指向配套的 `backend\blender.exe` 后提交渲染。下文命令行用法需要源码中的脚本和配套引擎。


## 渲染动画

**通过 Blender 界面。** 在「渲染属性 → Cycles 帧间流水线」选择当前场景或磁盘上的 `.blend`，设置 PNG 输出目录和「Cycles 原生降噪与输出」。勾选「优化原版 BVH（配套引擎）」，在「BVH 输入」中选择「并行准备下一正式帧」，点击「启动流水线渲染」。按照千帧示例，将场景帧范围设为 1–1000、步长设为 1。面板按写完的 PNG 统计进度。大型场景可以从空白 Blender 窗口选择磁盘文件提交。

**通过命令行。** 在项目根目录运行，把 `.\scene.blend` 换成自己的场景。下例使用已保存的渲染设置，输出 `0001.png` 到 `1000.png`。使用 GPU 时，请先在 Blender 中选好 HIP 渲染设备。

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 1000 --step 1 `
    --profile scene --mode native --bvh-input prepared --post-threads 6
```

| 参数 | 用途 |
|---|---|
| `--bvh-input prepared` | 启用双会话，一边采样当前帧，一边正式准备下一帧。配合 `--mode native` 使用。 |
| `--profile scene` / `ruins-hip256` | 沿用场景设置，或选择 RX 7800 XT 实测预设，使用普通 HIP、最多 256 采样和 0.01 自适应阈值。 |
| `--existing error` / `skip` / `replace` | 遇到已有 PNG 时退出（默认）、跳过或覆盖。 |

## 实测与成片对照

**Ruins** 场景按 624–633 原顺序连续渲染，1920×1080、RX 7800 XT、普通 HIP、持久化数据、最多 256 个自适应采样，阈值 0.01，CPU OIDN 六线程。官方 Blender 与流水线各完整渲染一次。

![连续十帧的实测耗时、GPU 利用率和专用显存峰值](benchmarks/overview-zh.png)

| 指标 | 官方 Blender | 发布版 |
|---|---:|---:|
| 启动到首张 PNG 写完 | 189.14 秒 | 208.31 秒 |
| 启动到末张 PNG 写完 | 560.25 秒 | **466.03 秒** |
| 后九帧平均出图间隔 | 41.23 秒 | **28.64 秒** |
| 首张 PNG 写完后的平均 GPU 利用率 | 69.91% | **94.85%** |
| 首张 PNG 写完后 GPU 利用率低于 10% 的时长 | 81.82 秒 | **3.00 秒** |
| 专用显存峰值 | 8.62 GiB | **12.29 GiB** |
| 系统提交内存峰值 | 73.10 GiB | **85.21 GiB** |

从启动到末张 PNG 写完，流水线比官方 Blender 节省 **94.22 秒（16.82%）**。九次切帧时，下一帧都在当前帧最后一批 GPU 采样结束前准备就绪。相邻两帧采样之间的间隔中位数为 **0.139 秒**。GPU 利用率约每秒采样一次，统计整张卡。系统提交内存可由物理内存或 Windows 页面文件承载，两组实测的物理内存使用峰值均为 31.95 GiB。

**画面对照。** 解码十对 PNG 后，共 20,736,000 个像素，其中 5,343 个像素的 RGB 与官方成片相差 1 个 8 位色阶，其余像素的 RGB 和全部 alpha 完全一致。两个会话交接时会继承同一份环境光重要性采样表，世界材质变化时重新计算。另用正式发行程序渲染四帧动画，在第 3 帧改变世界亮度，四张 RGBA 与官方均逐像素一致。

Ruins 生产场景为私有素材。仓库提供实测数据、图表重绘脚本和用于验证画面一致性的程序化小场景。简体中文和英文发行包使用相同的 Windows 渲染程序。相较于十帧计时构建，发布引擎在继承环境光采样表前多了两项配置一致性检查，本次实测配置固定。[基准数据、逐秒曲线与测量方法](benchmarks/README.zh-CN.md)

## 从源码构建并验证

构建需要 Python 3.11+、Git 和 Git LFS、CMake、Ninja、LLVM **20.1.0**（`clang-cl`）、x64 MSVC **14.44** 头文件、库与可再发行组件、Windows SDK **10.0.26100.0**，以及匹配的官方 Blender。脚本会取得固定提交的 Blender 源码和 Windows 依赖，应用补丁，并将官方 HIP 内核复制到配套构建中。在选好对应 MSVC 工具和可再发行组件的 Visual Studio Developer PowerShell 中，从项目根目录执行以下命令。LLVM 路径按本机安装位置填写。

```powershell
.\engine\build_backend.ps1 -ClangDir 'C:\Program Files\LLVM' `
    -MsvcDir $env:VCToolsInstallDir -RedistDir $env:VCToolsRedistDir -InstallDir .\backend
python tools/package.py
```

两个语言版本的插件 ZIP 和公共源码 ZIP 输出到 `dist/`。省略 `-InstallDir` 时，配套引擎默认安装到 `work/clang-release/`。源码与依赖已就绪后，使用 `-Offline` 可复用本地检出目录。[构建脚本](engine/build_backend.ps1) · [Cycles 补丁](engine/patches)

在 RX 7800 XT 上，以下测试会生成一个世界材质读取相机坐标的小型动画场景，分别用官方和配套引擎渲染三帧，比较解码后的 RGBA 像素。请为本次测试指定新的输出目录。

```powershell
python -m pip install numpy pillow
python engine/lookahead/check_stock_pipeline.py `
    'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
    .\backend\blender.exe .\parity-check --prepared
```

## 许可证

项目以 **GPL-3.0-or-later** 发布。上游 Blender 和 Cycles 文件保留各自的许可证声明。[许可证全文](COPYING)
