# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage one tested Windows release asset without adding binaries to the source tree."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def git(*args, data=None):
    result = subprocess.run(["git", *args], cwd=ROOT, input=data, stdout=subprocess.PIPE,
                            text=True, check=True)
    return result.stdout.strip()


def main():
    manifest = tomllib.loads((ROOT / "extension/blender_manifest.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    tag = f"v{version}"
    asset = ROOT / "dist" / f"cycles-frame-pipeline-windows-x64-{version}.zip"
    with asset.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    blob = git("hash-object", "-w", "--", str(asset))
    tree = git("mktree", data=f"100644 blob {blob}\t{asset.name}\n")
    commit = git("commit-tree", tree, "-m", f"Stage tested Windows overlay for {tag}")
    local_ref = f"refs/cycles-frame-pipeline/release-input/{tag}"
    git("update-ref", local_ref, commit)
    (ROOT / "release/windows-overlay.sha256").write_bytes(
        f"{digest}  {asset.name}\n".encode("ascii"))
    print(f"git push origin {local_ref}:refs/heads/release-input/{tag}")
    print("Commit release/windows-overlay.sha256 on main before pushing the version tag.")


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(__doc__)
    main()
