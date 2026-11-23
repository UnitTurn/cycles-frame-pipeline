"""Run with blender -b scene.blend --python-exit-code 1 -P render.py -- --output DIR."""

import argparse
from contextlib import contextmanager
from functools import partial
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from composition import Unsupported, apply, qualify, save_graph, settings, snapshot
from frame_snapshot_paths import set_bvh_frame
from render_profile import apply_profile


def arguments(argv):
    p = argparse.ArgumentParser(description="Render numbered PNGs with bounded asynchronous CPU denoising.")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--step", type=int, help="defaults to the scene's frame step")
    p.add_argument("--profile", choices=["scene", "ruins-hip256"], default="scene")
    p.add_argument("--mode", choices=["native", "serial", "compositor"], default="native",
                   help="native async, native inline, or the older compositor denoiser")
    p.add_argument("--bvh-input", choices=["off", "auto", "next", "previous", "prepared"],
                   help="enable the specified native BVH mode, or turn it off; auto selects by render profile")
    p.add_argument("--stop-file", type=Path)
    p.add_argument("--exr-codec", choices=["NONE", "ZIP", "PIZ"], default="NONE",
                   help="lossless intermediate; NONE minimizes producer CPU work on a local drive")
    p.add_argument("--post-threads", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)))
    p.add_argument("--fallback", choices=["serial", "error"], default="serial")
    p.add_argument("--existing", choices=["error", "skip", "replace"], default="error")
    args = p.parse_args(argv)
    args.lookahead = (args.bvh_input != "off" if args.bvh_input is not None
                      else os.environ.get("CYCLES_BVH_LOOKAHEAD") == "1")
    if args.bvh_input in (None, "auto"):
        args.bvh_input = "previous" if args.profile == "ruins-hip256" else "next"
    if (args.step is not None and args.step < 1) or args.post_threads < 1:
        p.error("--step and --post-threads must be positive")
    if args.bvh_input == "prepared" and args.mode != "native":
        p.error("prepared frames require native frame capture")
    return args


