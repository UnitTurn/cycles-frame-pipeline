# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup


_directory = Path(__file__).parent
_catalog = _directory / 'ui.json'
if not _catalog.exists():
    # A source checkout uses the original language. Each release ZIP contains its chosen catalog.
    _catalog = _directory / 'locales' / 'zh-CN.json'
UI = json.loads(_catalog.read_text(encoding='utf-8'))
UI_CONTEXT = 'CyclesFramePipeline'


def _label(key):
    return {'name': UI[key], 'description': UI[key + '.tip'], 'translation_context': UI_CONTEXT}


def _option(identifier, key=None):
    key = key or identifier
    return (identifier, UI[key], UI[key + '.tip'])


class FramePipelinePreferences(AddonPreferences):
    bl_idname = __package__
    backend: StringProperty(**_label('backend'), subtype='FILE_PATH')

    def draw(self, context):
        self.layout.prop(self, 'backend')


class FramePipelineSettings(PropertyGroup):
    source: EnumProperty(**_label('source'), items=[_option('current'), _option('file')])
    scene_file: StringProperty(**_label('scene_file'), subtype='FILE_PATH')
    profile: EnumProperty(**_label('profile'), items=[_option('scene'), _option('ruins-hip256', 'ruins')])
    output: StringProperty(**_label('output'), subtype='DIR_PATH', default=UI['output.default'])
    mode: EnumProperty(**_label('mode'), items=[_option('native'), _option('serial'), _option('compositor')],
                       default='native')
    lookahead: BoolProperty(**_label('lookahead'), default=True)
    bvh_input: EnumProperty(**_label('bvh_input'), items=[_option('auto'), _option('next'),
                            _option('previous'), _option('prepared')], default='auto')
    defer_upload: BoolProperty(**_label('defer_upload'), default=True)
    threads: IntProperty(**_label('threads'), default=6, min=1, max=128)
    existing: EnumProperty(**_label('existing'), items=[_option('error'), _option('skip'), _option('replace')])


_active = None
_last = {}


def _refresh():
    wm = bpy.context.window_manager
    if wm:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()


def _read_log(job, final=False):
    # The renderer may write a line in several chunks. Publish progress only once it is complete.
    with job['log'].open('rb') as stream:
        stream.seek(job['position'])
        data = stream.read()
        job['position'] = stream.tell()
    parts = (job['fragment'] + data).split(b'\n')
    job['fragment'] = parts.pop()
    if final and job['fragment']:
        parts.append(job['fragment'])
        job['fragment'] = b''
    for raw in parts:
        line = raw.decode('utf-8', errors='replace').strip()
        if not line:
            continue
        match = re.fullmatch(r'PIPELINE_FRAME_(START|DONE|SKIP)\s+(-?\d+)', line)
        if match:
            if match[1] == 'START':
                job['frame'] = match[2]
            elif match[1] == 'SKIP':
                job['skipped'] += 1
            else:
                job['done'] += 1
        elif total := re.fullmatch(r'PIPELINE_TOTAL\s+(\d+)', line):
            job['total'] = int(total[1])
        if line == 'PIPELINE_DEFER_UPLOAD_UNSUPPORTED':
            job['error'] = UI['err.defer_backend']
        elif line.startswith('PIPELINE_MODE serial'):
            job['fallback'] = line[:170]
        elif line.startswith(('FRAMEPIPE_EXACT ', 'FRAMEPIPE_BVH ')):
            if 'hit=' in line:
                job['bvh_hits'] += 1
                job.pop('bvh_last_miss', None)
                partial = re.search(r'\bhit=partial\b.*?\brefs=(\d+) total=(\d+) branches=(\d+)', line)
                if partial:
                    job['bvh_partial'] += 1
                    job['bvh_partial_detail'] = tuple(map(int, partial.groups()))
            elif 'miss=' in line:
                job['bvh_last_miss'] = line.partition('miss=')[2].split()[0]


def _poll():
    global _active, _last
    job = _active
    if not job:
        return None
    code = job['proc'].poll()
    try:
        _read_log(job, final=code is not None)
    except OSError:
        pass
    if code is not None:
        if job['snapshot']:
            job['snapshot'].unlink(missing_ok=True)
        if code:
            state = job.get('error') or UI['status.exit'].format(code=code)
        elif job['done'] + job['skipped'] == job['total']:
            state = UI['status.complete'].format(**job)
        elif job['stop'].exists():
            state = UI['status.stop'].format(**job)
        else:
            state = UI['status.incomplete'].format(done=job['done'], total=job['total'] if job['total'] is not None else '…')
        _last = {'state': state, 'log': str(job['log']), 'fallback': job.get('fallback', ''),
                 'lookahead': job['lookahead'], 'bvh_hits': job['bvh_hits'],
                 'bvh_partial': job['bvh_partial'], 'bvh_partial_detail': job.get('bvh_partial_detail'),
                 'bvh_last_miss': job.get('bvh_last_miss', '')}
        _active = None
    _refresh()
    return 0.7 if _active else None


