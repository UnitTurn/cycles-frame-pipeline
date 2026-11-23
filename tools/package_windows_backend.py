# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the Windows executable, installer, source references and license notices."""
import argparse
from pathlib import Path, PureWindowsPath
import struct
import subprocess
import tempfile
import tomllib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
BLENDER_REVISION = "9e2066aef7ef7e20c142ad7bd3303138a4304c93"
REPOSITORY = "https://github.com/expitau-one/cycles-frame-pipeline"


def release_executable(path):
    image = bytearray(path.read_bytes())
    coff = struct.unpack_from("<I", image, 0x3C)[0]
    opt = coff + 24
    if (image[:2] != b"MZ" or image[coff:coff+4] != b"PE\0\0" or
            struct.unpack_from("<H", image, coff+4)[0] != 0x8664 or
            struct.unpack_from("<H", image, opt)[0] != 0x20B):
        raise ValueError("Expected a Windows x64 PE32+ executable")
    if b"formal_begin\0" not in image or b"with_native_frame_post\0" not in image:
        raise ValueError("Missing the prepared-frame Cycles extension")
    directories = opt + 112
    if (struct.unpack_from("<I", image, opt+64)[0] or
            struct.unpack_from("<II", image, directories+32) != (0, 0)):
        raise ValueError("Package an unsigned release build with the default zero PE checksum")
    debug_rva, debug_size = struct.unpack_from("<II", image, directories+48)
    if debug_size == 0:
        return image
    sections = struct.unpack_from("<H", image, coff+6)[0]
    optional_size = struct.unpack_from("<H", image, coff+20)[0]
    for index in range(sections):
        header = opt + optional_size + index*40
        rva, size, file_start = struct.unpack_from("<III", image, header+12)
        if rva <= debug_rva and debug_rva+debug_size <= rva+size:
            debug = file_start + debug_rva-rva
            break
    else:
        raise ValueError("PE debug directory falls outside the sections")
    if debug_size % 28 or debug+debug_size > len(image):
        raise ValueError("Invalid PE debug directory bounds")
    for entry in range(debug, debug+debug_size, 28):
        kind, length, _, offset = struct.unpack_from("<IIII", image, entry+12)
        if kind != 2:
            continue
        if length < 25 or offset+length > len(image) or image[offset:offset+4] != b"RSDS":
            raise ValueError("Unrecognized CodeView record")
        # Leave the record size, PDB GUID and age intact. The optional path follows them.
        start, stop = offset+24, offset+length
        end = image.index(0, start, stop)
        filename = PureWindowsPath(image[start:end].decode("utf-8")).name.encode("utf-8")
        if not filename.lower().endswith(b".pdb"):
            raise ValueError("Expected a PDB filename in the CodeView record")
        image[start:stop] = filename.ljust(stop-start, b"\0")
    return image


def instructions(version, chinese):
    tag = f"{REPOSITORY}/tree/v{version}"
    release = f"{REPOSITORY}/releases/tag/v{version}"
    upstream = f"https://projects.blender.org/blender/blender/src/commit/{BLENDER_REVISION}"
    commands = r"""```powershell
.\install_backend.ps1 -PatchedExe .\blender.exe -BlenderInstall "$env:ProgramFiles\Blender Foundation\Blender 5.2" -Destination .\backend
```"""
    if chinese:
        return f"""# Cycles Frame Pipeline {version} · Windows x64

安装官方 Blender 5.2.1 LTS（构建 `9e2066aef7ef`），解压本包，在解压目录的 PowerShell 中运行以下命令。目标目录必须是新目录。安装器会读取本机官方运行时和 HIP 内核，创建独立的配套 Blender。

{commands}

从[对应版本]({release})下载 `cycles_frame_pipeline-{version}.zip`，在 Blender 偏好设置中选择「从磁盘安装」。在插件偏好设置中将「定制 Blender 程序」指向新建的 `backend\\blender.exe`。

[中文说明与构建步骤]({tag}/README.zh-CN.md) · [本版本完整工程源码及补丁]({tag}) · [对应 Blender 上游源码]({upstream})

本包随附项目许可证 `COPYING`、官方 `copyright.txt` 以及 `license/` 中的第三方许可声明。
"""
    return f"""# Cycles Frame Pipeline {version} · Windows x64

Install official Blender 5.2.1 LTS (build `9e2066aef7ef`). Extract this archive, open PowerShell in the extracted directory and run the command below. Choose a new destination directory. The installer copies your local official runtime and HIP kernels into a separate Blender installation.

{commands}

Download `cycles_frame_pipeline-{version}.zip` from the [matching release]({release}) and use **Install from Disk** in Blender's extension preferences. Point the extension's custom Blender executable preference to the new `backend\\blender.exe`.

[English manual and build instructions]({tag}/README.md) · [Release project source and patches]({tag}) · [Corresponding upstream Blender source]({upstream})

License notices are included in `COPYING`, the official `copyright.txt` and `license/`.
"""


def add(archive, name, content):
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, content, compress_type=ZIP_DEFLATED, compresslevel=6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patched_exe", type=Path)
    parser.add_argument("official_install", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()
    version = tomllib.loads((ROOT/"extension/blender_manifest.toml").read_text("utf8"))["version"]
    official = args.official_install
    info = subprocess.check_output([official/"blender.exe", "--version"], text=True,
                                   encoding="utf8", errors="replace")
    if BLENDER_REVISION[:12] not in info:
        raise SystemExit("Select the official Blender 5.2.1 Windows x64 installation")
    notices = sorted(p for p in (official/"license").rglob("*") if p.is_file())
    if not notices or any(p.suffix.lower() not in {".txt", ".md", ".json"} for p in notices):
        raise SystemExit("Unexpected contents in the official Blender license directory")
    image = release_executable(args.patched_exe)
    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output_zip.parent) as temp:
        staged = Path(temp)/"backend.zip"
        with ZipFile(staged, "w") as archive:
            add(archive, "blender.exe", image)
            add(archive, "install_backend.ps1", (ROOT/"tools/install_backend.ps1").read_bytes())
            add(archive, "COPYING", (ROOT/"COPYING").read_bytes())
            add(archive, "copyright.txt", (official/"copyright.txt").read_bytes())
            for notice in notices:
                add(archive, notice.relative_to(official).as_posix(), notice.read_bytes())
            add(archive, "README.md", instructions(version, False).encode("utf-8"))
            add(archive, "README.zh-CN.md", instructions(version, True).encode("utf-8"))
        staged.replace(args.output_zip)
    print(f"{args.output_zip} ({args.output_zip.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
