"""Run with system Python and the custom blender.exe to exercise the actual BVH2 render path."""

import argparse
import json
import os
from array import array
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def make_base_scene(device, hip_name, time_steps, motion_blur):
    import bpy

    # Cycles ignores debug_bvh_layout on CPU unless both preference switches are set.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    prefs = bpy.context.preferences
    prefs.view.show_developer_ui = True
    prefs.experimental.use_cycles_debug = True
    scene.render.engine = "CYCLES"
    scene.cycles.debug_bvh_layout = "BVH2"
    scene.cycles.debug_bvh_type = "STATIC_BVH"
    scene.cycles.debug_bvh_time_steps = time_steps
    scene.render.use_motion_blur = motion_blur
    if device == "HIP":
        cycles_prefs = prefs.addons["cycles"].preferences
        cycles_prefs.compute_device_type = "HIP"
        cycles_prefs.use_hiprt = False
        devices = cycles_prefs.get_devices_for_type("HIP")
        cards = [card for card in devices if card.type == "HIP"]
        if hip_name:
            cards = [card for card in cards if hip_name.casefold() in card.name.casefold()
                     or hip_name == card.id]
        elif len(cards) > 1:
            # This fixture targets the user's workstation. Avoid accidentally running multiple GPUs.
            cards = [card for card in cards if "RX 7800 XT" in card.name]
        if len(cards) != 1:
            available = [f"{card.name} [{card.id}]" for card in devices if card.type == "HIP"]
            raise RuntimeError(f"Select a single plain HIP device via --hip-name. Available: {available}")
        gpu = cards[0]
        for entry in cycles_prefs.devices:
            entry.use = entry.type == "HIP" and entry.id == gpu.id
        scene.cycles.device = "GPU"
        device_id = gpu.id
    else:
        scene.cycles.device = "CPU"
        device_id = "CPU"
    print("FRAMEPIPE_TEST_DEVICE=" + json.dumps({"type": device, "id": device_id}), flush=True)
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    scene.render.use_persistent_data = True
    scene.render.film_transparent = True
    scene.render.resolution_x = 120
    scene.render.resolution_y = 72
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"

    camera = bpy.data.cameras.new("Orthographic check")
    camera.type = "ORTHO"
    camera.ortho_scale = 7.7
    obj = bpy.data.objects.new("Camera", camera)
    scene.collection.objects.link(obj)
    obj.location.z = 5
    scene.camera = obj

    mat = bpy.data.materials.new("Constant emission")
    mat.use_nodes = True
    emit = mat.node_tree.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.75, 0.35, 0.125, 1)
    mat.node_tree.links.new(emit.outputs[0], mat.node_tree.nodes["Material Output"].inputs[0])
    return scene, mat


