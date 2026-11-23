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
        def check(diff, *args):
            return subprocess.run([*git, "apply", "--check", *args, "-"], input=diff,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if check(combined, "--reverse"):
            return
        if verify:
            raise SystemExit("The checkout differs from the packaged Cycles patch series")
        if check(combined):
            subprocess.run([*git, "apply", "--whitespace=nowarn", "-"], input=combined, check=True)
            return
        # Later patches may replace hunks introduced by earlier releases. Match the
        # complete old series, then apply just the delta to the new version.
        final_tree = subprocess.check_output([*git, "write-tree"], env=env).decode().strip()
        for path in reversed(patches[1:]):
            subprocess.run([*git, "apply", "--cached", "--reverse", "--whitespace=nowarn", str(path)],
                           env=env, check=True)
            prefix = subprocess.check_output([*git, "diff", "--cached", "--binary", "HEAD"], env=env)
            if check(prefix, "--reverse"):
                delta = subprocess.check_output([*git, "diff", "--cached", "--binary", "-R", final_tree], env=env)
                subprocess.run([*git, "apply", "--whitespace=nowarn", "-"], input=delta, check=True)
                return
        raise SystemExit("The checkout does not match this Blender patch series or an earlier release")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    install(Path(sys.argv[1]).resolve(), sorted((root / "patches").glob("*.patch")),
            verify="--check" in sys.argv[2:])
