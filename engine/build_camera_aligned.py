# SPDX-License-Identifier: GPL-3.0-or-later
"""Relink the patched Windows backend with the release Cycles camera math options.

Reuse the existing MSVC Release/Ninja build. Only the two POD camera math
operations use the release compiler. All generated libraries, symbols, and
the candidate executable live outside the original build products.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import shutil
import subprocess


SOURCES = {
    "bf_intern_cycles": ("camera.cpp",),
    "cycles_scene": ("camera.cpp",),
}


def cached(cache, key):
    return Path(re.search(rf"^{key}:[^=]+=(.+)$", cache, re.M)[1].strip())


def find_edge(lines, output):
    start = next(i for i, line in enumerate(lines) if line.startswith("build " + output + ": "))
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    return lines[start:end]


def build(work, runtime, output):
    build_dir = work / "build"
    source = work / "blender"
    candidate = output / "backend"
    objects = output / "objects"
    candidate.mkdir(parents=True, exist_ok=True)
    objects.mkdir(parents=True, exist_ok=True)
    cache = (build_dir / "CMakeCache.txt").read_text(encoding="utf8")
    ninja = cached(cache, "CMAKE_MAKE_PROGRAM")
    msvc = cached(cache, "CMAKE_CXX_COMPILER")
    vcvars = next(p / "Auxiliary/Build/vcvars64.bat" for p in msvc.parents
                  if (p / "Auxiliary/Build/vcvars64.bat").is_file())
    setup = subprocess.check_output(f'call "{vcvars}" >NUL && set', shell=True).decode("mbcs")
    env = os.environ | dict(s.split("=", 1) for s in setup.splitlines() if "=" in s and not s.startswith("="))
    clang = work / "windows_lib/dpcpp/bin/clang.exe"
    lines = (build_dir / "build.ninja").read_text(encoding="utf8").splitlines()
    obj_map = {}
    jobs = []
    for target, sources in SOURCES.items():
        for filename in sources:
            name = next(s.split(": ", 1)[0][6:] for s in lines if s.startswith("build intern\\cycles\\")
                        and f"\\{target}.dir\\{filename}.obj: " in s)
            edge = find_edge(lines, name)
            settings = dict(s.strip().split(" = ", 1) for s in edge[1:])
            src = source / "intern/cycles" / name.split("\\")[2] / filename
            obj = objects / (target + "-" + filename + ".obj")
            obj_map[name] = obj
            rsp = obj.with_suffix(".rsp")
            rsp.write_text("\n".join([settings["DEFINES"], settings["INCLUDES"], settings["FLAGS"],
                                      "/DWITH_FRAMEPIPE_RELEASE_CAMERA_MATH", "/c", f'"{src}"',
                                      f'/Fo"{obj}"', f'/Fd"{obj.with_suffix(".pdb")}"']), encoding="utf-8-sig")
            jobs.append([str(msvc), "@" + str(rsp)])

    helper = objects / "framepipe_camera_math.obj"
    helper_rsp = helper.with_suffix(".rsp")
    math_flags = ("/nologo /O2 /MD /J /EHsc /std:c++20 /Zc:__cplusplus /utf-8 /Z7 "
                  "/clang:-march=x86-64-v2 /clang:-fno-strict-aliasing "
                  "/clang:-fno-trapping-math /clang:-fno-math-errno /clang:-fno-signed-zeros "
                  "/clang:-ffp-contract=on /clang:-freciprocal-math")
    helper_source = source / "intern/cycles/util/framepipe_camera_math.cpp"
    helper_rsp.write_text("\n".join([settings["DEFINES"], settings["INCLUDES"], math_flags,
                                     "/c", f'"{helper_source}"', f'/Fo"{helper}"']),
                          encoding="utf-8-sig")
    jobs.append([str(clang), "--driver-mode=cl", "@" + str(helper_rsp)])

    def compile_one(command):
        subprocess.run(command, env=env, cwd=build_dir, check=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(compile_one, jobs))

    # Replace exact object members in their original archives, preserving the
    # source build's library order and entry points, including Python bindings.
    libs = {}
    for target in SOURCES:
        lib = "lib\\" + target + ".lib"
        edge = find_edge(lines, lib)
        inputs = edge[0].split(": ", 1)[1].split(" || ", 1)[0].split()[1:]
        result = objects / (target + ".lib")
        rsp = result.with_suffix(".lib.rsp")
        args = [f'/OUT:"{result}"', "/machine:x64", "/ignore:4221"]
        args += [f'"{obj_map.get(name, build_dir / name)}"' for name in inputs]
        if target == "cycles_scene":
            args.append(f'"{helper}"')
        rsp.write_text("\n".join(args), encoding="utf-16")
        subprocess.run([str(msvc.with_name("lib.exe")), "/nologo", "@" + str(rsp)], env=env, check=True)
        libs[lib] = str(result)

    # Use the native CMake link command and manifest embedding, but redirect all
    # mutable outputs (PDBs, manifest intermediate, import library, response file).
    edge = find_edge(lines, r"bin\blender.exe")
    def rel(path):
        return os.path.relpath(path, build_dir).replace("/", "\\")

    link_dir = objects / "link"
    link_dir.mkdir(exist_ok=True)
    overrides = {
        "OBJECT_DIR": rel(link_dir), "RSP_FILE": rel(link_dir / "blender.rsp"),
        "TARGET_FILE": rel(candidate / "blender.exe"), "TARGET_IMPLIB": rel(link_dir / "blender.lib"),
        "TARGET_PDB": rel(link_dir / "blender-private.pdb"), "POST_BUILD": "cd .",
    }
    def ninja_path(path):
        return path.replace("$", "$$").replace(" ", "$ ").replace(":", "$:")

    def replace_libs(line, ninja):
        for old, new in libs.items():
            path = rel(new)
            line = line.replace(old, ninja_path(path) if ninja else '"' + path + '"')
        return line
    target = rel(candidate / "blender.exe")
    first = edge[0].split(" || ", 1)[0].replace(r"bin\blender.exe:", ninja_path(target) + ":", 1)
    manifest = ["include CMakeFiles/rules.ninja", "", replace_libs(first, True)]
    for s in edge[1:]:
        key, value = s.strip().split(" = ", 1)
        value = overrides.get(key, value)
        if key == "LINK_FLAGS":
            pdb = rel(candidate / "blender.pdb")
            value = re.sub(r"/PDBSTRIPPED:\S+", lambda _: f'/PDBSTRIPPED:"{pdb}"', value)
        if key == "LINK_LIBRARIES":
            value = replace_libs(value, False)
        manifest.append("  " + key + " = " + value)
    manifest_path = objects / "link.ninja"
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="utf8")
    subprocess.run([str(ninja), "-f", str(manifest_path), target], cwd=build_dir, env=env, check=True)

    # A candidate layout shares immutable runtime resources with the matching
    # install. The executable and symbols are regular independent files.
    for item in runtime.iterdir():
        target = candidate / item.name
        if item.name in {"blender.crt", "blender.shared"}:
            # Windows activation contexts require private assembly directories
            # at the executable's own path. Directory junctions fail with 14001.
            if os.path.isjunction(target) and target.resolve() == item.resolve():
                target.rmdir()
            if not target.exists():
                shutil.copytree(item, target, copy_function=os.link)
            continue
        if target.exists() or item.name in {"blender.exe", "blender.pdb"}:
            continue
        if item.is_dir():
            subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(target), str(item)],
                           stdout=subprocess.DEVNULL, check=True)
        else:
            os.link(item, target)
    print(candidate / "blender.exe", flush=True)


if __name__ == "__main__":
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=project / "work")
    parser.add_argument("--runtime", type=Path, default=project / "backend")
    parser.add_argument("--output", type=Path, default=project / "work/camera-pod")
    args = parser.parse_args()
    build(args.work.resolve(), args.runtime.resolve(), args.output.resolve())
