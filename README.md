# Cycles Frame Pipeline

English · [简体中文](README.zh-CN.md)

Render consecutive Blender animation frames on one GPU. While Cycles samples frame **N**, Blender evaluates frame **N+1** in animation order and a second Cycles session prepares its scene and acceleration structures. At the frame boundary, the prepared session starts sampling without a second scene evaluation. A CPU worker denoises the previous frame and writes its numbered PNG.

The Windows release targets AMD HIP and NVIDIA CUDA and OptiX. Published Ruins timing and image comparisons cover the RX 7800 XT on HIP. Both NVIDIA backends completed a separate three-frame regression scene on an RTX 3090. [GPU and Blender compatibility](#gpu-and-blender-compatibility) · [Published Ruins benchmark](benchmarks/README.md)

**1,000-frame estimate on a Radeon RX 7800 XT.** If a 1080p animation sustains the throughput measured on Ruins frames 624–633, the pipeline would save about **3 h 29 min 26 s**. Both percentages use the time from launch to final PNG and the same denominator, the wall time measured for official Blender on the same card. The calculation is `(official time − pipeline time) / official time`.

| Sequence | Official Blender | Cycles Frame Pipeline | Time reduction |
|---|---:|---:|---:|
| 10 frames · measured | 560.25 s | 466.03 s | **16.82%** |
| 1,000 frames · projected | 11 h 29 min 41 s | 8 h 00 min 15 s | **30.37%** |

![Measured time reduction across ten frames and projected time reduction across 1,000 frames on the RX 7800 XT](benchmarks/projection-en.png)

The estimate counts startup once and uses the mean of the nine measured intervals for the remaining frames. The formula is `first PNG + 999 × ((tenth PNG − first PNG) / 9)`. Times are seconds from launch. The input pairs were 189.144 and 560.246 for official Blender, and 208.306 and 466.027 for Cycles Frame Pipeline. Shots with different geometry or sampling costs will have different frame intervals.

[Install](#install) · [Render an animation](#render-an-animation) · [Benchmark and image quality](#benchmark-and-image-quality) · [Build and test](#build-and-test)

## When to use it

- **Workload.** Consecutive Cycles frames with a measurable gap between one frame's last samples and the next frame's first samples. Geometry, camera, motion blur and material inputs advance in animation order. Two resident device scenes cost extra VRAM and system memory. The first frame still pays for scene loading and setup.
- **Scene and output.** Use a single enabled view layer, a single view, the Combined pass, PNG output and CPU Open Image Denoise enabled for final rendering on both scene and layer. A compositor using Combined image/alpha can be replayed when its dependencies are supported. Multiple views, active sequencer strips, animated compositor graphs, partial render borders and custom view curves are examples that require the serial path. Prepared mode reports an unsupported setting at submission. [Scene compatibility checks](pipeline/composition.py)

## GPU and Blender compatibility

The engine overlay requires the official **Blender 5.2.1 LTS for Windows x64**, build `9e2066aef7ef`. The installer uses its runtime and GPU kernels. Other Blender versions (including other 5.2.x builds), Linux and macOS require a matching engine port and separate testing.

| Backend | Tested on hardware | Theoretical coverage on Windows x64 |
|---|---|---|
| AMD HIP | Radeon RX 7800 XT, software BVH2 | RDNA 1 and newer. Examples include Radeon RX 5000, 6000, 7000 and 9000. Blender lists Radeon Software 24.9.1 or Radeon PRO Software 24.Q4 as its Windows minimum. |
| NVIDIA CUDA | GeForce RTX 3090, software BVH2 | Compute capability 5.0 or higher, with a driver able to load the matching Blender CUDA kernel. Examples include GeForce RTX 20, 30, 40 and 50 series. |
| NVIDIA OptiX | GeForce RTX 3090, native OptiX acceleration structures | Compute capability 5.0 or higher and NVIDIA driver 575 or newer. RTX cards can use their RT cores for ray tracing. |

The theoretical range follows Blender 5.2's device requirements. The official 5.2.1 Windows runtime includes CUDA cubins and a PTX fallback. Its main OptiX PTX kernel targets `sm_50`. For an untested model, the matching official build must be able to render on that backend, and both sessions must fit the available memory. Performance and image comparisons apply to the tested card, backend and workload. This release covers single-GPU operation and omits HIP RT, Intel oneAPI and Apple Metal. [Blender 5.2 GPU requirements](https://docs.blender.org/manual/en/5.2/render/cycles/gpu_rendering.html) · [NVIDIA compute capability by model](https://developer.nvidia.com/cuda/gpus)

HIP and CUDA validate the software BVH2 inputs before reusing a previous tree and rebuild when those inputs change. OptiX prepares the next frame using its own acceleration structures. All three backends can overlap next-frame preparation and CPU frame output, including CPU Open Image Denoise. Select a GPU backend for path tracing and CPU OIDN for the final denoise.

## Install

1. Install the official **Blender 5.2.1 LTS Windows x64** build. The installer checks the build hash because the patched executable uses the matching Blender runtime and HIP, CUDA and OptiX kernels.
2. For the English interface, download `cycles-frame-pipeline-windows-x64-0.4.0-en.zip` (Windows engine overlay and English installer) and `cycles_frame_pipeline-0.4.0-en.zip` (extension) from the [latest release](https://github.com/expitau-one/cycles-frame-pipeline/releases/latest). The Chinese distribution has the same extension ID and engine. Install one language edition. Extract the engine overlay to `.\downloads\engine` for the paths below. From your working directory, run the included English installer in PowerShell. Adjust the official installation path and choose a new destination directory for the side-by-side runtime.

   ```powershell
   .\downloads\engine\install_backend.ps1 `
       -PatchedExe '.\downloads\engine\blender.exe' `
       -BlenderInstall 'C:\Program Files\Blender Foundation\Blender 5.2' `
       -Destination '.\backend'
   ```

3. Open the English Blender window using the launcher installed with the backend.

   ```powershell
   .\backend\open_blender.ps1
   ```

4. **In that window**, open **Edit → Preferences → Get Extensions → menu → Install from Disk**, select `cycles_frame_pipeline-0.4.0-en.zip` and choose the default user repository. Enable **Cycles Frame Pipeline**. Use the same launcher next time. It keeps this edition's preferences and default extensions under `%LOCALAPPDATA%\CyclesFramePipeline\5.2\en_US`. On first launch, it imports the existing startup settings and default user extensions.

**Using your regular Blender profile.** Starting `backend\blender.exe` directly follows your normal Blender language and preferences. To submit from an official Blender installation, install the English extension in that window and set **Custom Blender Executable** to the patched `backend\blender.exe`. The CLI workflow below uses the repository scripts and the backend.


## Render an animation

**Select your GPU.** In the Blender profile used for rendering, open **Edit → Preferences → System → Cycles Render Devices**, choose **HIP**, **CUDA** or **OptiX**, enable the target GPU only and save preferences. In the source scene set **Render Properties → Cycles → Device** to **GPU Compute**. Select **OpenImageDenoise** for final rendering and disable **Use GPU** for that denoise. Save the scene before submitting it from disk.

**Blender UI.** In **Render Properties → Cycles Frame Pipeline**, select the current scene or a saved `.blend`, choose **Use Scene Settings**, set a PNG output directory and choose **Native Cycles Denoising and Output**. Enable **Optimize Native BVH (Custom Engine)**, select **Prepare Next Frame in Parallel**, then click **Start Pipeline Render**. For the 1,000-frame example, set the scene’s frame range to 1–1000 with a step of 1. Progress counts completed PNGs. For a large scene, an empty Blender window can submit a `.blend` from disk.

**Command line.** From the repository root, replace `.\scene.blend` with your scene. This example uses the scene's saved render settings and writes `0001.png` through `1000.png`. The background process reads the device preferences for the Blender profile it starts with.

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 1000 --step 1 `
    --profile scene --mode native --bvh-input prepared --post-threads 6
```

| Option | Use |
|---|---|
| `--bvh-input prepared` | Opt in to two sessions. One samples while the other prepares the next production frame. Requires `--mode native`. |
| `--profile scene` / `ruins-hip256` | Use saved scene settings for HIP, CUDA or OptiX. The optional Ruins preset explicitly selects the RX 7800 XT on HIP, up to 256 samples and a 0.01 adaptive threshold. |
| `--existing error` / `skip` / `replace` | Stop at an existing PNG (default), skip it, or overwrite it. |

## Benchmark and image quality

**AMD HIP.** The recorded Ruins benchmark used frames 624–633 in order, 1920×1080, RX 7800 XT, standard HIP, persistent data, up to 256 adaptive samples, threshold 0.01 and six CPU OIDN threads. Official Blender and the pipeline each rendered these ten frames once.

![Measured performance, GPU utilization and peak GPU memory for the ten-frame run](benchmarks/overview-en.png)

| Metric | Official Blender | Cycles Frame Pipeline |
|---|---:|---:|
| Launch to first PNG | 189.14 s | 208.31 s |
| Launch to final PNG | 560.25 s | **466.03 s** |
| Mean interval between subsequent PNGs | 41.23 s | **28.64 s** |
| Mean GPU utilization after first PNG | 69.91% | **94.85%** |
| Time below 10% GPU utilization after first PNG | 81.82 s | **3.00 s** |
| Peak dedicated GPU memory | 8.62 GiB | **12.29 GiB** |
| Peak system committed memory | 73.10 GiB | **85.21 GiB** |

The pipeline saved **94.22 s (16.82%)** over stock Blender from launch to the final PNG. At all nine frame transitions, preparation finished before the GPU completed its last sampling batch on the active frame. The median gap between successive sampling windows was **0.139 s**. GPU activity is whole-card utilization sampled at about 1 Hz. System commit includes memory backed by RAM or the Windows page file. Peak physical memory was 31.95 GiB in both runs.

**Image comparison.** Across ten decoded PNG pairs, 5,343 of 20,736,000 pixels differed from stock Blender by one 8-bit RGB level. All other RGB values and all alpha values matched. The two sessions inherit the same cached environment-light sampling distribution and update it when the world changes. A separate four-frame test of the release executable changed world intensity in frame 3. All four RGBA outputs matched stock pixel for pixel.

The AMD figures above come from the recorded ten-frame HIP run. A separate three-frame test of the Windows multi-backend executable on the RX 7800 XT matched the official RGBA output pixel for pixel. The production scene is private. The repository provides the measurements, a chart-generation script and a procedural image test. [AMD benchmark data, time series and methodology](benchmarks/README.md)

**NVIDIA CUDA and OptiX.** On the RTX 3090, both backends completed the three-frame regression scene with overlapping frame preparation and CPU postprocessing. Decoded PNGs were compared with the corresponding official backend. On the original Ruins scene, official CUDA completed the full sequence and CUDA prepared mode produced several frames before reaching the Windows system commit limit. For scenes this large, both GPU memory and the host's combined RAM and page-file capacity matter. The public timing and throughput figures above apply to the RX 7800 XT.

## Build and test

To build the backend from source, use Python 3.11+, Git with Git LFS, CMake, Ninja, LLVM **20.1.0** (`clang-cl`), x64 MSVC **14.44** headers/libraries/redistributables, Windows SDK **10.0.26100.0** and the matching official Blender installation. The script fetches the pinned Blender source and Windows dependencies, applies the patch series and copies the matching official HIP, CUDA and OptiX kernels into the build. For the OptiX host backend it fetches the pinned NVIDIA OptiX 8.0.0 headers. To use an existing SDK, pass `-OptixDir <SDK root>`. In a Visual Studio Developer PowerShell with those MSVC tool and redist directories selected, run the following from the repository root. Adjust the LLVM root to your installation.

```powershell
.\engine\build_backend.ps1 -ClangDir 'C:\Program Files\LLVM' `
    -MsvcDir $env:VCToolsInstallDir -RedistDir $env:VCToolsRedistDir -InstallDir .\backend
python tools/package.py
```

The language-specific extension ZIPs and shared source ZIP are written to `dist/`. Without `-InstallDir`, the backend installs to `work/clang-release/`. Once the source and dependencies have been fetched, `-Offline` reuses the local checkouts. [Build script](engine/build_backend.ps1) · [Cycles patch series](engine/patches)

On an RX 7800 XT, the following test generates a small animated scene with a camera-dependent world shader, renders three frames with both engines and compares the decoded RGBA pixels. Use a new output directory.

```powershell
python -m pip install numpy pillow
python engine/lookahead/check_stock_pipeline.py `
    'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
    .\backend\blender.exe .\parity-check --prepared
```

## License

The project is distributed under **GPL-3.0-or-later**. Upstream Blender and Cycles files retain their license notices. [License text](COPYING)
