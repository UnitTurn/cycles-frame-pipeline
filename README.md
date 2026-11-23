# Cycles Frame Pipeline

English · [简体中文](README.zh-CN.md)

Render consecutive Blender animation frames on one GPU. While Cycles samples frame **N**, Blender evaluates frame **N+1** and a second Cycles session validates its BVH, packs the scene and uploads it to the GPU. At the frame boundary that same session starts sampling. A CPU worker denoises and writes finished frames as numbered PNGs.

**1,000-frame estimate on a Radeon RX 7800 XT.** If a 1080p animation sustains the throughput measured on Ruins frames 624–633, the pipeline would save about **3 h 29 min 26 s**. Both percentages use the time from launch to final PNG and the same denominator, official Blender’s wall time. The calculation is `(official time − pipeline time) / official time`.

| Sequence | Official Blender | Cycles Frame Pipeline | Time reduction |
|---|---:|---:|---:|
| 10 frames · measured | 560.25 s | 466.03 s | **16.82%** |
| 1,000 frames · projected | 11 h 29 min 41 s | 8 h 00 min 15 s | **30.37%** |

![Measured time reduction across ten frames and projected time reduction across 1,000 frames on the RX 7800 XT](benchmarks/projection-en.png)

The estimate counts startup once and uses the mean of the nine measured intervals for the remaining frames. The formula is `first PNG + 999 × ((tenth PNG − first PNG) / 9)`. Times are seconds from launch. The input pairs were 189.144 and 560.246 for official Blender, and 208.306 and 466.027 for Cycles Frame Pipeline. Shots with different geometry or sampling costs will have different frame intervals.

[Install](#install) · [Render an animation](#render-an-animation) · [Benchmark and image quality](#benchmark-and-image-quality) · [Build and test](#build-and-test)

## When to use it

- **Workload.** Consecutive Cycles frames with a measurable gap between one frame's last samples and the next frame's first samples. Geometry, camera, motion blur and material inputs advance in animation order. Two resident device scenes cost extra VRAM and system memory. The first frame still pays for scene loading and setup.
- **Tested hardware and software.** Windows x64, Blender **5.2.1 LTS** at `9e2066aef7ef`, AMD Radeon **RX 7800 XT** with standard HIP and software BVH2. The supplied build has HIP RT disabled. Results below cover this configuration.
- **Scene and output.** Use a single enabled view layer, a single view, the Combined pass, PNG output and CPU Open Image Denoise enabled for final rendering on both scene and layer. A compositor using Combined image/alpha can be replayed when its dependencies are supported. Multiple views, active sequencer strips, animated compositor graphs, partial render borders and custom view curves are examples that require the serial path. Prepared mode reports an unsupported setting at submission. [Scene compatibility checks](pipeline/composition.py)

## Install

1. Install the official **Blender 5.2.1 LTS Windows x64** build. The installer checks the build hash because the patched executable uses the matching Blender runtime and HIP kernels.
2. For the English interface, download `cycles-frame-pipeline-windows-x64-0.3.1-en.zip` (Windows engine overlay and English installer) and `cycles_frame_pipeline-0.3.1-en.zip` (extension) from the [latest release](https://github.com/expitau-one/cycles-frame-pipeline/releases/latest). The Chinese distribution has the same extension ID and engine. Install one language edition. Extract the engine overlay to `.\downloads\engine` for the paths below. From your working directory, run the included English installer in PowerShell. Adjust the official installation path and choose a new destination directory for the side-by-side runtime.

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

4. **In that window**, open **Edit → Preferences → Get Extensions → menu → Install from Disk**, select `cycles_frame_pipeline-0.3.1-en.zip` and choose the default user repository. Enable **Cycles Frame Pipeline**. Use the same launcher next time. It keeps this edition's preferences and default extensions under `%LOCALAPPDATA%\CyclesFramePipeline\5.2\en_US`. On first launch, it imports the existing startup settings and default user extensions.

**Using your regular Blender profile.** Starting `backend\blender.exe` directly follows your normal Blender language and preferences. To submit from an official Blender installation, install the English extension in that window and set **Custom Blender Executable** to the patched `backend\blender.exe`. The CLI workflow below uses the repository scripts and the backend.


## Render an animation

**Blender UI.** In **Render Properties → Cycles Frame Pipeline**, select the current scene or a saved `.blend`, set a PNG output directory and choose **Native Cycles Denoising and Output**. Enable **Optimize Native BVH (Custom Engine)**, select **Prepare Next Frame in Parallel**, then click **Start Pipeline Render**. For the 1,000-frame example, set the scene’s frame range to 1–1000 with a step of 1. Progress counts completed PNGs. For a large scene, an empty Blender window can submit a `.blend` from disk.

**Command line.** From the repository root, replace `.\scene.blend` with your scene. This example uses the scene's saved render settings and writes `0001.png` through `1000.png`. Select the HIP render device in Blender for GPU rendering.

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 1000 --step 1 `
    --profile scene --mode native --bvh-input prepared --post-threads 6
```

| Option | Use |
|---|---|
| `--bvh-input prepared` | Opt in to two sessions. One samples while the other prepares the next production frame. Requires `--mode native`. |
| `--profile scene` / `ruins-hip256` | Use saved settings, or select the RX 7800 XT benchmark preset with standard HIP, up to 256 samples and a 0.01 adaptive threshold. |
| `--existing error` / `skip` / `replace` | Stop at an existing PNG (default), skip it, or overwrite it. |

## Benchmark and image quality

**Ruins**, frames 624–633 in order, 1920×1080, RX 7800 XT, standard HIP, persistent data, up to 256 adaptive samples, threshold 0.01 and six CPU OIDN threads. Official Blender and the pipeline each rendered these ten frames once.

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

The production scene is private. The repository includes the measurements, a script to regenerate the charts and a procedural scene for testing image parity. The English and Simplified Chinese packages ship the same Windows rendering executable. The release engine adds two configuration checks before reusing the environment sampling distribution compared with the ten-frame timing build. The benchmark configuration was constant. [Benchmark data, time series and methodology](benchmarks/README.md)

## Build and test

To build the backend from source, use Python 3.11+, Git with Git LFS, CMake, Ninja, LLVM **20.1.0** (`clang-cl`), x64 MSVC **14.44** headers/libraries/redistributables, Windows SDK **10.0.26100.0** and the matching official Blender installation. The script fetches the pinned Blender source and Windows dependencies, applies the patch series and copies the matching official HIP kernels into the build. In a Visual Studio Developer PowerShell with those MSVC tool and redist directories selected, run the following from the repository root. Adjust the LLVM root to your installation.

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
