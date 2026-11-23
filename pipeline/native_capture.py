# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture the actual Cycles film buffer, including adaptive sample counts."""

import bpy
import _cycles

from frame_snapshot_paths import set_bvh_frame


def submit_prepared(scene, path, frame, next_frame):
    if path.exists():
        raise FileExistsError(path)
    set_bvh_frame(frame, next_frame)
    use_compositing = scene.render.use_compositing
    try:
        scene.render.use_compositing = False
        _cycles.formal_begin(frame, str(path))
        result = bpy.ops.render.render(write_still=False, scene=scene.name)
        if "FINISHED" not in result:
            raise RuntimeError(f"Cycles cancelled prepared frame {frame}")
    finally:
        scene.render.use_compositing = use_compositing


def collect_prepared(directory, frame):
    _cycles.formal_collect(frame)
    if not (directory / f"{frame}.cycles.exr").is_file():
        raise RuntimeError(f"Cycles did not publish the raw film for prepared frame {frame}")


def capture(scene, path, frame, next_frame):
    if path.exists():
        raise FileExistsError(path)
    set_bvh_frame(frame, next_frame)
    use_compositing = scene.render.use_compositing
    try:
        # The standalone consumer executes the original compatible compositor after denoising.
        scene.render.use_compositing = False
        _cycles.native_frame_paths(str(path), "")
        result = bpy.ops.render.render(write_still=False, scene=scene.name)
        if 'FINISHED' not in result or not _cycles.native_frame_done() or not path.is_file():
            raise RuntimeError(f"Cycles failed to capture the complete raw buffer for frame {frame}")
    finally:
        _cycles.native_frame_paths("", "")
        scene.render.use_compositing = use_compositing