def make_scene(device, hip_name, hip_blas, time_steps, motion_blur):
    import bpy

    scene, mat = make_base_scene(device, hip_name, time_steps, motion_blur)

    def create_mesh(name, vertices, faces):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        result = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(result)
        mesh.materials.append(mat)
        return result

    verts, faces = [], []
    for y in range(48):
        for x in range(72):
            idx = len(verts)
            a, b = x * 0.072 - 3.3, y * 0.072 - 1.9
            verts.extend(((a, b, 0), (a + 0.055, b, 0), (a, b + 0.055, 0)))
            faces.append((idx, idx + 1, idx + 2))
    obj = create_mesh("Deforming triangles", verts, faces)
    obj.shape_key_add(name="Basis")
    moved = obj.shape_key_add(name="Moved")
    for index, point in enumerate(moved.data):
        point.co.x += 0.7
        point.co.y += 0.2
        if hip_blas and index % 3 == 0:
            # Change the shape of each triangle independently of its object transform.
            point.co.y += 0.1 if (index // 3) % 2 == 0 else -0.12
    for frame, value in ((1, 0.0), (2, 0.5), (3, 1.0)):
        moved.value = value
        moved.keyframe_insert(data_path="value", frame=frame)

    extra = create_mesh("Topology change", [(-2, -1.5, 0.1), (0, -1.5, 0.1), (-2, 0, 0.1)], [(0, 1, 2)])
    for frame, hidden in ((1, True), (2, True), (3, False)):
        extra.hide_render = hidden
        extra.keyframe_insert(data_path="hide_render", frame=frame)
    if hip_blas:
        create_mesh("Static marker", [(1, 1, 0.3), (3, 1, 0.3), (3, 1.5, 0.3)], [(0, 1, 2)])
        moving = create_mesh("Rigid moving mesh", [(0, -1, 0.2), (1, -1, 0.2), (0, 0, 0.2)],
                             [(0, 1, 2)])
        for frame, dx in ((1, 1.75), (2, 0.5), (3, -0.5)):
            moving.location.x = dx
            moving.keyframe_insert(data_path="location", frame=frame)
    return scene


def render_fixture(directory, device, hip_name, hip_blas, time_steps, motion_blur):
    import bpy

    scene = make_scene(device, hip_name, hip_blas, time_steps, motion_blur)
    directory.mkdir(parents=True)
    for frame in (1, 2, 3):
        os.environ["CYCLES_FRAMEPIPE_LAST"] = "1" if frame == 3 else "0"
        scene.frame_set(frame)
        path = directory / f"{frame}.png"
        scene.render.filepath = str(path)
        print(f"FRAMEPIPE_TEST_FRAME={frame}", flush=True)
        if 'FINISHED' not in bpy.ops.render.render(write_still=True):
            raise RuntimeError(f"Render failed on frame {frame}")
        image = bpy.data.images.load(str(path), check_existing=False)
        pixels = array("f", [0]) * len(image.pixels)
        image.pixels.foreach_get(pixels)
        with (directory / f"{frame}.rgba").open("wb") as handle:
            pixels.tofile(handle)
        bpy.data.images.remove(image)


def check_device_and_frames(log, device):
    selection = re.findall(r"^FRAMEPIPE_TEST_DEVICE=(.+)$", log, re.MULTILINE)
    if len(selection) != 1 or json.loads(selection[0])["type"] != device:
        raise AssertionError(f"Expected exactly one {device} device selection")
    device_id = json.loads(selection[0])["id"]
    halves = re.split(r"^FRAMEPIPE_TEST_FRAME=([0-9]+)\s*$", log, flags=re.MULTILINE)
    if halves[1::2] != ["1", "2", "3"]:
        raise AssertionError("Missing or repeated frame boundary")
    reports = halves[2::2]
    for frame, report in enumerate(reports, 1):
        tracing = re.findall(r"Path tracing on: ([^\r\n]+)", report)
        if (len(tracing) != 1 or f"({device})" not in tracing[0] or f"[{device_id}]" not in tracing[0]
                or "Hardware Ray-Tracing: Off" not in report or "Using BVH2 layout." not in report):
            raise AssertionError(f"Frame {frame}: actual {device} / BVH2 path unconfirmed: {tracing}")
    return reports


def check(exe, work, device, hip_name, hip_blas, time_steps, motion_blur):
    script = Path(__file__).resolve()
    for name, enabled in (("original", "0"), ("lookahead", "1")):
        env = os.environ.copy()
        for key in ("CYCLES_FRAMEPIPE_CAPTURE", "CYCLES_FRAMEPIPE_NEXT", "CYCLES_FRAMEPIPE_CACHE_DIR",
                    "CYCLES_FRAMEPIPE_MAX_REFS"):
            env.pop(key, None)
        env["CYCLES_BVH_LOOKAHEAD"] = enabled
        env["CYCLES_FRAMEPIPE_HIP_BLAS"] = "1" if hip_blas and name == "lookahead" else "0"
        dest = work / name
        command = [str(exe), "--background", "--factory-startup", "-t", "2",
                   "--log", "cycles", "--log-level", "debug", "--python-exit-code", "12",
                   "--python", str(script), "--", "--render-fixture", str(dest), "--device", device]
        if hip_name:
            command.extend(["--hip-name", hip_name])
        command.extend(["--bvh-time-steps", str(time_steps)])
        if hip_blas:
            command.append("--hip-blas")
        if motion_blur:
            command.append("--motion-blur")
        run = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = run.stdout.decode(errors="replace").replace("\r\n", "\n")
        (work / f"{name}.log").write_text(text, encoding="utf-8")
        if run.returncode:
            raise RuntimeError(text[-2000:])
        reports = check_device_and_frames(text, device)
        if name == "original" and ("FRAMEPIPE_BVH " in text or "FRAMEPIPE_HIP_BLAS " in text):
            raise AssertionError("Acceleration unexpectedly active in reference render")
    events = [[line for line in report.splitlines() if "FRAMEPIPE_BVH " in line] for report in reports]
    if (not any("miss=cold" in line for line in events[0])
            or not any("launched target=2 " in line for line in events[0])
            or not re.search(r"FRAMEPIPE_BVH prepared target=2 input=prediction refs=\d+", text)
            or not any("hit=refit " in line for line in events[1])
            or not any("launched target=3 " in line for line in events[1])
            or not any("miss=identity" in line for line in events[2])
            or any("hit=" in line or "launched " in line for line in events[2])):
        raise AssertionError(f"Expected real refit on frame 2 and topology rejection on frame 3: {events}")
    if hip_blas:
        # Three visible objects for thousands of triangles on the first two frames.
        # Frame 2 deforms one mesh, moves a rigid mesh and leaves another mesh unchanged.
        counters = [re.search(r"FRAMEPIPE_HIP_BLAS objects=\d+ geometries=(\d+) scheduled_blas_updates=(\d+)", x)
                    for x in reports]
        if (not all(counters) or not any(re.search(r"\bhit=refit refs=3\b", line) for line in events[1])
                or not 0 < int(counters[1][2]) < int(counters[0][2])):
            raise AssertionError(f"Expected object-only TLAS and partial BLAS rebuild: {events}, {counters}")
        print("Scheduled geometry BVH updates by frame:", [int(row[2]) for row in counters])
    last = None
    for frame in (1, 2, 3):
        colors = []
        for name in ("original", "lookahead"):
            values = array("f")
            values.frombytes((work / name / f"{frame}.rgba").read_bytes())
            colors.append(values)
        if len(colors[0]) != 120 * 72 * 4 or len(colors[0]) != len(colors[1]):
            raise AssertionError("Wrong dimensions")
        delta = max(abs(a - b) for a, b in zip(*colors))
        if delta > 1e-6 or max(colors[0][3::4]) < 0.25 or colors[0] == last:
            raise AssertionError(f"Frame {frame}: wrong or unchanged image, maximum difference {delta}")
        last = colors[0]
        print(f"Frame {frame}: maximum pixel difference {delta:g}; {events[frame-1]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["CPU", "HIP"], default="CPU")
    parser.add_argument("--hip-name", help="HIP device name substring or exact device ID")
    parser.add_argument("--hip-blas", action="store_true",
                        help="Keep geometry BVHs in the optimized pass and compare to normal HIP")
    parser.add_argument("--bvh-time-steps", type=int, choices=range(17), default=0)
    parser.add_argument("--motion-blur", action="store_true", help="Render true shutter motion")
    if "--render-fixture" in sys.argv:
        parser.add_argument("--render-fixture", type=Path, required=True)
        args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
        render_fixture(args.render_fixture, args.device, args.hip_name, args.hip_blas,
                       args.bvh_time_steps, args.motion_blur)
    else:
        parser.add_argument("blender", type=Path)
        parser.add_argument("--work", type=Path, help="Keep the logs and tiny reference renders here.")
        args = parser.parse_args()
        if (args.hip_name or args.hip_blas) and args.device != "HIP":
            parser.error("--hip-name and --hip-blas require --device HIP")
        with tempfile.TemporaryDirectory() as scratch:
            work = Path(scratch)
            if args.work:
                args.work.mkdir(parents=True, exist_ok=True)
                work = Path(tempfile.mkdtemp(prefix=f"{args.device.lower()}-", dir=args.work.resolve()))
                print(f"Keeping logs and rendered images in {work}", flush=True)
            check(args.blender.resolve(), work, args.device, args.hip_name, args.hip_blas,
                  args.bvh_time_steps, args.motion_blur)
