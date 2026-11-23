# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the single-language Blender extension packages and the shared project source ZIP."""
import argparse
import json
from pathlib import Path
import re
from string import Formatter
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "extension/blender_manifest.toml"
manifest_text = manifest.read_text(encoding="utf8")
metadata = tomllib.loads(manifest_text)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--locale", choices=("en", "zh-CN"), help="build one UI language (default: both)")
parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
parser.add_argument("--extension-only", action="store_true", help="omit the source archive")
args = parser.parse_args()
dist = args.output_dir
dist.mkdir(parents=True, exist_ok=True)
files = {manifest.with_name("__init__.py"): "__init__.py", ROOT / "COPYING": "COPYING"}
for path in sorted((ROOT / "pipeline").glob("*.py")):
    files[path] = f"pipeline/{path.name}"
for name in ("render.py", "post.py", "composition.py", "frame_snapshot_paths.py", "render_profile.py",
             "bvh_producer.py", "native_capture.py", "native_post.py"):
    if f"pipeline/{name}" not in files.values():
        raise FileNotFoundError(name)


def format_fields(catalog):
    return {key: sorted(field for _, field, _, _ in Formatter().parse(value) if field is not None)
            for key, value in catalog.items()}


catalogs = {locale: json.loads((manifest.parent / "locales" / f"{locale}.json").read_text(encoding="utf8"))
            for locale in ("en", "zh-CN")}
if format_fields(catalogs["en"]) != format_fields(catalogs["zh-CN"]):
    raise ValueError("UI catalogs must contain the same keys and formatting fields")
for locale in ([args.locale] if args.locale else catalogs):
    catalog = catalogs[locale]
    localized = manifest_text
    for name in ("name", "tagline", "files"):
        value = json.dumps(catalog["manifest." + name], ensure_ascii=False)
        localized, count = re.subn(rf"^{name} = .+$", lambda _: f"{name} = {value}", localized, flags=re.M)
        if count != 1:
            raise ValueError(f"Expected one manifest field {name}")
    target = dist / f"{metadata['id']}-{metadata['version']}-{locale}.zip"
    with zipfile.ZipFile(target.with_suffix(".tmp"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # GitHub Actions and local builds should produce the same installable ZIP.
        contents = {name: path.read_bytes().replace(b"\r\n", b"\n") for path, name in files.items()}
        contents["blender_manifest.toml"] = localized.encode("utf8")
        contents["ui.json"] = json.dumps(catalog, ensure_ascii=False, indent=2).encode("utf8")
        for name, data in sorted(contents.items()):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)
    target.with_suffix(".tmp").replace(target)
    print(target)

if args.extension_only:
    sys.exit(0)

source_zip = dist / f"{metadata['id']}-source-{metadata['version']}.zip"
with zipfile.ZipFile(source_zip.with_suffix(".tmp"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in ("README.md", "README.zh-CN.md", "COPYING", "LICENSES/Apache-2.0.txt",
                 ".gitattributes", ".gitignore", ".github/workflows/release.yml", ".github/workflows/check.yml"):
        archive.write(ROOT / name, name)
    # Keep locally built binaries, input scenes, raw telemetry and user data out of releases.
    public_sources = {
        "extension": {".py", ".toml", ".json"},
        "pipeline": {".py"},
        "engine": {".py", ".ps1", ".patch", ".h", ".cpp", ".md", ".cmake"},
        "tools": {".py", ".ps1", ".psd1"},
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