@contextmanager
def output_lock(directory):
    # The idle lock file remains valid after a crash. Only an OS-held lock is authoritative.
    with (directory / ".cycles-pipeline.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"another renderer owns {directory}") from exc
        yield


def render_frame(scene, path, frame, next_frame):
    set_bvh_frame(frame, next_frame)
    scene.render.filepath = str(path)
    if "FINISHED" not in bpy.ops.render.render(write_still=True, scene=scene.name):
        raise RuntimeError(f"render cancelled on frame {frame}")


@contextmanager
def render_settings(scene, layer, exr_codec):
    render = scene.render
    image = render.image_settings
    saved_render = snapshot(render, ("filepath", "use_compositing", "use_file_extension"))
    saved_image = snapshot(image, ("media_type", "file_format", "color_mode", "color_depth",
                                   "exr_codec", "color_management"))
    if layer:
        native = scene.cycles.use_denoising
        passes = layer.cycles.denoising_store_passes
    try:
        render.use_file_extension = True
        if layer:
            render.use_compositing = False
            scene.cycles.use_denoising = False
            layer.cycles.denoising_store_passes = True
            image.media_type = "MULTI_LAYER_IMAGE"
            image.file_format = "OPEN_EXR_MULTILAYER"
            image.color_depth = "32"
            image.color_mode = "RGBA"
            image.color_management = "FOLLOW_SCENE"
            image.exr_codec = exr_codec
        else:
            image.media_type = "IMAGE"
            image.file_format = "PNG"
        yield
    finally:
        if layer:
            scene.cycles.use_denoising = native
            layer.cycles.denoising_store_passes = passes
        apply(image, saved_image)
        apply(render, saved_render)


def check_child(child):
    code = child.poll()
    if code is not None:
        raise RuntimeError(f"CPU postprocess exited early, exit code {code}; see its traceback above")


def wait_finished(child, ack):
    while not ack.exists():
        check_child(child)
        time.sleep(0.05)


def send_post(child, working, ack, payload):
    if ack is not None:
        wait_finished(child, ack)
    check_child(child)
    child.stdin.write(json.dumps(payload) + "\n")
    child.stdin.flush()
    return working / f"{payload['frame']}.done"


def run_job(scene, args, frames, working, bvh_inputs=None):
    if args.stop_file and args.stop_file.exists():
        print("PIPELINE_STOP before first frame", flush=True)
        return
    if args.existing == "skip":
        pending = []
        for frame in frames:
            if (args.output / f"{frame:04d}.png").exists():
                print(f"PIPELINE_FRAME_SKIP {frame}", flush=True)
            else:
                pending.append(frame)
        frames = pending
    if not frames:
        return
    # Apply frame-change evaluation before selecting the layer and copying the compositor.
    scene.frame_set(frames[0])
    native = args.mode == "native"
    prepared = args.bvh_input == "prepared"
    def compositor_tree():
        return scene.compositing_node_group if scene.render.use_compositing else None

    static_tree = compositor_tree()
    if native and (bpy.app.handlers.frame_change_pre or bpy.app.handlers.frame_change_post):
        # A frame handler can edit the same node tree in place after frame_set.
        # Snapshot its evaluated settings for each submitted native frame.
        static_tree = None
    if args.mode == "serial":
        layer = None
        print("PIPELINE_MODE native inline", flush=True)
    else:
        try:
            if native:
                import _cycles
                if not getattr(_cycles, "with_native_frame_post", False):
                    raise Unsupported("this Blender uses its original synchronous frame output")
            layer = qualify(scene)
            graph = save_graph(scene, layer, working / "graph.blend") if static_tree or not native else None
        except Unsupported as exc:
            if args.fallback == "error" or prepared:
                raise
            print(f"PIPELINE_MODE serial ({exc})", flush=True)
            layer = None
    child = None
    if layer:
        profile = {"graph": graph, "native_use_compositor": bool(static_tree)}
        (working / "profile.json").write_text(json.dumps(profile), encoding="utf8")
        post_script = "native_post.py" if native else "post.py"
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", "-t", str(args.post_threads),
               "--python-exit-code", "1", "-P", str(HERE / post_script), "--", str(working)]
        # Never pass the production .blend to the CPU worker.
        env = os.environ.copy()
        env["OIDN_NUM_THREADS"] = str(args.post_threads)
        for key in tuple(env):
            if key == "CYCLES_BVH_LOOKAHEAD" or key.startswith("CYCLES_FRAMEPIPE_"):
                del env[key]
        child = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, encoding="utf8",
                                 env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        print(f"PIPELINE_MODE async {args.mode} CPU worker {child.pid}, {args.post_threads} threads", flush=True)
    ack = None
    pending = None
    if prepared:
        from native_capture import submit_prepared, collect_prepared
    try:
        for i, frame in enumerate(frames):
            if args.stop_file and args.stop_file.exists():
                print("PIPELINE_STOP draining submitted frames", flush=True)
                break
            if child:
                check_child(child)
            out = args.output / f"{frame:04d}.png"
            if out.exists() and args.existing == "skip":
                print(f"PIPELINE_FRAME_SKIP {frame}", flush=True)
                continue
            if out.exists() and args.existing == "error":
                raise FileExistsError(out)
            next_frame = frames[i+1] if i+1 < len(frames) else None
            print(f"PIPELINE_FRAME_START {frame}", flush=True)
            if prepared:
                print(f"READYFRAME frame={frame} event=prepare_begin", flush=True)
            if scene.frame_current != frame or scene.frame_subframe:
                scene.frame_set(frame)
            if bvh_inputs is not None and next_frame is not None:
                if bvh_inputs(scene, next_frame) is None:
                    next_frame = None
            frame_layer = layer
            graph_override = {}
            if frame_layer:
                try:
                    if qualify(scene) != layer:
                        raise Unsupported("active view layer changed during animation")
                    tree = compositor_tree()
                    if native and tree != static_tree:
                        # A new tree or a tree controlled by a frame handler is saved
                        # before the producer advances to the next frame.
                        name = save_graph(scene, layer, working / f"{frame}.blend") if tree else None
                        graph_override["frame_graph"] = name
                except Unsupported as exc:
                    if args.fallback == "error" or prepared:
                        raise
                    print(f"PIPELINE_MODE frame {frame} serial ({exc})", flush=True)
                    frame_layer = None
            cfg = settings(scene) if frame_layer else None
            if prepared:
                submit_prepared(scene, working / f"{frame}.cycles.exr", frame, next_frame)
            elif frame_layer and native:
                from native_capture import capture
                capture(scene, working / f"{frame}.cycles.exr", frame, next_frame)
            else:
                path = working / (f"{frame}.exr" if frame_layer else f"{frame}.png")
                with render_settings(scene, frame_layer, args.exr_codec):
                    render_frame(scene, path, frame, next_frame)
            if frame_layer:
                payload = {"frame": frame, "layer": layer.name, "output": str(out), "settings": cfg,
                           **graph_override}
                if prepared:
                    if pending:
                        collect_prepared(working, pending["frame"])
                        ack = send_post(child, working, ack, pending)
                    pending = payload
                else:
                    ack = send_post(child, working, ack, payload)
            else:
                os.replace(path, out)
                print(f"PIPELINE_FRAME_DONE {frame}", flush=True)
            if bvh_inputs is not None:
                (working / f"{frame}.cfbvh").unlink(missing_ok=True)
        if pending:
            collect_prepared(working, pending["frame"])
            ack = send_post(child, working, ack, pending)
    finally:
        try:
            if prepared:
                import _cycles
                _cycles.formal_end()
        finally:
            if child:
                try:
                    child.stdin.close()
                finally:
                    code = child.wait()
                if code:
                    raise RuntimeError(f"CPU postprocess failed with exit code {code}")
    if ack and not ack.exists():
        raise RuntimeError("CPU worker closed without committing the final PNG")


