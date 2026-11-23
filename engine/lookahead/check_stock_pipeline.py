"""Compare stock synchronous PNGs against the native two-stage HIP pipeline on the same scene."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def make_scene(path, all_samples, prepared=False):
    import bpy
    from mathutils import Vector
    sys.path.insert(0, str(HERE))
    from check_render import make_base_scene

    scene, _ = make_base_scene("HIP", "7800 XT", 0, True)
    scene.frame_start, scene.frame_end = 1, 3
    scene.render.resolution_x, scene.render.resolution_y = 144, 96
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.motion_blur_shutter = .09
    scene.view_settings.view_transform = 'AgX'
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.denoising_use_gpu = False
    scene.cycles.sampling_pattern = 'TABULATED_SOBOL'
    scene.cycles.seed = 0
    if not all_samples:
        # Use one fixed path per pixel for a strict deterministic regression while
        # preserving the 256-sample Sobol sequence and the production OIDN path.
        scene.cycles.use_sample_subset = True
        scene.cycles.sample_offset, scene.cycles.sample_subset_length = 2, 1
    camera = scene.camera
    camera.data.type = 'PERSP'
    camera.data.lens = 22
    camera.data.clip_start, camera.data.clip_end = .1, 1000
    camera.scale = (1.000000119, .99999994, 1)
    for frame, x in [(1, -.21), (2, -.06), (3, .13)]:
        camera.location = (x, -3.65, 1.78)
        camera.rotation_euler = (Vector((0, 0, .72)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)

    world = bpy.data.worlds.new("Daylight")
    scene.world = world
    world.use_nodes = True
    sky = world.node_tree.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'SINGLE_SCATTERING'
    sky.sun_elevation, sky.sun_rotation, sky.sun_size = .4, 2.2, .06
    background = world.node_tree.nodes.get('Background')
    background.inputs['Strength'].default_value = .14
    world.node_tree.links.new(sky.outputs['Color'], background.inputs['Color'])
    if prepared:
        # A moving camera changes this environment shader's importance distribution.
        # A persistent official session keeps the first map until the World changes.
        nodes, links = world.node_tree.nodes, world.node_tree.links
        coords = nodes.new('ShaderNodeTexCoord')
        separate = nodes.new('ShaderNodeSeparateXYZ')
        threshold = nodes.new('ShaderNodeMath')
        threshold.operation = 'GREATER_THAN'
        threshold.inputs[1].default_value = .15
        mix = nodes.new('ShaderNodeMixRGB')
        mix.inputs[1].default_value = (.015, .025, .05, 1)
        links.new(coords.outputs['Camera'], separate.inputs['Vector'])
        links.new(separate.outputs['X'], threshold.inputs[0])
        links.new(threshold.outputs[0], mix.inputs[0])
        links.new(sky.outputs['Color'], mix.inputs[2])
        links.new(mix.outputs[0], background.inputs['Color'])
        world.cycles.sampling_method = 'MANUAL'
        world.cycles.sample_map_resolution = 128
    metal = bpy.data.materials.new("Brushed metal")
    metal.use_nodes = True
    shader = metal.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.62, .48, .31, 1)
    shader.inputs['Roughness'].default_value = .13
    shader.inputs['Metallic'].default_value = 1
    def mesh_object(name, vertices, faces):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        mesh.materials.append(metal)
        return obj
    panel = mesh_object('Flexing reflector', [(-2.3, -1, 0), (2.3, -1, 0),
                                             (2.3, 1.9, .35), (-2.3, 1.9, .35)], [(0,1,2,3)])
    panel.shape_key_add(name='Basis')
    bend = panel.shape_key_add(name='Bend')
    bend.data[2].co.z += .35
    for frame, value in [(1, 0.0), (2, .65), (3, .2)]:
        bend.value = value
        bend.keyframe_insert(data_path='value', frame=frame)
    points = [((x-6)*.21, (y-1)*.23, .33+y*.23+.02*(x%3)) for y in range(4) for x in range(13)]
    rail = mesh_object('Reflective points', points, [])
    group = bpy.data.node_groups.new('Points from fixed vertices', 'GeometryNodeTree')
    group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    src = group.nodes.new('NodeGroupInput')
    convert = group.nodes.new('GeometryNodeMeshToPoints')
    convert.inputs['Radius'].default_value = .109
    assign = group.nodes.new('GeometryNodeSetMaterial')
    assign.inputs['Material'].default_value = metal
    target = group.nodes.new('NodeGroupOutput')
    group.links.new(src.outputs['Geometry'], convert.inputs['Mesh'])
    group.links.new(convert.outputs['Points'], assign.inputs['Geometry'])
    group.links.new(assign.outputs['Geometry'], target.inputs['Geometry'])
    rail.modifiers.new('Point cloud', 'NODES').node_group = group
    light = bpy.data.lights.new('Strip light', 'AREA')
    light.shape, light.size, light.size_y, light.energy = 'RECTANGLE', 2.8, .085, 480
    lamp = bpy.data.objects.new('Strip light', light)
    scene.collection.objects.link(lamp)
    lamp.location = (-.6, .75, 2.9)
    lamp.rotation_euler = (Vector((0, 0, .7)) - lamp.location).to_track_quat('-Z', 'Y').to_euler()
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def run(official, backend, output, all_samples, fixture, prepared=False):
    import numpy as np
    from PIL import Image
    output.mkdir(parents=True, exist_ok=False)
    env = {k:v for k,v in os.environ.items() if not k.startswith('CYCLES_FRAMEPIPE_') and k!='CYCLES_BVH_LOOKAHEAD'}
    def blender(label, executable, *args):
        log = output / (label+'.log')
        with log.open('wb') as file:
            p = subprocess.run([str(executable), '-b', *map(str,args)], env=env, stdout=file, stderr=subprocess.STDOUT)
        if p.returncode:
            raise RuntimeError(f"{label} failed ({p.returncode}), see {log}")
        return log.read_text(encoding='utf8', errors='replace')
    if fixture:
        scene = fixture.resolve(strict=True)
    else:
        scene = output / 'reflectors.blend'
        blender('create', official, '--factory-startup', '--python-exit-code', '9', '-P', __file__, '--',
                scene, *(['--all-samples'] if all_samples else []), *(['--prepared'] if prepared else []))
    entry = HERE.parents[1] / 'pipeline/render.py'
    candidate_bvh = 'prepared' if prepared else 'next'
    for label, exe, mode, bvh in [('official',official,'serial','off'), ('candidate',backend,'native',candidate_bvh)]:
        report = blender(label, exe, scene, '-t', 4, '--python-exit-code', 9, '-P', entry, '--',
                         '--profile', 'ruins-hip256', '--post-threads', 4, '--output', output/label,
                         '--mode', mode, '--bvh-input', bvh, '--fallback', 'error')
        if label == 'candidate':
            assert 'PIPELINE_MODE async native' in report, report
            if prepared:
                for frame in range(1, 4):
                    for stage in ('scene_eval', 'bvh_packed', 'prepared', 'sample_begin'):
                        assert report.count(f'READYFRAME frame={frame} event={stage} ') == 1, report
            else:
                assert report.count('FRAMEPIPE_EXACT hit=native ') == 2, report
        assert report.count('PIPELINE_FRAME_DONE ') == 3, report
    results = {}
    for frame in range(1, 4):
        filename = f'{frame:04d}.png'
        with Image.open(output/'official'/filename) as a, Image.open(output/'candidate'/filename) as b:
            assert a.size == b.size == (144, 96) and a.mode == b.mode == 'RGBA'
            diff = np.abs(np.array(a, dtype=np.int16) - np.array(b, dtype=np.int16))
        results[filename] = {'different_pixels':int(np.any(diff!=0,axis=2).sum()),
                             'max_channel_delta':int(diff.max()), 'mean_channel_delta':float(diff.mean())}
    output.joinpath('comparison.json').write_text(json.dumps(results,indent=2), encoding='utf8')
    print(json.dumps(results,indent=2))
    if any(v['different_pixels'] for v in results.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    if '--' in sys.argv:
        make_scene(Path(sys.argv[sys.argv.index('--')+1]).resolve(), '--all-samples' in sys.argv,
                   '--prepared' in sys.argv)
    else:
        p = argparse.ArgumentParser(description=__doc__)
        for name in ('official','backend','output'):
            p.add_argument(name, type=Path)
        source = p.add_mutually_exclusive_group()
        source.add_argument('--all-samples', action='store_true', help='stress run using the full 256-sample adaptive job')
        source.add_argument('--scene', type=Path, help='use reflectors.blend saved by an earlier run')
        p.add_argument('--prepared', action='store_true',
                       help='check formal frame handoff with a camera-dependent World shader')
        opt = p.parse_args()
        run(opt.official.resolve(), opt.backend.resolve(), opt.output.resolve(), opt.all_samples,
            opt.scene, opt.prepared)
