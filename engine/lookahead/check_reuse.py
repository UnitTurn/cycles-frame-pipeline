"""Exercise native whole-tree and partition reuse on sparse animation, with and without snapshots."""

import argparse
from array import array
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


FRAMES = (1, 2, 3)
GRID_WIDTH = 128
GRID_HEIGHT = 64
REFS = GRID_WIDTH * GRID_HEIGHT + 1


def make_fixture(args):
    import bpy

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_render import make_base_scene

    scene, material = make_base_scene(args.device, args.hip_name, 0, False)
    vertices = []
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            px, py = x * 0.05 - 3.2, y * 0.05 - 2.0
            vertices.extend(((px, py, 0), (px + 0.03, py, 0), (px, py + 0.03, 0)))
    # A visible triangle above the grid. The first two vertices define all its bounds.
    marker = len(vertices)
    vertices.extend(((-0.6, 1.4, 0), (0.6, 2.1, 0), (-0.5, 2.03, 0)))
    triangles = [(i, i + 1, i + 2) for i in range(0, len(vertices), 3)]
    mesh = bpy.data.meshes.new("Sparse animation")
    mesh.from_pydata(vertices, [], triangles)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)

    obj.shape_key_add(name="Basis")
    interior = obj.shape_key_add(name="Move inside bounds")
    interior.data[marker + 2].co.x += 0.55
    translation = obj.shape_key_add(name="Change one bound")
    translation.data[3 * (GRID_WIDTH * 49 + 99) + 1].co.x += 0.002
    for frame in FRAMES:
        # The marker changes visibly on both frame transitions without affecting its
        # bounds. Only one grid triangle changes its box in frame 3.
        for key, value in ((interior, (frame - 1) * 0.5), (translation, frame == 3)):
            key.value = float(value)
            key.keyframe_insert(data_path="value", frame=frame)
    if args.case == "biased-capture":
        # Capture a valid native target frame whose input is wrong in a second region.
        # The rightmost vertex in this triangle determines its maximum X.
        biased = obj.shape_key_add(name="Snapshot-only difference")
        biased.data[3 * (GRID_WIDTH * 15 + 24) + 1].co.x += 0.002
        biased.value = 1.0
    return scene


def run_blender(args):
    import bpy

    scene = make_fixture(args)
    snapshot = args.case in ("capture", "biased-capture")
    for frame in ((args.frame,) if snapshot else FRAMES):
        scene.frame_set(frame)
        print(f"FRAMEPIPE_TEST_FRAME={frame}", flush=True)
        if snapshot:
            target = args.work / f"target-{frame}.xbvh"
            os.environ["CYCLES_FRAMEPIPE_PRODUCE"] = str(target)
            bpy.ops.render.render()
            if not target.is_file():
                raise RuntimeError(f"Native input missing for frame {frame}")
            continue
        os.environ["CYCLES_FRAMEPIPE_LAST"] = str(int(frame == FRAMES[-1]))
        if args.case == "next" and frame < FRAMES[-1]:
            os.environ["CYCLES_FRAMEPIPE_NEXT"] = str(args.work / f"target-{frame + 1}.xbvh")
        else:
            os.environ.pop("CYCLES_FRAMEPIPE_NEXT", None)
        target = args.work / f"{args.case}-{frame}.png"
        scene.render.filepath = str(target)
        if "FINISHED" not in bpy.ops.render.render(write_still=True):
            raise RuntimeError(f"Render failed on frame {frame}")
        image = bpy.data.images.load(str(target), check_existing=False)
        pixels = array("f", [0]) * len(image.pixels)
        image.pixels.foreach_get(pixels)
        target.with_suffix(".rgba").write_bytes(pixels.tobytes())
        bpy.data.images.remove(image)


def execute(args, directory, case, frame=0):
    enabled = case in ("previous", "next")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CYCLES_FRAMEPIPE_")}
    env.update(CYCLES_BVH_LOOKAHEAD=str(int(enabled)),
               CYCLES_FRAMEPIPE_EXACT=str(int(enabled)),
               CYCLES_FRAMEPIPE_EXACT_REUSE=str(int(case == "previous")),
               CYCLES_FRAMEPIPE_HIP_BLAS="0", CYCLES_FRAMEPIPE_AUDIT_PACKED="1")
    command = [str(args.blender.resolve()), "-b", "--factory-startup", "-t", "2",
               "--log", "cycles", "--log-level", "debug", "--python-exit-code", "12",
               "-P", str(Path(__file__).resolve()), "--", "--inside", "--case", case,
               "--work", str(directory), "--device", args.device, "--frame", str(frame)]
    if args.hip_name:
        command.extend(("--hip-name", args.hip_name))
    logfile = directory / f"{case}.log"
    with logfile.open("wb") as log:
        run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env)
    report = logfile.read_text(encoding="utf-8", errors="replace")
    if run.returncode:
        raise RuntimeError(f"Blender exited {run.returncode}: {logfile}\n{report[-1800:]}")
    return report