def run(argv=None):
    """Main-thread entry for background Blender or an add-on; argv excludes Blender arguments."""
    args = arguments(argv if argv is not None else sys.argv[sys.argv.index("--") + 1:])
    lookahead = args.lookahead
    if lookahead:
        import _cycles
        if not getattr(_cycles, "with_exact_bvh", False):
            raise RuntimeError("Exact BVH lookahead requires the 0.2 or newer project backend")
        if args.bvh_input == "prepared" and not hasattr(_cycles, "formal_begin"):
            raise RuntimeError("This Blender backend does not support prepared frames")
    scene = bpy.context.scene
    with apply_profile(scene, args.profile):
        run_scene(scene, args, lookahead)


def run_scene(scene, args, lookahead):
    saved_persistent = scene.render.use_persistent_data
    first = scene.frame_start if args.start is None else args.start
    last = scene.frame_end if args.end is None else args.end
    if first > last:
        raise ValueError("start frame exceeds end frame")
    frames = range(first, last+1, args.step if args.step is not None else scene.frame_step)
    print(f"PIPELINE_TOTAL {len(frames)}", flush=True)
    args.output = args.output.expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    original_frame = scene.frame_current
    original_sub = scene.frame_subframe
    env_keys = ("CYCLES_BVH_LOOKAHEAD", "CYCLES_FRAMEPIPE_CAPTURE", "CYCLES_FRAMEPIPE_NEXT", "CYCLES_FRAMEPIPE_LAST",
                "CYCLES_FRAMEPIPE_EXACT", "CYCLES_FRAMEPIPE_EXACT_REUSE",
                "CYCLES_FRAMEPIPE_CACHE_DIR", "CYCLES_FRAMEPIPE_HIP_BLAS")
    original_env = {key: os.environ.get(key) for key in env_keys}
    with output_lock(args.output):
        working = Path(tempfile.mkdtemp(prefix=".cycles-stage-", dir=args.output))
        try:
            os.environ["CYCLES_BVH_LOOKAHEAD"] = "1" if lookahead else "0"
            bvh_inputs = None
            if args.mode != "compositor" or lookahead:
                os.environ["CYCLES_FRAMEPIPE_HIP_BLAS"] = "0"
            if lookahead:
                os.environ["CYCLES_FRAMEPIPE_EXACT"] = "1"
                os.environ["CYCLES_FRAMEPIPE_CACHE_DIR"] = str(working)
                os.environ["CYCLES_FRAMEPIPE_EXACT_REUSE"] = "1" if args.bvh_input in {"previous", "prepared"} else "0"
                if args.bvh_input == "next":
                    from bvh_producer import capture_next
                    bvh_inputs = partial(capture_next, directory=working)
                scene.render.use_persistent_data = True
                print(f"PIPELINE_BVH exact native layout, input={args.bvh_input}", flush=True)
            run_job(scene, args, frames, working, bvh_inputs)
        except BaseException:
            print(f"PIPELINE_ERROR diagnostic files kept in {working}", flush=True)
            raise
        else:
            shutil.rmtree(working)
        finally:
            if lookahead:
                scene.render.use_persistent_data = saved_persistent
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if not bpy.app.background:
                scene.frame_set(original_frame, subframe=original_sub)


if __name__ == "__main__":
    run()
