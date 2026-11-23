# SPDX-License-Identifier: GPL-3.0-or-later
# Store this language's preferences and default extension repositories together.
param([string[]]$BlenderArgs = @())
$ErrorActionPreference = 'Stop'
$messages = Import-PowerShellDataFile -LiteralPath (Join-Path $PSScriptRoot 'install-messages.psd1')
$exe = Join-Path $PSScriptRoot 'blender.exe'
$locale = $messages.Locale
$profiles = Join-Path $env:LOCALAPPDATA 'CyclesFramePipeline\5.2'
$profileDir = Join-Path $profiles $locale
if (!(Test-Path -LiteralPath $profileDir -PathType Container)) {
    $query = "import bpy,json; print('CFP_DIRS='+json.dumps([bpy.utils.user_resource('CONFIG'), bpy.utils.user_resource('EXTENSIONS')]))"
    $info = & $exe -b --factory-startup --disable-autoexec --python-exit-code 1 --python-expr $query
    $entry = @($info | Where-Object { $_ -like 'CFP_DIRS=*' })
    if ($LASTEXITCODE -ne 0 -or $entry.Count -ne 1) { throw $messages.Config }
    $original = ConvertFrom-Json -InputObject $entry[0].Substring(9)
    [IO.Directory]::CreateDirectory($profiles) | Out-Null
    $stage = Join-Path $profiles ('.initialize-' + [guid]::NewGuid().ToString('N'))
    $config = Join-Path $stage 'config'
    $extensions = Join-Path $stage 'extensions'
    [IO.Directory]::CreateDirectory($config) | Out-Null
    [IO.Directory]::CreateDirectory($extensions) | Out-Null
    try {
        if ($original[0] -and (Test-Path -LiteralPath $original[0] -PathType Container)) {
            foreach ($name in 'userpref.blend', 'startup.blend') {
                $file = Join-Path $original[0] $name
                if (Test-Path -LiteralPath $file -PathType Leaf) {
                    Copy-Item -LiteralPath $file -Destination $config
                }
            }
        }
        if ($original[1] -and (Test-Path -LiteralPath $original[1] -PathType Container)) {
            & robocopy.exe $original[1] $extensions /E /XJ /R:1 /W:0 /NFL /NDL /NJH /NJS /NP | Out-Null
            if ($LASTEXITCODE -ge 8) { throw $messages.Extensions }
        }
        try {
            [IO.Directory]::Move($stage, $profileDir)
        } catch [IO.IOException] {
            if (!(Test-Path -LiteralPath $profileDir -PathType Container)) { throw }
        }
    } finally {
        if ((Test-Path -LiteralPath $stage) -and [IO.Path]::GetDirectoryName($stage) -eq $profiles -and
            [IO.Path]::GetFileName($stage) -match '^\.initialize-[0-9a-f]{32}$') {
            Remove-Item -LiteralPath $stage -Recurse -Force
        }
    }
}
$savedConfig = $env:BLENDER_USER_CONFIG
$savedExtensions = $env:BLENDER_USER_EXTENSIONS
try {
    $env:BLENDER_USER_CONFIG = Join-Path $profileDir 'config'
    $env:BLENDER_USER_EXTENSIONS = Join-Path $profileDir 'extensions'
    $language = "import bpy; v=bpy.context.preferences.view; v.language='$locale'; v.use_translate_interface=True; v.use_translate_tooltips=True"
    & $exe --python-expr $language @BlenderArgs | Out-Host
    $exitCode = $LASTEXITCODE
} finally {
    $env:BLENDER_USER_CONFIG = $savedConfig
    $env:BLENDER_USER_EXTENSIONS = $savedExtensions
}
exit $exitCode
