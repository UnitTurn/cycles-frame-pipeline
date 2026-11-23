"""Compare native packed BVH output, decoded pixels and rejection of a stale snapshot."""

import argparse
from array import array
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def render(args):
    import bpy

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_render import make_scene

    scene = make_scene(args.device, args.hip_name, False, 2, True)
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.cycles.use_deform_motion = True
            obj.cycles.motion_steps = 2
    for frame in ((args.capture,) if args.capture else (1, 2, 3)):
        scene.frame_set(frame)
        if args.capture:
            dest = args.work / f"frame{frame}.xbvh"
            os.environ["CYCLES_FRAMEPIPE_PRODUCE"] = str(dest)
        else:
            target = 1 if args.mode == "mismatch" and frame == 1 else frame + 1
            os.environ["CYCLES_FRAMEPIPE_NEXT"] = str(args.work / f"frame{target}.xbvh")
            os.environ["CYCLES_FRAMEPIPE_LAST"] = str(int(frame == 3))
        scene.render.filepath = str(args.work / f"{args.mode}-{frame}.png")
        bpy.ops.render.render(write_still=not args.capture)
        if args.capture:
            if not dest.is_file():
                raise RuntimeError(f"Input capture missing for frame {frame}")
            continue
        image = bpy.data.images.load(scene.render.filepath, check_existing=False)
        pixels = array("f", [0]) * len(image.pixels)
        image.pixels.foreach_get(pixels)
        (args.work / f"{args.mode}-{frame}.rgba").write_bytes(pixels.tobytes())
        bpy.data.images.remove(image)


def check(args):
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        if args.work:
            args.work.mkdir(parents=True, exist_ok=True)
            root = Path(tempfile.mkdtemp(prefix="exact-", dir=args.work.resolve()))
        print("Test directory", root, flush=True)
        reports = {}
        for mode, capture in [("capture", i) for i in (1, 2, 3)] + [
                ("original", 0), ("exact", 0), ("mismatch", 0)]:
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("CYCLES_FRAMEPIPE_")}
            enabled = mode in ("exact", "mismatch")
            env.update(CYCLES_BVH_LOOKAHEAD=str(int(enabled)),
                       CYCLES_FRAMEPIPE_EXACT=str(int(enabled)),
                       CYCLES_FRAMEPIPE_HIP_BLAS="0", CYCLES_FRAMEPIPE_AUDIT_PACKED="1")
            cmd = [str(args.blender.resolve()), "-b", "--factory-startup", "-t", "4",
                   "--python-exit-code", "9", "-P", str(Path(__file__).resolve()),
                   "--", "--inside", "--work", str(root), "--mode", mode, "--device", args.device,
                   "--capture", str(capture)]
            if args.hip_name:
                cmd.extend(("--hip-name", args.hip_name))
            log = root / f"{mode}-{capture}.log"
            with log.open("wb") as f:
                p = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
            msg = log.read_text(errors="replace", encoding="utf8")
            if p.returncode:
                raise RuntimeError(f"{log}\n{msg[-1800:]}")
            if capture:
                assert "FRAMEPIPE_EXACT captured " in msg, log
            else:
                reports[mode] = msg
        digests = [re.findall(r"FRAMEPIPE_EXACT packed=([0-9A-Fa-f]+)", reports[x])
                   for x in ("original", "exact", "mismatch")]
        assert len(digests[0]) == 3 and all(d == digests[0] for d in digests), digests
        assert reports["exact"].count("FRAMEPIPE_EXACT hit=native") == 2, reports["exact"][-2000:]
        assert "FRAMEPIPE_EXACT miss=input-mismatch" in reports["mismatch"], reports["mismatch"][-2000:]
        for i in (1, 2, 3):
            pixel = (root / f"original-{i}.rgba").read_bytes()
            for mode in ("exact", "mismatch"):
                assert pixel == (root / f"{mode}-{i}.rgba").read_bytes(), (mode, i)
        print(f"{args.device}: 3 packed BVHs and decoded images match. Two native hits; stale input rejected.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("blender", type=Path, nargs="?")
    p.add_argument("--work", type=Path)
    p.add_argument("--device", choices=("CPU", "HIP"), default="CPU")
    p.add_argument("--hip-name")
    p.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--capture", type=int, default=0, help=argparse.SUPPRESS)
    p.add_argument("--mode", default="", help=argparse.SUPPRESS)
    inside = "--inside" in sys.argv
    opts = p.parse_args(sys.argv[sys.argv.index("--")+1:] if inside else None)
    render(opts) if inside else check(opts)
