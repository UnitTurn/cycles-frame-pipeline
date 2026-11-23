<#
.SYNOPSIS
Build the patched Blender 5.2.1 Windows x64 release with clang-cl 20.1.0.
.DESCRIPTION
Requires CMake, Ninja, the Windows 10.0.26100.0 SDK, MSVC 14.44 x64 headers,
libraries and redistributables, and the matching official Blender GPU kernels.
The script fetches the pinned OptiX 8.0.0 headers, or uses -OptixDir / OPTIX_ROOT_DIR.
An existing work/official-toolchain layout is supported. Otherwise use clang-cl on PATH
and VCToolsInstallDir/VCToolsRedistDir from an x64 Visual Studio Developer shell.
Set -ClangDir, -MsvcDir, -RedistDir or -SdkDir for equivalent installations.
The default build tree is work/build-clang and the install is work/clang-release.
.EXAMPLE
.\engine\build_backend.ps1 -Offline -Jobs 4
.EXAMPLE
.\engine\build_backend.ps1 -BuildDir C:\build\blender-clang -InstallDir C:\build\blender-bin
#>
param(
    [int]$Jobs = 6,
    [string]$BlenderInstall = "C:\Program Files\Blender Foundation\Blender 5.2",
    [string]$CMake,
    [string]$Ninja,
    [string]$GitProxy,
    [switch]$Offline,
    [switch]$Fresh,
    [string]$AsciiProjectRoot,
    [string]$ClangDir,
    [string]$MsvcDir,
    [string]$RedistDir,
    [string]$OptixDir = $env:OPTIX_ROOT_DIR,
    [string]$SdkDir = "${env:ProgramFiles(x86)}\Windows Kits\10",
    [string]$SdkVersion = '10.0.26100.0',
    [string]$BuildDir,
    [string]$InstallDir
)
$ErrorActionPreference = 'Stop'
if ($Jobs -lt 1) { throw 'Jobs must be positive.' }
$project = Split-Path -Parent $PSScriptRoot
$physicalProject = $project
if ($project -match '[^\x00-\x7F]') {
    # Some Windows tools still write response files with the active ANSI code page.
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($project)))).Replace('-','').Substring(0,12) }
    finally { $hash.Dispose() }
    $project = if ($AsciiProjectRoot) { $AsciiProjectRoot } else {
        # Keep the prefix short enough for generated GLSL object names as well.
        Join-Path ([IO.Path]::GetPathRoot($physicalProject)) "cfp-$key"
    }
    if (!(Test-Path -LiteralPath $project)) {
        New-Item -ItemType Junction -Path $project -Target $physicalProject | Out-Null
    } elseif ((Get-Item -LiteralPath $project).Target -ne $physicalProject) {
        throw "The ASCII project alias is occupied: $project"
    }
}
$work = Join-Path $project 'work'
$source = Join-Path $work 'blender'
$libs = Join-Path $work 'windows_lib'
function Get-ProjectPath($value, $default) {
    if (!$value) { return $default }
    $full = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($value)
    if ($full.StartsWith($physicalProject + '\', [StringComparison]::OrdinalIgnoreCase)) {
        return $project + $full.Substring($physicalProject.Length)
    }
    return $full
}
$build = Get-ProjectPath $BuildDir (Join-Path $work 'build-clang')
$install = Get-ProjectPath $InstallDir (Join-Path $work 'clang-release')
$upstream = '9e2066aef7ef7e20c142ad7bd3303138a4304c93'
$libCommit = '60d6e96b917568278d400a4024c98da0fb777338'
$optixCommit = 'f60c1e44f18426f426a2ed948f28515b3cf67b8a'
$baseURL = 'https://projects.blender.org/blender'
$gitOpts = @()
if ($PSBoundParameters.ContainsKey('GitProxy')) { $gitOpts = @('-c', "http.proxy=$GitProxy") }

function Invoke-Checked($program, [array]$arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program exited with status $LASTEXITCODE" }
}
function Use-Tool($specified, $bundled, $command) {
    if ($specified) { return (Resolve-Path -LiteralPath $specified).Path }
    if (Test-Path -LiteralPath $bundled) { return $bundled }
    return (Get-Command $command -ErrorAction Stop).Source
}
function Invoke-GitWithoutSmudge([array]$arguments) {
    $previous = $env:GIT_LFS_SKIP_SMUDGE
    try {
        $env:GIT_LFS_SKIP_SMUDGE = '1'
        Invoke-Checked git $arguments
    } finally {
        $env:GIT_LFS_SKIP_SMUDGE = $previous
    }
}

New-Item -Force -ItemType Directory $work | Out-Null
$cm = Use-Tool $CMake (Join-Path $work 'pytools/cmake/data/bin/cmake.exe') 'cmake'
$nj = Use-Tool $Ninja (Join-Path $work 'pytools/bin/ninja.exe') 'ninja'
$stockExe = Join-Path $BlenderInstall 'blender.exe'
if (!(Test-Path -LiteralPath $stockExe)) { throw "Blender 5.2.1 is required for matching precompiled GPU kernels: $stockExe" }
$version = & $stockExe --version
if (!($version -match $upstream.Substring(0,12))) { throw 'The installed GPU kernels must match Blender 5.2.1 (9e2066aef7ef).' }

$tools = Join-Path $work 'official-toolchain'
$localClang = Join-Path $tools 'llvm20'
$localMsvc = Join-Path $tools 'vs/VC/Tools/MSVC/14.44.35207'
$localRedist = Join-Path $tools 'vs/VC/Redist/MSVC/14.44.35112'
if (!$ClangDir -and !(Test-Path -LiteralPath $localClang)) {
    $installedClang = Get-Command clang-cl.exe -ErrorAction SilentlyContinue
    $ClangDir = if ($installedClang) { Split-Path -Parent (Split-Path -Parent $installedClang.Source) }
                else { Join-Path $env:ProgramFiles 'LLVM' }
}
if (!$MsvcDir -and !(Test-Path -LiteralPath $localMsvc)) { $MsvcDir = $env:VCToolsInstallDir }
if (!$RedistDir -and !(Test-Path -LiteralPath $localRedist)) { $RedistDir = $env:VCToolsRedistDir }
$ClangDir = Get-ProjectPath $ClangDir $localClang
$MsvcDir = Get-ProjectPath $MsvcDir $localMsvc
$RedistDir = Get-ProjectPath $RedistDir $localRedist
$clang = Join-Path $ClangDir 'bin/clang-cl.exe'
$vcBin = Join-Path $MsvcDir 'bin/Hostx64/x64'
$sdkBin = Join-Path $SdkDir "bin/$SdkVersion/x64"
$sdkInclude = Join-Path $SdkDir "Include/$SdkVersion"
$sdkLib = Join-Path $SdkDir "Lib/$SdkVersion"
foreach ($required in @($clang,"$vcBin/link.exe","$vcBin/lib.exe","$sdkBin/rc.exe","$RedistDir/x64")) {
    if (!(Test-Path -LiteralPath $required)) { throw "Missing Windows build tool or runtime: $required" }
}
if (!((& $clang --version) -match '^clang version 20\.1\.0(?: |$)')) {
    throw "This release uses LLVM 20.1.0. Specify its root with -ClangDir."
}
Get-Command python, git -ErrorAction Stop | Out-Null
if (!$Offline) { Invoke-Checked git @('lfs','version') }

if ($OptixDir) {
    $optix = Get-ProjectPath $OptixDir $null
} else {
    $optix = Join-Path $work 'optix-dev'
    if (!(Test-Path -LiteralPath (Join-Path $optix '.git'))) {
        if ($Offline) { throw "Provide OptiX 8.0.0 headers with -OptixDir or fetch them before using -Offline." }
        Invoke-Checked git ($gitOpts + @('clone','--depth','1','--branch','v8.0.0','https://github.com/NVIDIA/optix-dev.git',$optix))
    }
    if ((git -C $optix rev-parse HEAD) -ne $optixCommit) { throw "Unexpected OptiX headers revision at $optix" }
}
$optixInclude = Join-Path $optix 'include'
if (!(Select-String -LiteralPath (Join-Path $optixInclude 'optix.h') -Pattern '^#define OPTIX_VERSION\s+80000\s*$' -Quiet) -or
    !(Select-String -LiteralPath (Join-Path $optixInclude 'optix_function_table.h') -Pattern '^#define OPTIX_ABI_VERSION\s+87\s*$' -Quiet)) {
    throw 'This build uses the OptiX 8.0.0 headers (ABI 87).'
}

if (!(Test-Path -LiteralPath (Join-Path $source '.git'))) {
    if ($Offline) { throw "Missing source checkout for offline build: $source" }
    Invoke-GitWithoutSmudge ($gitOpts + @('clone','--depth','1','--branch','v5.2.1',"$baseURL/blender.git",$source))
}
if ((git -C $source rev-parse HEAD) -ne $upstream) { throw "Unexpected source revision at $source" }
if (!(Test-Path -LiteralPath (Join-Path $libs '.git'))) {
    if ($Offline) { throw "Missing Windows dependencies for offline build: $libs" }
    New-Item -Force -ItemType Directory $libs | Out-Null
    Invoke-Checked git @('-C',$libs,'init')
    Invoke-Checked git @('-C',$libs,'remote','add','origin',"$baseURL/lib-windows_x64.git")
    Invoke-Checked git ($gitOpts + @('-C',$libs,'fetch','--depth','1','origin',$libCommit))
    Invoke-GitWithoutSmudge @('-C',$libs,'checkout','--detach','FETCH_HEAD')
}
if ((git -C $libs rev-parse HEAD) -ne $libCommit) { throw "Unexpected Windows library revision at $libs" }
if (!$Offline) {
    Invoke-Checked git ($gitOpts + @('-C',$source,'-c',"lfs.url=$baseURL/blender.git/info/lfs",'lfs','pull','--include=release/**,source/**,intern/**'))
    Invoke-Checked git ($gitOpts + @('-C',$libs,'lfs','pull','--exclude=*.pdb,*.pdb.gz'))
}
Invoke-Checked python @((Join-Path $PSScriptRoot 'apply_patches.py'),$source)

$env:PATH = "$ClangDir\bin;$vcBin;$sdkBin;$env:PATH"
$env:INCLUDE = "$MsvcDir\include;$sdkInclude\ucrt;$sdkInclude\shared;$sdkInclude\um;$sdkInclude\winrt;$sdkInclude\cppwinrt"
$env:LIB = "$MsvcDir\lib\x64;$sdkLib\ucrt\x64;$sdkLib\um\x64"
$env:VCToolsInstallDir = "$MsvcDir\"
$env:VCToolsRedistDir = "$RedistDir\"
$env:VSCMD_ARG_TGT_ARCH = 'x64'
$env:WindowsSdkDir = "$SdkDir\"
$env:WindowsSDKVersion = "$SdkVersion\"
$cmakeLibs = $libs.Replace('\','/')
$releasePreset = Join-Path $source 'build_files/cmake/config/blender_release.cmake'
$heavyJobs = [Math]::Max(1, [Math]::Min(4, [Math]::Floor($Jobs / 2)))
$options = @('-S',$source,'-B',$build,'-G','Ninja','-C',$releasePreset,"-DCMAKE_MAKE_PROGRAM=$nj",
    "-DCMAKE_C_COMPILER:FILEPATH=$clang","-DCMAKE_CXX_COMPILER:FILEPATH=$clang",
    "-DCMAKE_AR:FILEPATH=$vcBin/lib.exe","-DCMAKE_LINKER:FILEPATH=$vcBin/link.exe",
    '-DCMAKE_BUILD_TYPE=Release',"-DLIBDIR:PATH=$cmakeLibs","-DCMAKE_INSTALL_PREFIX=$install",
    "-DNINJA_MAX_NUM_PARALLEL_COMPILE_HEAVY_JOBS=$heavyJobs",'-DNINJA_MAX_NUM_PARALLEL_LINK_JOBS=1',
    '-DWITH_GTESTS=OFF','-DWITH_CYCLES_DEVICE_HIP=ON','-DWITH_CYCLES_DEVICE_HIPRT=OFF',
    '-DWITH_CYCLES_HIP_BINARIES=OFF','-DWITH_CYCLES_DEVICE_CUDA=ON','-DWITH_CYCLES_DEVICE_OPTIX=ON',
    '-DWITH_CUDA_DYNLOAD=ON',"-DOPTIX_ROOT_DIR:PATH=$optix","-DOPTIX_INCLUDE_DIR:PATH=$optixInclude",
    '-DWITH_CYCLES_CUDA_BINARIES=OFF','-DWITH_CYCLES_ONEAPI_BINARIES=OFF','-DWITH_CYCLES_DEVICE_ONEAPI=OFF',
    '-DWITH_PYTHON_INSTALL=ON')
if ($physicalProject -match '[^\x00-\x7F]') {
    # Blender's generator resolves junctions when naming some generated objects.
    # MSVC otherwise reads their UTF-8 names in Ninja response files as ANSI.
    $options += "-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES:FILEPATH=$(Join-Path $project 'engine/windows_link.cmake')"
    $options += "-DCFP_PYTHON:FILEPATH=$((Get-Command python).Source)"
}
if ($Fresh) { $options += '--fresh' }
Invoke-Checked $cm $options
Invoke-Checked $cm @('--build',$build,'--target','install','--parallel',$Jobs)

$kernelDir = '5.2/scripts/addons_core/cycles/lib'
$targetDir = Join-Path $install $kernelDir
New-Item -Force -ItemType Directory $targetDir | Out-Null
foreach ($pattern in 'kernel_gfx*.fatbin.zst','kernel_sm_*.cubin.zst','kernel_compute_*.ptx.zst','kernel_optix*.ptx.zst') {
    $kernels = @(Get-ChildItem -LiteralPath (Join-Path $BlenderInstall $kernelDir) -Filter $pattern -File)
    if (!$kernels) { throw "Missing official Blender 5.2.1 kernels matching $pattern in $BlenderInstall." }
    foreach ($kernel in $kernels) { Copy-Item -LiteralPath $kernel.FullName -Destination $targetDir -Force }
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'OptiX-NOTICE.md') -Destination (Join-Path $install 'license/others/NVIDIA-OptiX.md')
Invoke-Checked (Join-Path $install 'blender.exe') @('-b','--factory-startup','--python-exit-code','1',
    '--python-expr','import _cycles; assert _cycles.with_exact_bvh and _cycles.with_native_frame_post and callable(_cycles.formal_begin)')
Write-Output "Backend ready: $install\blender.exe"
