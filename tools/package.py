# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a Blender extension ZIP from the project source."""
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "extension" / "blender_manifest.toml"
with manifest.open("rb") as stream:
    metadata = tomllib.load(stream)
target = ROOT / "dist" / f"{metadata['id']}-{metadata['version']}.zip"
target.parent.mkdir(exist_ok=True)
files = {manifest: manifest.name, manifest.with_name("__init__.py"): "__init__.py"}
for path in sorted((ROOT / "pipeline").glob("*.py")):
    files[path] = f"pipeline/{path.name}"
for name in ("render.py", "post.py", "composition.py", "frame_snapshot_paths.py", "render_profile.py",
             "bvh_producer.py", "native_capture.py", "native_post.py"):
    if f"pipeline/{name}" not in files.values():
        raise FileNotFoundError(name)
license_path = ROOT / "COPYING"
files[license_path] = license_path.name
with zipfile.ZipFile(target.with_suffix(".tmp"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path, name in files.items():
        archive.write(path, name)
target.with_suffix(".tmp").replace(target)
print(target)

source_zip = target.with_name(f"{metadata['id']}-source-{metadata['version']}.zip")
with zipfile.ZipFile(source_zip.with_suffix(".tmp"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ("README.md", "README.zh-CN.md", "COPYING", ".gitattributes", ".gitignore",
                 ".github/workflows/release.yml"):
        archive.write(ROOT / name, name)
    # Keep locally built binaries, input scenes, raw telemetry and user data out of releases.
    public_sources = {
        "extension": {".py", ".toml"},
        "pipeline": {".py"},
        "engine": {".py", ".ps1", ".patch", ".h", ".cpp", ".md"},
        "tools": {".py", ".ps1"},
        "benchmarks": {".py", ".md", ".csv", ".png"},
        "docs": {".md"},
        "release": {".md", ".sha256"},
    }
    for directory, extensions in public_sources.items():
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix.lower() in extensions and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT))
source_zip.with_suffix(".tmp").replace(source_zip)
print(source_zip)
