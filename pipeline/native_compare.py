# SPDX-License-Identifier: GPL-3.0-or-later
"""One render, two outputs: compare native inline and replay using exactly the same film."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import bpy
import _cycles

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from composition import qualify, save_graph, settings
from render_profile import apply_profile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="new directory for the paired PNGs")
    parser.add_argument("--frame", type=int, required=True)
    parser.add_argument("--profile", choices=["scene", "ruins-hip256"], default="scene")
    parser.add_argument("--post-threads", type=int, default=6)
    parser.add_argument("--keep-buffer", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.post_threads < 1:
        parser.error("--post-threads must be positive")
    working = args.output.resolve()
    working.mkdir(parents=True, exist_ok=False)
    scene = bpy.context.scene
    frame = args.frame
    with apply_profile(scene, args.profile):
        scene.frame_set(frame)
        layer = qualify(scene)
        info = {"graph": save_graph(scene, layer, working / "graph.blend"),
                "native_use_compositor": bool(scene.render.use_compositing and scene.compositing_node_group)}
        (working / "profile.json").write_text(json.dumps(info), encoding="utf8")
        payload = {"frame": frame, "settings": settings(scene), "layer": layer.name,
                   "output": str(working / "replay.png")}
        raw = working / f"{frame}.cycles.exr"
        scene.render.filepath = str(working / "inline.png")
        _cycles.native_frame_paths(str(raw), "", True)
        try:
            result = bpy.ops.render.render(write_still=True, scene=scene.name)
            if 'FINISHED' not in result or not _cycles.native_frame_done():
                raise RuntimeError("Unable to capture the full film before inline denoising")
        finally:
            _cycles.native_frame_paths("", "")
        if args.keep_buffer:
            os.link(raw, working / "captured-film.cycles.exr")
    env = os.environ.copy()
    env["OIDN_NUM_THREADS"] = str(args.post_threads)
    env.pop("CYCLES_BVH_LOOKAHEAD", None)
    command = [bpy.app.binary_path, "-b", "--factory-startup", "-t", str(args.post_threads),
               "--python-exit-code", "9", "-P", str(HERE / "native_post.py"), "--", str(working)]
    subprocess.run(command, input=json.dumps(payload) + "\n", text=True, encoding="utf8",
                   env=env, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(f"PAIRED_NATIVE_OUTPUT {working}", flush=True)


if __name__ == "__main__":
    main()