class FRAMEPIPE_OT_start(Operator):
    bl_idname = 'render.frame_pipeline_start'
    bl_translation_context = UI_CONTEXT
    bl_label = UI['start']
    bl_description = UI['start.tip']

    def execute(self, context):
        global _active, _last
        if _active:
            self.report({'ERROR'}, UI['err.active'])
            return {'CANCELLED'}
        scene = context.scene
        cfg = context.window_manager.frame_pipeline
        external = cfg.source == 'file'
        snapshot = None
        try:
            if not external and scene.render.engine != 'CYCLES':
                raise ValueError(UI['err.cycles'])
            if not external and scene.frame_end < scene.frame_start:
                raise ValueError(UI['err.range'])
            exe = Path(bpy.app.binary_path)
            if cfg.lookahead and cfg.bvh_input == 'prepared' and cfg.mode != 'native':
                raise ValueError(UI['err.mode'])
            prepared = cfg.lookahead and cfg.mode == 'native' and cfg.bvh_input in {'auto', 'prepared'}
            defer_upload = prepared and cfg.defer_upload
            backend = context.preferences.addons[__package__].preferences.backend
            auto_prepared = defer_upload and cfg.bvh_input == 'auto'
            if cfg.lookahead and not backend and not auto_prepared:
                import _cycles
                if defer_upload and not getattr(_cycles, 'with_host_bvh_packing', False):
                    raise ValueError(UI['err.defer_backend'])
                if not getattr(_cycles, 'with_exact_bvh', False):
                    raise ValueError(UI['err.backend'])
            if backend and (cfg.lookahead or cfg.mode != 'compositor'):
                exe = Path(bpy.path.abspath(backend))
            if not exe.is_file():
                raise ValueError(UI['err.exe'])
            if not cfg.output.strip():
                raise ValueError(UI['err.output'])
            if external:
                if not cfg.scene_file.strip():
                    raise ValueError(UI['err.input'])
                source_path = Path(bpy.path.abspath(cfg.scene_file)).resolve()
                if not source_path.is_file() or source_path.suffix.lower() != '.blend':
                    raise ValueError(UI['err.file'])
            elif not bpy.data.filepath and cfg.output.startswith('//'):
                raise ValueError(UI['err.unsaved'])
            if external and cfg.output.startswith('//'):
                output = (source_path.parent / cfg.output[2:]).resolve()
            else:
                output = Path(bpy.path.abspath(cfg.output)).resolve()
            run_root = output / '.frame-pipeline'
            run_root.mkdir(parents=True, exist_ok=True)
            run = Path(tempfile.mkdtemp(prefix='job-', dir=run_root))
            log_path = run / 'render.log'
            stop = run / 'stop'
            scene_file = str(source_path) if external else bpy.data.filepath
            if not external and (not scene_file or bpy.data.is_dirty):
                snapshot = run / 'scene.blend'
                result = bpy.ops.wm.save_as_mainfile(filepath=str(snapshot), copy=True, relative_remap=True)
                if 'FINISHED' not in result:
                    raise RuntimeError(UI['err.snapshot'])
                scene_file = str(snapshot)
            entry = Path(__file__).parent / 'pipeline' / 'render.py'
            if not entry.is_file():
                raise RuntimeError(UI['err.entry'])
            args = [str(exe), '-b', scene_file]
            if not external:
                args += ['-S', scene.name]
            args += ['--python-exit-code', '9', '-P', str(entry), '--', '--output', str(output),
                     '--post-threads', str(cfg.threads), '--stop-file', str(stop), '--existing', cfg.existing,
                     '--profile', cfg.profile, '--mode', cfg.mode,
                     '--bvh-input', cfg.bvh_input if cfg.lookahead else 'off']
            if prepared and not defer_upload:
                args.append('--eager-upload')
            if not external:
                args += ['--start', str(scene.frame_start), '--end', str(scene.frame_end), '--step', str(scene.frame_step)]
            environment = os.environ.copy()
            environment['PYTHONIOENCODING'] = 'utf-8'
            environment['CYCLES_BVH_LOOKAHEAD'] = '1' if cfg.lookahead else '0'
            with log_path.open('wb') as log:
                child = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                         env=environment, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, ValueError, RuntimeError) as exc:
            if snapshot:
                snapshot.unlink(missing_ok=True)
            message = UI['err.io'].format(detail=exc) if isinstance(exc, OSError) else str(exc)
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        _active = {'proc': child, 'log': log_path, 'stop': stop, 'snapshot': snapshot,
                   'frame': '', 'done': 0, 'total': None if external else len(range(scene.frame_start, scene.frame_end + 1, scene.frame_step)),
                   'skipped': 0, 'position': 0, 'fragment': b'', 'bvh_hits': 0,
                   'bvh_partial': 0, 'lookahead': cfg.lookahead}
        _last = {}
        if not bpy.app.timers.is_registered(_poll):
            bpy.app.timers.register(_poll, first_interval=0.3, persistent=True)
        return {'FINISHED'}


