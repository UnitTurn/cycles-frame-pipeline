"""Check that a camera-only frame can prepare a subsequent changed TLAS on HIP."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def save_scene(path):
    import bpy
    sys.path.insert(0, str(HERE))
    from check_render import make_base_scene

    scene, material = make_base_scene('HIP', '7800 XT', 0, False)
    scene.frame_start, scene.frame_end = 1, 3
    for name, x in [('Static', 0.0), ('Appears on three', 1.4)]:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(x-.5, -1, 0), (x+.5, -1, 0), (x, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new(name, mesh)
        mesh.materials.append(material)
        scene.collection.objects.link(obj)
        if x:
            for frame, hidden in [(1, True), (3, False)]:
                obj.hide_render = hidden
                obj.keyframe_insert(data_path='hide_render', frame=frame)
    for frame, x in [(1, 0.0), (3, .15)]:
        scene.camera.location.x = x
        scene.camera.keyframe_insert(data_path='location', frame=frame)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def compare_frames(root):
    from array import array
    import bpy

    for frame in range(1, 4):
        results = []
        for mode in ('off', 'next'):
            image = bpy.data.images.load(str(root / mode / f'{frame:04d}.png'), check_existing=False)
            pixels = array('f', [0.0]) * len(image.pixels)
            image.pixels.foreach_get(pixels)
            results.append(pixels)
            bpy.data.images.remove(image)
        assert results[0] == results[1], f'Frame {frame} changed'


def check(executable):
    executable = str(Path(executable).resolve())
    env = {k: v for k, v in os.environ.items()
           if k != 'CYCLES_BVH_LOOKAHEAD' and not k.startswith('CYCLES_FRAMEPIPE_')}
    def blender(*args):
        return subprocess.run([executable, '-b', *args], check=True, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding='utf8', errors='replace').stdout

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        scene = root / 'gap.blend'
        script = str(Path(__file__).resolve())
        blender('--factory-startup', '--python-exit-code', '1', '-P', script, '--', 'save', str(scene))
        entry = str(HERE.parents[1] / 'pipeline/render.py')
        for mode in ('off', 'next'):
            report = blender(str(scene), '--python-exit-code', '1', '-P', entry, '--', '--output',
                             str(root / mode), '--profile', 'ruins-hip256', '--mode', 'serial',
                             '--bvh-input', mode)
            if mode == 'next':
                second, third = report.split('PIPELINE_FRAME_START 2', 1)[-1].split('PIPELINE_FRAME_START 3', 1)
                assert 'FRAMEPIPE_EXACT discarded=unused-target' in second, report
                assert 'FRAMEPIPE_EXACT launched source=next-frame' in second, report
                assert 'FRAMEPIPE_EXACT hit=native refs=2 ' in third, report
        blender('--factory-startup', '--python-exit-code', '1', '-P', script, '--', 'compare', str(root))
        print('Frame 2 kept its current TLAS and prepared frame 3. All three decoded PNGs match.')


if __name__ == '__main__':
    if '--' in sys.argv:
        action, path = sys.argv[sys.argv.index('--')+1:]
        (save_scene if action == 'save' else compare_frames)(Path(path))
    else:
        check(sys.argv[1])
