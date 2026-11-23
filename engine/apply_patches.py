# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the pinned Blender patch series to a fresh checkout or its previous release."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def install(source, patches, verify=False):
    git = ["git", "-C", str(source)]
    with tempfile.TemporaryDirectory() as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        subprocess.run([*git, "read-tree", "HEAD"], env=env, check=True)
        for path in patches:
            subprocess.run([*git, "apply", "--cached", "--whitespace=nowarn", str(path)],
                           env=env, check=True)
        combined = subprocess.check_output([*git, "diff", "--cached", "--binary", "HEAD"], env=env)
        def check(*args):
            return subprocess.run([*git, "apply", "--check", *args, "-"], input=combined,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if check("--reverse"):
            return
        if verify:
            raise SystemExit("The checkout differs from the packaged Cycles patch series")
        if check():
            subprocess.run([*git, "apply", "--whitespace=nowarn", "-"], input=combined, check=True)
            return

    # Upgrade a checkout which already has the old release. Keep unrelated local edits.
    for path in patches:
        present = subprocess.run([*git, "apply", "--reverse", "--check", str(path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if present.returncode:
            subprocess.run([*git, "apply", "--whitespace=nowarn", str(path)], check=True)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    install(Path(sys.argv[1]).resolve(), sorted((root / "patches").glob("*.patch")),
            verify="--check" in sys.argv[2:])
