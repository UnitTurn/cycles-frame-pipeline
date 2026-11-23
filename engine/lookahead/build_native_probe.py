"""Build the isolated BVH probe from the configured Windows/MSVC/Ninja checkout."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess


def write_rsp(path, arguments):
    path.write_text("\n".join(arguments) + "\n", encoding="utf-16")


def scene_accessors(cycles, output):
    # The BVH translation units also reference scene methods for spatial/motion/curve modes.
    # Link their *original definitions*, without registering scene nodes or initializing Blender.
    # This probe supplies ordered references at the input of the top-level builder.
    methods = {
        "scene/hair.cpp": r"(?:hair_step_buffers|Hair::Curve::)",
        "scene/pointcloud.cpp": r"PointCloud::Point::",
        "scene/mesh.cpp": r"Mesh::Triangle::",
        "graph/node_type.cpp": r"NodeType::find_input",
        "scene/geometry.cpp": r"Geometry::(?:get_position\(\) const|get_radius\(\) const|is_instanced\()",
        "scene/attribute.cpp": r"AttributeSet::find\(AttributeStandard",
        "scene/object.cpp": r"Object::(?:is_traceable|visibility_for_tracing)\(",
    }
    includes = ("bvh/bvh.h", "scene/attribute.h", "scene/curves.h", "scene/hair.h",
                "scene/mesh.h", "scene/object.h", "scene/pointcloud.h", "graph/node_type.h",
                "kernel/types.h")
    parts = [f'#include "{path}"' for path in includes] + ["CCL_NAMESPACE_BEGIN"]
    for filename, expr in methods.items():
        data = (cycles / filename).read_text(encoding="utf-8")
        # At this pinned revision the member definitions close with an unindented brace.
        signatures = list(re.finditer(r"^[A-Za-z_][\w *&]*" + expr + r".*$", data, re.MULTILINE))
        if not signatures:
            raise RuntimeError(f"Unexpected source layout in {filename}")
        for match in signatures:
            end = data.index("\n}", match.end())
            parts.append(data[match.start():end + 2])
    output.write_text("\n\n".join(parts + ["CCL_NAMESPACE_END"]), encoding="utf-8")


def compiler_settings(build):
    ninja = (build / "build.ninja").read_text(encoding="utf-8")
    start = ninja.index(r"build intern\cycles\bvh\CMakeFiles\cycles_bvh.dir\frame_lookahead.cpp.obj:")
    block = ninja[start:ninja.index("\n\n", start)]
    flags = dict(line.strip().split(" = ", 1) for line in block.splitlines()[1:] if " = " in line)
    return [flags[name] for name in ("DEFINES", "FLAGS", "INCLUDES")]


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=root / "work/blender")
    parser.add_argument("--build", type=Path, default=root / "work/build")
    parser.add_argument("--libs", type=Path, default=root / "work/windows_lib")
    parser.add_argument("--out", type=Path, default=root / "work/native-probe")
    args = parser.parse_args()
    if os.name != "nt" or not shutil.which("cl.exe"):
        parser.error("Run from an x64 Visual Studio Developer Command Prompt.")
    cycles = args.source.resolve() / "intern/cycles"
    out, libs, build = args.out.resolve(), args.libs.resolve(), args.build.resolve()
    out.mkdir(parents=True, exist_ok=True)
    accessors = out / "upstream_accessors.cpp"
    scene_accessors(cycles, accessors)
    files = [cycles / "bvh" / f"{n}.cpp" for n in
             ("frame_lookahead", "build", "node", "binning", "sort", "split", "unaligned")]
    files += [cycles / "util" / f"{n}.cpp" for n in
              ("time", "log", "thread", "task", "string", "guarded_allocator", "aligned_malloc")]
    files += [cycles / "scene/curves.cpp", accessors, Path(__file__).with_name("check_native_bvh.cpp")]
    guarded = build / "lib/bf_intern_guardedalloc.lib"
    if not guarded.is_file():
        parser.error(f"Build bf_intern_guardedalloc in the main checkout first: {guarded}")
    options = compiler_settings(build)
    options += ["/Gy /Gw /Z7 /FS /MP3 /c", *(f'"{file}"' for file in files)]
    write_rsp(out / "compile.rsp", options)
    subprocess.run(["cl.exe", "@compile.rsp"], cwd=out, check=True)
    libraries = [guarded, libs / "OpenImageIO/lib/OpenImageIO_Util.lib", libs / "tbb/lib/tbb12.lib",
                 libs / "tbb/lib/tbbmalloc.lib", libs / "pthreads/lib/pthreadVC3.lib"]
    write_rsp(out / "probe-link.rsp", ["/nologo /OUT:bvh_probe.exe /OPT:REF /OPT:ICF /INCREMENTAL:NO",
              *(f'"{file.stem}.obj"' for file in files), *(f'"{lib}"' for lib in libraries),
              "User32.lib Advapi32.lib Kernel32.lib Ws2_32.lib"])
    subprocess.run(["link.exe", "@probe-link.rsp"], cwd=out, check=True)
    print(out / "bvh_probe.exe")


if __name__ == "__main__":
    main()
