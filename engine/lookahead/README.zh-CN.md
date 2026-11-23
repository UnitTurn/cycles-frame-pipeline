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

在 RX 7800 XT 上，系统 Python 安装 `numpy` 和 `Pillow` 后运行以下命令，输出路径应为新目录。脚本生成移动的相机、形变反射物和读取相机坐标的世界材质，将定制引擎正式帧交接的三张解码 RGBA 与官方串行渲染逐像素比较。

```powershell
$stock = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\prepared-check --prepared
```

## Blender 端到端测试

使用项目定制的 Blender 二进制。从工作站的 PowerShell 运行：

```powershell
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-name "RX 7800 XT" --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device CPU --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-blas --bvh-time-steps 1 --motion-blur --work .\work\bvh-e2e
```

每次会建立独立的测试结果目录。检查项包括实际采样设备、BVH2 布局、禁用硬件光追、第二帧采用预建结果并更新边界、第三帧拓扑变化回退，以及三帧像素与同一程序的原始同步路径一致。

`--hip-blas` 用带形变的网格、移动的刚体、静止网格和最后加入的网格，比较原始普通 HIP 与启用几何级 BVH 的渲染结果。本机 RX 7800 XT 在实际快门运动和一个 BVH 时间步下，三帧最大像素差均为 0。前两帧顶层各只有 3 个实例引用，各帧调度更新的几何级 BVH 数量为 3、1、2。
