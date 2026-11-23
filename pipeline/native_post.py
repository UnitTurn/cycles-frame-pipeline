# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay a Cycles raw frame through the native denoiser, output driver and PNG writer."""

import json
import os
from pathlib import Path
import sys

import bpy
import _cycles

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composition import SOCKET_TAG, apply


def load_compositor(scene, path, name):
    if name is None:
        scene.compositing_node_group = None
        scene.render.use_compositing = False
        return None
    with bpy.data.libraries.load(str(path)) as (_, dest):
        dest.node_groups = [name]
    tree = dest.node_groups[0]
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    render_layer = tree.nodes.new("CompositorNodeRLayers")
    render_layer.scene = scene
    for node in tree.nodes:
        if SOCKET_TAG in node:
            tree.links.new(render_layer.outputs[node[SOCKET_TAG]], node.inputs[0])
    return render_layer


def main():
    working = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_use_gpu = False
    scene.render.use_sequencer = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_management = "FOLLOW_SCENE"
    info = json.loads((working / "profile.json").read_text(encoding="utf8"))
    base_name = info["graph"] if info["native_use_compositor"] else None
    base_layer = load_compositor(scene, working / "graph.blend", base_name)
    for line in sys.stdin:
        job = json.loads(line)
        frame = job["frame"]
        raw = working / f"{frame}.cycles.exr"
        tmp = working / f"{frame}.png"
        cfg = job["settings"]
        print(f"PIPELINE_POST_START {frame}", flush=True)
        scene.frame_set(frame)
        render_layer = base_layer
        if "frame_graph" in job:
            base_tree = scene.compositing_node_group
            before = set(bpy.data.user_map())
            frame_path = working / f"{frame}.blend"
            render_layer = load_compositor(scene, frame_path, job["frame_graph"])
            # Record appended IDs before rendering creates its Render Result.
            appended = set(bpy.data.user_map()) - before
        scene.view_layers[0].name = job["layer"]
        if render_layer is not None:
            render_layer.layer = job["layer"]
        apply(scene.render, cfg["render"])
        apply(scene.render.image_settings, cfg["png"])
        scene.display_settings.display_device = cfg["display"]
        apply(scene.view_settings, cfg["view"])
        scene.render.filepath = str(tmp)
        _cycles.native_frame_paths("", str(raw))
        try:
            result = bpy.ops.render.render(write_still=True, scene=scene.name)
            if 'FINISHED' not in result or not _cycles.native_frame_done() or not tmp.is_file():
                raise RuntimeError(f"Cycles did not replay and write frame {frame}")
        finally:
            _cycles.native_frame_paths("", "")
            if "frame_graph" in job:
                scene.compositing_node_group = base_tree
                scene.render.use_compositing = base_tree is not None
                if appended:
                    bpy.data.batch_remove(appended)
        os.replace(tmp, Path(job["output"]))
        raw.unlink()
        if job.get("frame_graph"):
            frame_path.unlink()
        (working / f"{frame}.done").touch()
        print(f"PIPELINE_FRAME_DONE {frame}", flush=True)


if __name__ == "__main__":
    main()
