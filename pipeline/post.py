"""Persistent CPU worker. Its factory-startup scene contains no production geometry."""
import json
import os
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from composition import SOCKET_TAG, apply


def main():
    working = Path(sys.argv[sys.argv.index("--") + 1])
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.render.compositor_device = "CPU"
    scene.render.compositor_denoise_device = "CPU"
    scene.render.use_sequencer = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_management = "FOLLOW_SCENE"
    info = json.loads((working / "profile.json").read_text(encoding="utf8"))
    with bpy.data.libraries.load(str(working / "graph.blend")) as (_, dest):
        dest.node_groups = [info["graph"]]
    tree = dest.node_groups[0]
    scene.compositing_node_group = tree
    inputs = [node for node in tree.nodes if SOCKET_TAG in node]
    image_node = tree.nodes.new("CompositorNodeImage")
    denoise = tree.nodes.new("CompositorNodeDenoise")
    for line in sys.stdin:
        job = json.loads(line)
        frame = job["frame"]
        cfg = job["settings"]
        png = Path(job["output"])
        raw = working / f"{frame}.exr"
        tmp = working / f"{frame}.png"
        print(f"PIPELINE_POST_START {frame}", flush=True)
        scene.frame_set(frame)
        apply(scene.render, cfg["render"])
        apply(scene.render.image_settings, cfg["png"])
        scene.display_settings.display_device = cfg["display"]
        apply(scene.view_settings, cfg["view"])
        image = bpy.data.images.load(str(raw), check_existing=False)
        try:
            image_node.image = image
            image_node.layer = job["layer"]
            tree.links.new(image_node.outputs["Combined"], denoise.inputs["Image"])
            denoise.inputs["Prefilter"].default_value = cfg["denoise"]["denoising_prefilter"].title()
            denoise.inputs["Quality"].default_value = cfg["denoise"]["denoising_quality"].title()
            guide_passes = cfg["denoise"]["denoising_input_passes"].split("_")
            for kind in ("Albedo", "Normal"):
                guide = denoise.inputs[kind]
                for link in list(guide.links):
                    tree.links.remove(link)
                if kind.upper() in guide_passes:
                    tree.links.new(image_node.outputs["Denoising " + kind], guide)
            for route in inputs:
                output = denoise.outputs[0] if route[SOCKET_TAG] == "Image" else image_node.outputs["Alpha"]
                tree.links.new(output, route.inputs[0])
            scene.render.filepath = str(tmp)
            if 'FINISHED' not in bpy.ops.render.render(write_still=True):
                raise RuntimeError(f"compositing cancelled for frame {frame}")
            os.replace(tmp, png)
        finally:
            bpy.data.images.remove(image)
        raw.unlink()
        print(f"PIPELINE_FRAME_DONE {frame}", flush=True)
        (working / f"{frame}.done").touch()


if __name__ == "__main__":
    main()
