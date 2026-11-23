# SPDX-License-Identifier: GPL-3.0-or-later
"""Install and exercise each language edition in a clean Blender user profile."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace


def inspect_ui(locale):
    import bpy
    from bl_ext.user_default import cycles_frame_pipeline as addon
    from unittest.mock import patch

    catalog = addon.UI
    assert catalog['start'] == {'en': 'Start Pipeline Render', 'zh-CN': '启动流水线渲染'}[locale]
    context = bpy.context
    prefs = context.preferences.addons[addon.__package__].preferences
    cfg = context.window_manager.frame_pipeline
    assert (cfg.source, cfg.mode, cfg.bvh_input, cfg.existing) == ('current', 'native', 'auto', 'error')
    assert cfg.lookahead and cfg.defer_upload
    assert catalog['defer_upload'] == {'en': 'Host BVH Prepacking', 'zh-CN': '主机端 BVH 预打包'}[locale]
    assert prefs.bl_rna.properties['backend'].name == catalog['backend']
    assert addon.FRAMEPIPE_PT_render.bl_label == catalog['manifest.name']
    for name, cls in [('start', addon.FRAMEPIPE_OT_start), ('stop', addon.FRAMEPIPE_OT_stop), ('log', addon.FRAMEPIPE_OT_log)]:
        assert cls.bl_label == catalog[name] and cls.bl_description == catalog[name + '.tip']

    class Layout:
        def __init__(self):
            self.labels, self.props, self.operators = [], [], []
        def row(self): return self
        def column(self): return self
        def label(self, text, **kwargs): self.labels.append(text)
        def operator(self, identifier, **kwargs): self.operators.append(identifier)
        def prop(self, data, name):
            prop = data.bl_rna.properties[name]
            assert (prop.name, prop.description) == (catalog[name], catalog[name + '.tip'])
            if prop.type == 'ENUM':
                for item in prop.enum_items:
                    key = 'ruins' if item.identifier == 'ruins-hip256' else item.identifier
                    assert (item.name, item.description) == (catalog[key], catalog[key + '.tip'])
            self.props.append(name)

    cfg.source = 'file'
    layout = Layout()
    addon.FramePipelinePreferences.draw(SimpleNamespace(layout=layout, bl_rna=prefs.bl_rna), context)
    addon.FRAMEPIPE_PT_render.draw(SimpleNamespace(layout=layout), context)
    assert set(layout.props) == {'source','scene_file','output','profile','mode','threads','existing','lookahead','bvh_input','defer_upload','backend'}
    assert layout.operators == ['render.frame_pipeline_start']
    cfg.bvh_input, cfg.defer_upload = 'previous', True
    inactive = Layout()
    addon.FRAMEPIPE_PT_render.draw(SimpleNamespace(layout=inactive), context)
    assert 'defer_upload' not in inactive.props
    cfg.bvh_input = 'prepared'
    try:
        cfg.mode = 'serial'
        bpy.ops.render.frame_pipeline_start()
    except RuntimeError as err:
        assert catalog['err.mode'] in str(err), str(err)
    else:
        raise AssertionError('Expected incompatible mode to produce a localized error')

    with TemporaryDirectory() as tmp:
        cfg.mode, cfg.source = 'native', 'file'
        fixture = Path(tmp) / 'scene.blend'
        fixture.touch()
        cfg.scene_file, cfg.output = str(fixture), tmp
        prefs.backend = bpy.app.binary_path
        for checkbox, strategy in ((True, 'auto'), (False, 'auto'), (False, 'prepared'),
                                   (True, 'prepared'), (True, 'previous')):
            cfg.defer_upload, cfg.bvh_input = checkbox, strategy
            with patch.object(addon.subprocess, 'Popen', return_value=SimpleNamespace(poll=lambda: 0)) as launch:
                assert bpy.ops.render.frame_pipeline_start() == {'FINISHED'}
                command = launch.call_args.args[0]
                assert command[command.index('--bvh-input') + 1] == strategy
                assert ('--eager-upload' in command) == (not checkbox and strategy in {'auto', 'prepared'})
                addon._poll()
        log, stop = Path(tmp)/'render.log', Path(tmp)/'stop'
        log.write_bytes(b'')
        addon._active = {'done': 1, 'skipped': 0, 'total': 2, 'frame': '2', 'lookahead': True,
                         'bvh_hits': 2, 'bvh_partial': 1, 'bvh_last_miss': 'cold', 'bvh_partial_detail': (5, 7, 1),
                         'stop': stop, 'log': log, 'position': 0, 'fragment': b'', 'snapshot': None,
                         'fallback': 'serial', 'proc': SimpleNamespace(poll=lambda: 0)}
        layout = Layout()
        addon.FRAMEPIPE_PT_render.draw(SimpleNamespace(layout=layout), context)
        assert catalog['status.active'].format(done=1,total=2) in layout.labels[0]
        assert catalog['status.frame'].format(frame='2') in layout.labels[0]
        assert any(catalog['miss.cold'] in text for text in layout.labels)
        assert catalog['status.refs'].format(branches=1,refs=5,total=7) in layout.labels
        assert catalog['status.fallback'] in layout.labels
        assert {'render.frame_pipeline_stop', 'render.frame_pipeline_log'} <= set(layout.operators)
        stop.touch()
        addon._poll()
        layout = Layout()
        addon.FRAMEPIPE_PT_render.draw(SimpleNamespace(layout=layout), context)
        assert catalog['status.stop'].format(done=1) in layout.labels
    print(f'{locale}: installed, registered and drew localized preferences, scene options, errors, job status and operators.')


def run(executable, package_dir=None):
    import tomllib
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((root/'extension/blender_manifest.toml').read_text(encoding='utf8'))
    with TemporaryDirectory() as tmp:
        for locale in ('en','zh-CN'):
            profile = Path(tmp)/locale
            profile.mkdir()
            env = dict(os.environ, BLENDER_USER_RESOURCES=str(profile),
                       BLENDER_USER_CONFIG=str(profile/'config'), BLENDER_USER_SCRIPTS=str(profile/'scripts'),
                       BLENDER_USER_EXTENSIONS=str(profile/'extensions'), PYTHONIOENCODING='utf-8')
            package = (package_dir or root/'dist')/f"{manifest['id']}-{manifest['version']}-{locale}.zip"
            subprocess.run([executable, '-b', '--factory-startup', '--command', 'extension', 'install-file',
                            '--repo', 'user_default', '--enable', package], check=True, env=env)
            subprocess.run([executable, '-b', '--python-exit-code', '1', '-P', Path(__file__).resolve(),
                            '--', locale], check=True, env=env)


if __name__ == '__main__':
    if '--' in sys.argv:
        inspect_ui(sys.argv[sys.argv.index('--')+1])
    else:
        run(Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None)