def require_partial(report, source):
    rows = re.findall(rf"FRAMEPIPE_EXACT hit=partial source={source} refs=(\d+) "
                      r"total=(\d+) branches=(\d+)\b", report)
    if len(rows) != 1:
        raise AssertionError(f"Expected one partial hit from {source}; saw {rows!r}")
    reused, total, branches = map(int, rows[0])
    if not (0 < reused < total == REFS and branches > 0):
        raise AssertionError(f"Invalid {source} partial reuse: {reused}/{total}, {branches} branches")
    if re.search(r"FRAMEPIPE_EXACT hit=(?:native|previous-native)\b", report):
        raise AssertionError(f"{source} reported a whole-tree hit on a known mismatch")
    return f"{source} reused {reused}/{total} refs in {branches} native branches"


def check(args, directory):
    from check_render import check_device_and_frames

    # A fresh process independently evaluates each target. Neither input file is produced
    # by the renderer whose hit it will be used to test.
    for case, frame in (("capture", 2), ("biased-capture", 3)):
        capture = execute(args, directory, case, frame)
        if not re.search(rf"FRAMEPIPE_EXACT captured refs={REFS}\b", capture):
            raise AssertionError(f"Expected {REFS} native input references in {case}.log")
    cases = ("sync", "previous", "next")
    reports = {}
    baseline = []
    for case in cases:
        log = execute(args, directory, case)
        frames = check_device_and_frames(log, args.device)
        reports[case] = frames
        if case == "sync" and "FRAMEPIPE_EXACT hit=" in log:
            raise AssertionError("Reuse active during synchronous reference run")
        for i, (frame, report) in enumerate(zip(FRAMES, frames)):
            packed = re.findall(r"FRAMEPIPE_EXACT packed=([0-9a-fA-F]{32})\b", report)
            if len(packed) != 1:
                raise AssertionError(f"{case} frame {frame} expected one packed TLAS, got {packed}")
            decoded = (directory / f"{case}-{frame}.rgba").read_bytes()
            if len(decoded) != 120 * 72 * 4 * array("f").itemsize:
                raise AssertionError(f"Incorrect decoded RGBA size in {case} frame {frame}")
            if case == "sync":
                baseline.append((packed[0], decoded))
            else:
                ref_digest, ref_pixels = baseline[i]
                if packed[0] != ref_digest or decoded != ref_pixels:
                    raise AssertionError(f"{case} frame {frame}: packed equality "
                                         f"{packed[0] == ref_digest}, pixel equality {decoded == ref_pixels}")
    if baseline[0][0] != baseline[1][0] or any(
            baseline[i][1] == baseline[i + 1][1] for i in range(len(FRAMES) - 1)):
        raise AssertionError("Fixture must change visibly between frames and keep frame 1/2 bounds identical")
    previous, next_frames = reports["previous"], reports["next"]
    if not re.search(rf"FRAMEPIPE_EXACT hit=previous-native refs={REFS}\b", previous[1]):
        raise AssertionError("Missing exact previous-frame native hit on frame 2")
    if not re.search(rf"FRAMEPIPE_EXACT hit=native refs={REFS}\b", next_frames[1]):
        raise AssertionError("Missing exact independent next-frame native hit on frame 2")
    summary = (require_partial(previous[2], "previous"), require_partial(next_frames[2], "next"))
    print(f"{args.device}: all three packed hashes and decoded RGBA match synchronous BVH2. "
          f"Whole-tree hits on frame 2. Frame 3: {', '.join(summary)}.")


if __name__ == "__main__":
    inside = "--inside" in sys.argv
    parser = argparse.ArgumentParser(description=__doc__)
    if inside:
        parser.add_argument("--inside", action="store_true")
        parser.add_argument("--case", required=True)
        parser.add_argument("--frame", type=int, default=0)
    else:
        parser.add_argument("blender", type=Path, help="Custom Blender executable")
    parser.add_argument("--device", choices=("CPU", "HIP"), default="CPU")
    parser.add_argument("--hip-name")
    parser.add_argument("--work", type=Path, help="Keep run artifacts in a new subdirectory")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if inside else None)
    if args.hip_name and args.device != "HIP":
        parser.error("--hip-name requires --device HIP")
    if inside:
        run_blender(args)
    elif args.work:
        args.work.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="reuse-", dir=args.work.resolve()))
        print(f"Test outputs: {directory}", flush=True)
        check(args, directory)
    else:
        with tempfile.TemporaryDirectory(prefix="framepipe-reuse-") as tmp:
            check(args, Path(tmp))
