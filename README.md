# Cycles Frame Pipeline

English · [简体中文](README.zh-CN.md)

Cycles Frame Pipeline uses **Host BVH Prepacking** by default. On supported software BVH2 scenes, Blender evaluates frame **N+1** while the GPU samples frame **N**. Cycles validates the next frame’s geometry inputs, packs its BVH on the CPU and keeps the result in system memory. At handoff, the same Cycles session uploads the prepared data and starts sampling. A CPU worker processes the previous frame and writes its PNG.

The Windows engine includes AMD HIP, NVIDIA CUDA and NVIDIA OptiX. The published Host BVH Prepacking benchmark uses an RX 7800 XT with HIP. [GPU and Blender compatibility](#gpu-and-blender-compatibility) · [Ruins benchmark](benchmarks/README.md)

<a id="benchmark-results"></a><a id="benchmark-and-image-quality"></a>

**Ruins, Radeon RX 7800 XT.** From the first completed PNG (frame 624) to the tenth (frame 633), the next nine frames took 382.908 s in official Blender, 271.873 s with Host BVH Prepacking (**29.00% less time**) and 260.416 s with Eager GPU Upload (**31.99% less time**). Startup and the first frame are reported separately. [Timings, hardware, estimates and image comparisons](benchmarks/README.md)

[Install](#install) · [Render an animation](#render-an-animation) · [Build and test](#build-and-test)

## When to use it

- **Workload.** Use this mode for consecutive Cycles frames with a gap between GPU sampling windows. It is most effective when BVH work fits inside the preceding frame’s sampling time. Allow system memory for the next packed tree. The GPU holds one active scene, and the first frame pays for loading and initialization.
- **Scene and output.** Use a single enabled view layer, a single view, the Combined pass, PNG output and CPU Open Image Denoise enabled for final rendering on both scene and layer. A compositor using Combined image/alpha can be replayed when its dependencies are supported. Multiple views, active sequencer strips, animated compositor graphs, partial render borders and custom view curves are examples that require the serial path. Automatic mode can fall back to serial output. Use `--fallback error` to require the requested pipeline. [Scene compatibility checks](pipeline/composition.py)

## GPU and Blender compatibility

The engine overlay requires the official **Blender 5.2.1 LTS for Windows x64**, build `9e2066aef7ef`. The installer uses its runtime and GPU kernels. Other Blender versions (including other 5.2.x builds), Linux and macOS require a matching engine port and separate testing.

| Backend | Tested on hardware | Theoretical coverage on Windows x64 |
|---|---|---|
| AMD HIP | Radeon RX 7800 XT, software BVH2 | RDNA 1 and newer. Examples include Radeon RX 5000, 6000, 7000 and 9000. Blender lists Radeon Software 24.9.1 or Radeon PRO Software 24.Q4 as its Windows minimum. |
| NVIDIA CUDA | RTX 3090 rendering verified in v0.4.0. The software BVH2 path supports host prepacking in 0.5.0 by design. | Compute capability 5.0 or higher with a compatible Blender CUDA kernel and driver. |
| NVIDIA OptiX | RTX 3090 rendering verified in v0.4.0. OptiX builds its own acceleration structures. | Compute capability 5.0 or higher, NVIDIA driver 575 or newer. RTX GPUs can use their RT cores for ray tracing. |

The theoretical range follows the requirements for the pinned Blender 5.2 runtime. The Windows package includes single-GPU HIP, CUDA and OptiX. The published measurements apply to the AMD configuration below. [Blender 5.2 GPU requirements](https://docs.blender.org/manual/en/5.2/render/cycles/gpu_rendering.html) · [NVIDIA compute capability by model](https://developer.nvidia.com/cuda/gpus)

HIP and CUDA use native software BVH2 validation and packing when the scene qualifies. OptiX uses its native device build at handoff with the default upload policy. The optional eager upload policy prepares the next device scene in a second session and requires more VRAM.

## Install

1. Install [official Blender 5.2.1 LTS for Windows x64](https://download.blender.org/release/Blender5.2/). The overlay uses the runtime and device kernels from build `9e2066aef7ef`.
2. Download the [shared Windows engine](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles-frame-pipeline-windows-x64-0.5.1.zip) and the [English extension](https://github.com/UnitTurn/cycles-frame-pipeline/releases/download/v0.5.1/cycles_frame_pipeline-0.5.1-en.zip). Extract the engine into `.\downloads\engine`. From your working directory run:

   ```powershell
   .\downloads\engine\install_backend.ps1 -Language en -Destination .\backend
   .\backend\open_blender.ps1
   ```

   Choose a new destination. If Blender is outside its usual Program Files directory, also pass `-BlenderInstall 'C:\path\to\Blender 5.2'`. The installer reports HIP, CUDA and OptiX kernel files separately. The same engine ZIP accepts `-Language zh-CN` for a Chinese profile.
3. In the opened Blender window, choose **Edit → Preferences → Get Extensions → menu → Install from Disk** and enable the extension ZIP in the default user repository. The launcher keeps English settings under `%LOCALAPPDATA%\CyclesFramePipeline\5.2\en_US` and imports existing startup settings and default user extensions on first use. To submit from official Blender, install the extension there and set **Custom Blender Executable** to the new `backend\blender.exe`. Starting that executable directly uses your regular Blender profile.

## Render an animation

**Select your GPU.** In the Blender profile used for rendering, open **Edit → Preferences → System → Cycles Render Devices**, choose **HIP**, **CUDA** or **OptiX**, enable the target GPU only and save preferences. In the source scene set **Render Properties → Cycles → Device** to **GPU Compute**. Select **OpenImageDenoise** for final rendering and disable **Use GPU** for that denoise. Save the scene before submitting it from disk.

**Blender UI.** In **Render Properties → Cycles Frame Pipeline**, select the current scene or a saved `.blend`, choose **Use Scene Settings** and a PNG output directory, then click **Start Pipeline Render**. New configurations default to **Host BVH Prepacking**. Set the scene frame range to 1–1000 and step to 1 for the example. For large scenes, submit the saved file from an empty Blender window.

**Command line.** From the repository root, replace `.\scene.blend` with your scene. This example uses the scene's saved render settings and writes `0001.png` through `1000.png`. The background process reads the device preferences for the Blender profile it starts with.

```powershell
& .\backend\blender.exe -b '.\scene.blend' --python-exit-code 9 -P .\pipeline\render.py -- `
    --output '.\renders' --start 1 --end 1000 --step 1 `
    --post-threads 6
```

| Option | Use |
|---|---|
| `--host-bvh-prepacking` | Explicitly select the default native preparation mode. `--defer-upload` is an alias. |
| `--eager-upload` | Prepare and upload the next frame in a second Cycles session while the current frame is sampling. |
| `--profile scene` / `ruins-hip256` | Use saved scene settings for HIP, CUDA or OptiX. The optional Ruins preset explicitly selects the RX 7800 XT on HIP, up to 256 samples and a 0.01 adaptive threshold. |
| `--existing error` / `skip` / `replace` | Stop at an existing PNG (default), skip it, or overwrite it. |

Early packing requires a single background render tile. Per-batch pixel jitter, textures with on-demand tile loading, and geometry that needs GPU displacement use the corresponding native update at handoff. The log records `host_bvh_ready` when the packed data is ready in system memory and `bvh_pack_consumed` when the next frame consumes it. OptiX uses its backend-specific acceleration structures.


## Build and test

To build the backend from source, use Python 3.11+, Git with Git LFS, CMake, Ninja, LLVM **20.1.0** (`clang-cl`), x64 MSVC **14.44** headers/libraries/redistributables, Windows SDK **10.0.26100.0** and the matching official Blender installation. The script fetches the pinned Blender source and Windows dependencies, applies the patch series and copies the matching official HIP, CUDA and OptiX kernels into the build. For the OptiX host backend it fetches the pinned NVIDIA OptiX 8.0.0 headers. To use an existing SDK, pass `-OptixDir <SDK root>`. In a Visual Studio Developer PowerShell with those MSVC tool and redist directories selected, run the following from the repository root. Adjust the LLVM root to your installation.

```powershell
.\engine\build_backend.ps1 -ClangDir 'C:\Program Files\LLVM' `
    -MsvcDir $env:VCToolsInstallDir -RedistDir $env:VCToolsRedistDir -InstallDir .\backend
python tools/package.py
```

The language-specific extension ZIPs and shared source ZIP are written to `dist/`. Without `-InstallDir`, the backend installs to `work/clang-release/`. Once the source and dependencies have been fetched, `-Offline` reuses the local checkouts. [Build script](engine/build_backend.ps1) · [Cycles patch series](engine/patches)

Pull requests package both extensions and exercise their panels in official Blender. For a local GPU check, compare the supplied animated scene on HIP, CUDA or OptiX. The fixture and both test commands are documented in [Frame handoff tests](engine/lookahead/README.md). Results on the release engine include timings and decoded PNG differences. [Public fixture results](benchmarks/README.md#public-fixture)

## License

The project is licensed under [GPL-3.0-or-later](COPYING). Cycles files and test code marked `SPDX-License-Identifier: Apache-2.0` carry the [Apache 2.0 license](LICENSES/Apache-2.0.txt). Upstream notices accompany their files. [OptiX notices](engine/OptiX-NOTICE.md)
