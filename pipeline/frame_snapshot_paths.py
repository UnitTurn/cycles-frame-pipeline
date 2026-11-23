"""Frame-local handoff from the Blender render worker to the custom Cycles build."""

import os
from pathlib import Path


def set_bvh_frame(frame: int, next_frame: int | None) -> None:
    """Set immediately before the main render. Use a separate cache directory per job."""
    cache = os.environ.get("CYCLES_FRAMEPIPE_CACHE_DIR")
    os.environ["CYCLES_FRAMEPIPE_LAST"] = "1" if next_frame is None else "0"
    if not cache:
        os.environ.pop("CYCLES_FRAMEPIPE_CAPTURE", None)
        os.environ.pop("CYCLES_FRAMEPIPE_NEXT", None)
        return

    directory = Path(cache).expanduser().resolve()
    if os.environ.get("CYCLES_FRAMEPIPE_EXACT") == "1":
        os.environ.pop("CYCLES_FRAMEPIPE_CAPTURE", None)
        if next_frame is None:
            os.environ.pop("CYCLES_FRAMEPIPE_NEXT", None)
        else:
            os.environ["CYCLES_FRAMEPIPE_NEXT"] = str(directory / f"{next_frame}.cfbvh")
        return
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Caching is optional. Keep the renderer's verified in-memory/refit path usable.
        print(f"BVH cache unavailable at {directory}: {exc}", flush=True)
        os.environ.pop("CYCLES_FRAMEPIPE_CAPTURE", None)
        os.environ.pop("CYCLES_FRAMEPIPE_NEXT", None)
        return
    os.environ["CYCLES_FRAMEPIPE_CAPTURE"] = str(directory / f"{frame}.cfbvh")
    if next_frame is None:
        os.environ.pop("CYCLES_FRAMEPIPE_NEXT", None)
    else:
        os.environ["CYCLES_FRAMEPIPE_NEXT"] = str(directory / f"{next_frame}.cfbvh")
