# BVH 预建验证

[English](README.md) · 简体中文

## 原生 CPU 探针

Windows x64 的本地探针从下述源码编译，运行时读取对应 Blender 5.2.1 安装的 `blender.shared` 依赖。

探针生成 50,000 个三角形引用，连续四帧移动其包围盒并改变可见性。每帧检查所有叶节点的图元索引、边界与掩码，以及父节点覆盖范围。随后增加一个图元，验证身份不匹配时同步回退。帧间留出 1.2 秒供后台建树，模拟 GPU 工作时间。该间隔不计入前台耗时。一次本机实测的四帧中位数为同步建树 15.003 ms、命中后的前台校验与更新 3.670 ms，后台建树约 24–30 ms。此测量从已有图元引用开始，未计入 Blender 场景求值、图元提取、GPU 打包上传及实际采样。

**重新编译。** 需要 x64 Visual Studio 开发者命令提示符、Python 3、已应用项目补丁的 Blender 5.2.1 源码、对应的 Windows 依赖，以及已配置的 Release Ninja 构建目录中的 `bf_intern_guardedalloc.lib`。在该命令提示符中运行：

```bat
python engine\lookahead\build_native_probe.py
set "PATH=%ProgramFiles%\Blender Foundation\Blender 5.2\blender.shared;%PATH%"
work\native-probe\bvh_probe.exe 50000 1200
```

构建脚本默认使用 `work/blender`、`work/build` 和 `work/windows_lib`，可分别用 `--source`、`--build` 和 `--libs` 指定。它读取该配置的实际编译选项，在独立目录编译原生 BVH 和所需依赖。源码布局固定于 Blender 5.2.1 的 `9e2066aef7ef`。

## 正式帧交接的像素检查

使用官方 Blender 5.2.1 和已安装的项目引擎，在同一张显卡上渲染程序化动画。每次选择一个新的输出目录。

```powershell
python -m pip install numpy pillow
$stock = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\parity --device HIP --prepared
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\ten --device HIP --prepared --frames 10
```

NVIDIA 用户可指定 `--device CUDA` 或 `--device OPTIX`。有多张显卡时，加 `--device-name` 指定型号关键词或完整 Cycles 设备 ID。两个渲染进程会分别选中同一张卡。HIP 和 CUDA 会检查首帧之后的每一帧是否恰好准备并取用一次主机端 BVH，OptiX 验证其原生加速结构的切帧流程。

输出目录包含生成的场景、两组 PNG、日志、`comparison.json` 和 `timings.json`。十帧测试会拉长动画，从首张 PNG 到第十张 PNG 计算后九帧的耗时降幅。严格画质检查在保存数据后执行，任何像素差异都会返回非零退出码。本次发行版三帧完全一致，十帧样例在 RX 7800 XT 上出现一个像素的蓝通道相差一个 8 位色阶。[公开样例实测](../../benchmarks/README.zh-CN.md#公开样例)

## Blender 端到端测试

使用项目定制的 Blender 二进制。从工作站的 PowerShell 运行：

```powershell
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-name "RX 7800 XT" --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device CPU --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-blas --bvh-time-steps 1 --motion-blur --work .\work\bvh-e2e
```

每次会建立独立的测试结果目录。检查项包括实际采样设备、BVH2 布局、禁用硬件光追、第二帧采用预建结果并更新边界、第三帧拓扑变化回退，以及三帧像素与同一程序的原始同步路径一致。

`--hip-blas` 用带形变的网格、移动的刚体、静止网格和最后加入的网格，比较原始普通 HIP 与启用几何级 BVH 的渲染结果。本机 RX 7800 XT 在实际快门运动和一个 BVH 时间步下，三帧最大像素差均为 0。前两帧顶层各只有 3 个实例引用，各帧调度更新的几何级 BVH 数量为 3、1、2。

## 快照格式测试

应用引擎补丁后，在 x64 Visual Studio 开发者 PowerShell 中运行以下命令。测试直接编译 Cycles 使用的头文件。

```powershell
New-Item -ItemType Directory -Force .\work\snapshot | Out-Null
cl /nologo /std:c++17 /EHsc /Iwork\blender\intern\cycles engine\lookahead\check_snapshot.cpp /Fowork\snapshot\check.obj /Fework\snapshot\check.exe
.\work\snapshot\check.exe .\work\snapshot
```
