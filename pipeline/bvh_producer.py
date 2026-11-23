# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture one future frame's native BVH inputs without opening another blend file."""

import os
from pathlib import Path

import bpy


def capture_next(scene, next_frame, directory):
    if next_frame is None:
        return None

    # The path is private to this render job. The C++ producer publishes it by
    # rename only after add_references() has written the entire ordered input.
    target = Path(directory).resolve() / f"{next_frame}.cfbvh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    values = {"CYCLES_FRAMEPIPE_PRODUCE": str(target),
              "CYCLES_FRAMEPIPE_PRODUCE_FRAME": str(next_frame)}
    previous = {name: os.environ.get(name) for name in values}
    try:
        os.environ.update(values)
        print(f"PIPELINE_BVH_CAPTURE_START {next_frame}", flush=True)
        # The backend creates a separate Render and dependency graph for this
        # original scene ID, seeds it at N, advances it to N+1, then releases it.
        with bpy.context.temp_override(scene=scene):
            bpy.ops.render.render(write_still=False)
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    if target.is_file():
        print(f"PIPELINE_BVH_CAPTURE_DONE {next_frame}", flush=True)
        return target
    print(f"PIPELINE_BVH_CAPTURE_MISS {next_frame}", flush=True)
    return None
