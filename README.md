# Cycles Frame Pipeline

English · [简体中文](README.zh-CN.md)

Render consecutive Blender animation frames on one GPU. While Cycles samples frame **N**, Blender evaluates frame **N+1** and a second Cycles session validates its BVH, packs the scene and uploads it to the GPU. At the frame boundary that same session starts sampling. A CPU worker denoises and writes finished frames as numbered PNGs.

On a ten-frame 1080p animation, the pipeline cut time to the final PNG from **560.25 s to 466.03 s** on a Radeon RX 7800 XT. Average GPU utilization after the first PNG rose from **69.91% to 94.85%**. Peak dedicated GPU memory rose from **8.62 GiB to 12.29 GiB**.

![Ten-frame render time, GPU utilization and peak memory for stock Blender, previous-frame BVH reuse and prepared frames](benchmarks/overview-en.png)

[Install](#install) · [Render an animation](#render-an-animation) · [Benchmark and image quality](#benchmark-and-image-quality) · [Build and test](#build-and-test)

## When to use it

- **Workload.** Consecutive Cycles frames with a measurable gap between one frame's last samples and the next frame's first samples. Geometry, camera, motion blur and material inputs advance in animation order. Two resident device scenes cost extra VRAM and system memory. The first frame still pays for scene loading and setup.
- **Tested hardware and software.** Windows x64, Blender **5.2.1 LTS** at `9e2066aef7ef`, AMD Radeon **RX 7800 XT** with standard HIP and software BVH2. The supplied build has HIP RT disabled. Results below cover this configuration.
- **Scene and output.** Use a single enabled view layer, a single view, the Combined pass, PNG output and CPU Open Image Denoise enabled for final rendering on both scene and layer. A compositor using Combined image/alpha can be replayed when its dependencies are supported. Multiple views, active sequencer strips, animated compositor graphs, partial render borders and custom view curves are examples that require the serial path. Prepared mode reports an unsupported setting at submission. [Scene compatibility checks](pipeline/composition.py)

## Install

1. Install the official **Blender 5.2.1 LTS Windows x64** build. The installer checks the build hash because the patched executable uses the matching Blender runtime and HIP kernels.
2. Download the Windows engine overlay and `cycles_frame_pipeline-0.3.0.zip` from the [latest release](https://github.com/expitau-one/cycles-frame-pipeline/releases/latest). Extract the engine overlay. From the source checkout, run the following in PowerShell, substituting the path to the extracted executable and your official installation. Choose a new destination directory for the side-by-side runtime. The overlay also includes the installation script.

   ```powershell
   .\tools\install_backend.ps1 `
       -PatchedExe '.\downloads\engine\blender.exe' `
       -BlenderInstall 'C:\Program Files\Blender Foundation\Blender 5.2' `
       -Destination '.\backend'
   ```

3. In Blender, open **Edit → Preferences → Get Extensions → menu → Install from Disk**, select the extension ZIP and enable **Cycles 帧间流水线**. If submitting from official Blender, set **定制 Blender 程序** (custom Blender executable) to the new `backend\blender.exe`. Running the patched Blender directly also works. The command-line workflow below requires the repository scripts and the backend.

## Render an animation

**Blender UI.** In **Render Properties → Cycles 帧间流水线**, select the current scene or a saved `.blend`, set a PNG output directory and choose **Cycles 原生降噪与输出** (native denoising and output). Enable **优化原版 BVH（配套引擎）**, select **并行准备下一正式帧** (prepare the next frame), then click **启动流水线渲染**. Progress counts completed PNGs. For a large scene, an empty Blender window can submit a `.blend` from disk.

**Command line.** From the repository root, replace `.\scene.blend` with your scene. This example uses the scene's saved render settings and writes `0001.png` through `0010.png`. Select the HIP render device in Blender for GPU rendering.

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 10 --step 1 `
    --profile scene --mode native --bvh-input prepared --post-threads 6
```

| Option | Use |
|---|---|
| `--bvh-input prepared` | Opt in to two sessions. One samples while the other prepares the next production frame. Requires `--mode native`. |
| `--bvh-input previous` | Use one render session and reuse verified BVH subtrees from the previous frame. This is the lower-VRAM comparison below. |
| `--bvh-input next` | Evaluate a separate candidate for the next frame and build its BVH ahead of time. The production frame validates it before use. |
| `--bvh-input off` | Turn off BVH optimization. Pair with `--mode serial` for an inline reference render. |
| `--profile scene` / `ruins-hip256` | Use saved settings, or select the RX 7800 XT benchmark preset with standard HIP, up to 256 samples and a 0.01 adaptive threshold. |
| `--existing error` / `skip` / `replace` | Stop at an existing PNG (default), skip it, or overwrite it. |

## Benchmark and image quality

**Ruins**, frames 624–633 in order, 1920×1080, RX 7800 XT, standard HIP, persistent data, up to 256 adaptive samples, threshold 0.01 and six CPU OIDN threads. Each configuration ran once. The previous pipeline combines previous-frame BVH reuse with asynchronous native output.

| Metric | Stock Blender | Previous pipeline | Prepared frames |
|---|---:|---:|---:|
| Launch to first PNG | 189.14 s | 198.80 s | 208.31 s |
| Launch to final PNG | 560.25 s | 516.92 s | **466.03 s** |
| Mean interval between subsequent PNGs | 41.23 s | 35.35 s | **28.64 s** |
| Mean GPU utilization after first PNG | 69.91% | 80.80% | **94.85%** |
| Time below 10% GPU utilization after first PNG | 81.82 s | 22.00 s | **3.00 s** |
| Peak dedicated GPU memory | 8.62 GiB | 7.95 GiB | **12.29 GiB** |
| Peak system committed memory | 73.10 GiB | 72.38 GiB | **85.21 GiB** |

Prepared frames saved **94.22 s (16.82%)** over stock Blender and **50.90 s (9.85%)** over the previous pipeline from launch to the final PNG. All nine subsequent frames were ready before the previous frame's last sampling batch ended. The median gap between successive sampling windows was **0.139 s**, versus **6.283 s** in the previous pipeline's same-order instrumented run. GPU activity is whole-card utilization sampled at about 1 Hz. System commit includes memory backed by RAM or the Windows page file. Peak physical memory was 31.95 GiB in all three runs.

**Image comparison.** Across ten decoded PNG pairs, 5,343 of 20,736,000 pixels differed from stock Blender by one 8-bit RGB level. All other RGB values and all alpha values matched. The two sessions inherit the same cached environment-light sampling distribution and update it when the world changes. A separate four-frame test of the release executable changed world intensity in frame 3. All four RGBA outputs matched stock pixel for pixel.

The production scene is private. The repository includes the measurements, a script to regenerate the charts and a procedural scene for testing image parity. The release executable adds two configuration checks before inheriting the environment sampling distribution. The benchmark configuration was constant. [Benchmark data, time series and methodology](benchmarks/README.md)

## Build and test

To build the backend from source, use Python 3.11+, Git with Git LFS, CMake, Ninja, LLVM **20.1.0** (`clang-cl`), x64 MSVC **14.44** headers/libraries/redistributables, Windows SDK **10.0.26100.0** and the matching official Blender installation. The script fetches the pinned Blender source and Windows dependencies, applies the patch series and copies the matching official HIP kernels into the build. In a Visual Studio Developer PowerShell with those MSVC tool and redist directories selected, run the following from the repository root. Adjust the LLVM root to your installation.

```powershell
.\engine\build_backend.ps1 -ClangDir 'C:\Program Files\LLVM' `
    -MsvcDir $env:VCToolsInstallDir -RedistDir $env:VCToolsRedistDir -InstallDir .\backend
python tools/package.py
```

The extension ZIP is written to `dist/`. Without `-InstallDir`, the backend installs to `work/clang-release/`. Once the source and dependencies have been fetched, `-Offline` reuses the local checkouts. [Build script](engine/build_backend.ps1) · [Cycles patch series](engine/patches)

On an RX 7800 XT, the following test generates a small animated scene with a camera-dependent world shader, renders three frames with both engines and compares the decoded RGBA pixels. Use a new output directory.

```powershell
python -m pip install numpy pillow
python engine/lookahead/check_stock_pipeline.py `
    'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
    .\backend\blender.exe .\parity-check --prepared
```

## License

The project is distributed under **GPL-3.0-or-later**. Upstream Blender and Cycles files retain their license notices. [License text](COPYING)
