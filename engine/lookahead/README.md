# BVH and frame handoff tests

English · [简体中文](README.zh-CN.md)

## Compare prepared frames with stock Blender

Use the official Blender 5.2.1 executable and the installed project engine on the same GPU. Use a new output directory for each run.

```powershell
python -m pip install numpy pillow
$stock = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\parity --device HIP --prepared
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\ten --device HIP --prepared --frames 10
```

Choose `--device CUDA` or `--device OPTIX` for NVIDIA. If several cards are available, pass `--device-name` with a name substring or the full Cycles device ID. Both processes explicitly select the same GPU. HIP and CUDA check that each frame after the first produces and consumes one host BVH. OptiX exercises its native acceleration structures.

The script saves the generated scene, both PNG sequences, logs, `comparison.json` and `timings.json`. The ten-frame run stretches the animation and calculates elapsed-time reduction from the first completed PNG to the tenth. Each PNG difference is recorded before the strict pixel check returns a nonzero exit code. The release's three-frame fixture matched exactly. The ten-frame test recorded one blue-channel difference of one 8-bit level on the RX 7800 XT. [Published measurements](../../benchmarks/README.md#public-fixture)

## Exercise BVH changes inside Blender

```powershell
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-name "RX 7800 XT" --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device CPU --work .\work\bvh-e2e
python engine/lookahead/check_render.py .\backend\blender.exe --device HIP --hip-blas --bvh-time-steps 1 --motion-blur --work .\work\bvh-e2e
```

These generated scenes cover reuse, changed bounds, topology changes and decoded output equivalence to the same engine's synchronous path. The HIP tests use software BVH2. The experimental `--hip-blas` test includes a deforming mesh, moving rigid geometry, static geometry and an object added at the end. A three-frame RX 7800 XT run with motion blur and one BVH time step matched every pixel. The first two frames had three top-level instance references each. The geometry update counts were three, one and two.

## Build the optional standalone CPU probe

Use a Windows x64 Visual Studio Developer Command Prompt with Python, patched Blender 5.2.1 sources (revision `9e2066aef7ef`), the matching Windows libraries and an MSVC Release/Ninja build containing `bf_intern_guardedalloc.lib`. `build_native_probe.py` defaults to `work/blender`, `work/build` and `work/windows_lib`. Override these with `--source`, `--build` and `--libs` for other MSVC build trees.

```bat
python engine\lookahead\build_native_probe.py
set "PATH=%ProgramFiles%\Blender Foundation\Blender 5.2\blender.shared;%PATH%"
work\native-probe\bvh_probe.exe 50000 1200
```

The probe moves and changes the visibility masks of 50,000 triangle references for four frames. It checks indices, bounds, masks and ancestor coverage, then introduces a primitive to exercise the synchronous fallback. The 1.2-second frame gaps allow the background builder to run. An earlier local run measured medians of 15.003 ms for synchronous construction and 3.670 ms for foreground validation and update, with 24–30 ms for the background build. The timing covers BVH processing from existing primitive references. The end-to-end production benchmark is in [benchmarks](../../benchmarks/README.md).

## Snapshot format test

After applying the engine patches, run in an x64 Visual Studio Developer PowerShell. This compiles the test against the header used by Cycles.

```powershell
New-Item -ItemType Directory -Force .\work\snapshot | Out-Null
cl /nologo /std:c++17 /EHsc /Iwork\blender\intern\cycles engine\lookahead\check_snapshot.cpp /Fowork\snapshot\check.obj /Fework\snapshot\check.exe
.\work\snapshot\check.exe .\work\snapshot
```
