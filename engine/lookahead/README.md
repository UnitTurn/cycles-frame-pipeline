# BVH and frame handoff tests

English · [简体中文](README.zh-CN.md)

## Compare prepared frames with stock Blender

Install `numpy` and `Pillow` into the system Python. On a workstation with an RX 7800 XT, run this from the project root in PowerShell. Use a new output directory on each run.

```powershell
$stock = "$env:ProgramFiles\Blender Foundation\Blender 5.2\blender.exe"
python engine/lookahead/check_stock_pipeline.py $stock .\backend\blender.exe .\work\prepared-check --prepared
```

The test generates a small scene with a moving camera, deforming reflectors and a camera-dependent World shader. It compares the three prepared RGBA frames pixel by pixel with stock Blender's sequential output. The directory contains the generated scene, logs, both sets of PNGs and `comparison.json`.

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
