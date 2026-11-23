# SPDX-License-Identifier: GPL-3.0-or-later
<#
.SYNOPSIS
Create a separate Cycles Frame Pipeline runtime from official Blender 5.2.1 for Windows x64.
.EXAMPLE
.\tools\install_backend.ps1 -PatchedExe .\download\blender.exe -Destination .\backend
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$PatchedExe,
    [string]$BlenderInstall = "$env:ProgramFiles\Blender Foundation\Blender 5.2",
    [Parameter(Mandatory = $true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$messagesFile = Join-Path $PSScriptRoot 'install-messages.psd1'
$launcher = Join-Path $PSScriptRoot 'open_blender.ps1'
$optixNotice = Join-Path $PSScriptRoot 'license\others\NVIDIA-OptiX.md'
if (!(Test-Path -LiteralPath $messagesFile -PathType Leaf)) {
    $messagesFile = Join-Path $PSScriptRoot 'windows_release\en.psd1'
    $launcher = Join-Path $PSScriptRoot 'windows_release\open_blender.ps1'
    $optixNotice = Join-Path (Split-Path -Parent $PSScriptRoot) 'engine\OptiX-NOTICE.md'
}
$messages = Import-PowerShellDataFile -LiteralPath $messagesFile
if (!(Test-Path -LiteralPath (Join-Path $BlenderInstall 'blender.exe') -PathType Leaf)) {
    throw ($messages.MissingRuntime -f $BlenderInstall)
}
if (!(Test-Path -LiteralPath $PatchedExe -PathType Leaf)) {
    throw ($messages.MissingBinary -f $PatchedExe)
}
$stock = (Resolve-Path -LiteralPath $BlenderInstall).ProviderPath.TrimEnd('\')
$binary = (Get-Item -LiteralPath $PatchedExe).FullName
$target = [IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Destination)).TrimEnd('\')
if ((Test-Path -LiteralPath $target) -or $target.StartsWith("$stock\", [StringComparison]::OrdinalIgnoreCase)) {
    throw ($messages.Destination -f $target)
}
$stockExe = Join-Path $stock 'blender.exe'
$stockVersion = & $stockExe --version
if ($LASTEXITCODE -ne 0 -or !($stockVersion -match '9e2066aef7ef')) {
    throw ($messages.Version -f $stock)
}
$kernels = Join-Path $stock '5.2\scripts\addons_core\cycles\lib'
if (!(Get-ChildItem -LiteralPath $kernels -File | Where-Object {
    $_.Name -like 'kernel_gfx*.fatbin.zst' -or $_.Name -like 'kernel_sm_*.cubin.zst' -or
    $_.Name -like 'kernel_compute_*.ptx.zst' -or $_.Name -eq 'kernel_optix.ptx.zst'
})) {
    throw ($messages.Kernels -f $kernels)
}
$parentDir = Split-Path -Parent $target
[IO.Directory]::CreateDirectory($parentDir) | Out-Null
$staging = Join-Path $parentDir ('.cycles-frame-pipeline-' + [guid]::NewGuid().ToString('N'))
New-Item -Path $staging -ItemType Directory | Out-Null
try {
    foreach ($dir in '5.2', 'blender.crt', 'blender.shared', 'license') {
        Copy-Item -LiteralPath (Join-Path $stock $dir) -Destination $staging -Recurse
    }
    Copy-Item -LiteralPath $optixNotice -Destination (Join-Path $staging 'license\others\NVIDIA-OptiX.md')
    foreach ($file in 'blender_cpu_check.dll', 'python3.dll', 'python313.dll', 'ucrtbase.dll', 'copyright.txt') {
        Copy-Item -LiteralPath (Join-Path $stock $file) -Destination $staging
    }
    $stagedExe = Join-Path $staging 'blender.exe'
    Copy-Item -LiteralPath $binary -Destination $stagedExe
    Copy-Item -LiteralPath $messagesFile -Destination (Join-Path $staging 'install-messages.psd1')
    Copy-Item -LiteralPath $launcher -Destination (Join-Path $staging 'open_blender.ps1')
    & $stagedExe -b --factory-startup --disable-autoexec --python-exit-code 1 --python-expr 'import _cycles; assert _cycles.with_exact_bvh and _cycles.with_native_frame_post and callable(_cycles.formal_begin)' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw $messages.Load }
    if ([IO.Path]::GetDirectoryName($staging) -ne $parentDir -or [IO.Path]::GetDirectoryName($target) -ne $parentDir) {
        throw $messages.Location
    }
    [IO.Directory]::Move($staging, $target)
} finally {
    if ((Test-Path -LiteralPath $staging) -and [IO.Path]::GetDirectoryName($staging) -eq $parentDir -and
        [IO.Path]::GetFileName($staging) -match '^\.cycles-frame-pipeline-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
Write-Output ($messages.Installed -f (Join-Path $target 'blender.exe'))
Write-Output ($messages.Launcher -f (Join-Path $target 'open_blender.ps1'))