class FRAMEPIPE_OT_stop(Operator):
    bl_idname = 'render.frame_pipeline_stop'
    bl_translation_context = UI_CONTEXT
    bl_label = UI['stop']
    bl_description = UI['stop.tip']

    def execute(self, context):
        if _active:
            try:
                _active['stop'].touch()
            except OSError as exc:
                self.report({'ERROR'}, UI['err.io'].format(detail=exc))
                return {'CANCELLED'}
        return {'FINISHED'}


class FRAMEPIPE_OT_log(Operator):
    bl_idname = 'render.frame_pipeline_log'
    bl_translation_context = UI_CONTEXT
    bl_label = UI['log']
    bl_description = UI['log.tip']

    def execute(self, context):
        job = _active or _last
        if not job or not job.get('log'):
            return {'CANCELLED'}
        return bpy.ops.wm.path_open(filepath=str(job['log']))


class FRAMEPIPE_PT_render(Panel):
    bl_translation_context = UI_CONTEXT
    bl_label = UI['manifest.name']
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'render'

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def draw(self, context):
        ui = self.layout
        cfg = context.window_manager.frame_pipeline
        group = ui.column()
        group.enabled = _active is None
        group.prop(cfg, 'source')
        if cfg.source == 'file':
            group.prop(cfg, 'scene_file')
        group.prop(cfg, 'output')
        group.prop(cfg, 'profile')
        group.prop(cfg, 'mode')
        group.prop(cfg, 'threads')
        group.prop(cfg, 'existing')
        group.prop(cfg, 'lookahead')
        if cfg.lookahead:
            group.prop(cfg, 'bvh_input')
            if cfg.mode == 'native' and cfg.bvh_input in {'auto', 'prepared'}:
                group.prop(cfg, 'defer_upload')
        if cfg.lookahead or cfg.mode != 'compositor':
            group.prop(context.preferences.addons[__package__].preferences, 'backend')
        group.operator(FRAMEPIPE_OT_start.bl_idname, icon='RENDER_ANIMATION')
        if _active:
            job = _active
            status = UI['status.active'].format(done=job['done'], total=job['total'] if job['total'] is not None else '…')
            if job['frame']:
                status += ' · ' + UI['status.frame'].format(frame=job['frame'])
            ui.label(text=status, translate=False)
            row = ui.row()
            row.enabled = not job['stop'].exists()
            row.operator(FRAMEPIPE_OT_stop.bl_idname, icon='CANCEL')
        elif _last:
            ui.label(text=_last['state'], translate=False)
        if _active or _last:
            job = _active or _last
            if job.get('lookahead'):
                msg = UI['status.bvh'].format(whole=job['bvh_hits'] - job['bvh_partial'], partial=job['bvh_partial'])
                if job.get('bvh_last_miss'):
                    msg += ' · ' + UI['status.miss'].format(reason=UI.get('miss.' + job['bvh_last_miss'], job['bvh_last_miss']))
                ui.label(text=msg, translate=False)
                if job.get('bvh_partial_detail'):
                    refs, total, branches = job['bvh_partial_detail']
                    ui.label(text=UI['status.refs'].format(branches=branches, refs=refs, total=total), translate=False)
            if job.get('fallback'):
                ui.label(text=UI['status.fallback'], icon='INFO', translate=False)
            ui.operator(FRAMEPIPE_OT_log.bl_idname, icon='TEXT')


_classes = (FramePipelinePreferences, FramePipelineSettings, FRAMEPIPE_OT_start, FRAMEPIPE_OT_stop,
            FRAMEPIPE_OT_log, FRAMEPIPE_PT_render)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.frame_pipeline = PointerProperty(type=FramePipelineSettings)


def unregister():
    if _active:
        _active['stop'].touch()
    del bpy.types.WindowManager.frame_pipeline
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
