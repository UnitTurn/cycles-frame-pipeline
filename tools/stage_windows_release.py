# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage the tested bilingual Windows overlay for the release workflow."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def git(*args, data=None):
    result = subprocess.run(["git", *args], cwd=ROOT, input=data, stdout=subprocess.PIPE,
                            check=True)
    return result.stdout.decode("ascii").strip()


def main():
    manifest = tomllib.loads((ROOT / "extension/blender_manifest.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    tag = f"v{version}"
    asset = ROOT / "dist" / f"cycles-frame-pipeline-windows-x64-{version}.zip"
    with asset.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    blob = git("hash-object", "-w", "--", str(asset))
    local_ref = f"refs/cycles-frame-pipeline/release-input/{tag}"
    tree = git("mktree", "-z", data=f"100644 blob {blob}\t{asset.name}\0".encode("ascii"))
    previous = subprocess.run(["git", "rev-parse", "--verify", "--quiet", local_ref], cwd=ROOT,
                              stdout=subprocess.PIPE)
    parents = ["-p", previous.stdout.decode("ascii").strip()] if previous.returncode == 0 else []
    commit = git("commit-tree", tree, *parents, "-m", f"Stage tested Windows overlay for {tag}")
    git("update-ref", local_ref, commit)
    (ROOT / "release/windows-overlay.sha256").write_bytes(f"{digest}  {asset.name}\n".encode("ascii"))
    print(f"git push origin {local_ref}:refs/heads/release-input/{tag}")
    print("Commit release/windows-overlay.sha256 on main before pushing the version tag.")


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(__doc__)
    main()
