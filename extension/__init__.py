# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import os
import re
import subprocess
import tempfile

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup


class FramePipelinePreferences(AddonPreferences):
    bl_idname = __package__
    backend: StringProperty(name="定制 Blender 程序", subtype='FILE_PATH')

    def draw(self, context):
        self.layout.prop(self, "backend")


class FramePipelineSettings(PropertyGroup):
    source: EnumProperty(name="场景来源", items=[
        ('current', '当前场景', ''),
        ('file', '从磁盘选择 .blend', '可从空场景启动，减少前台 Blender 的内存占用'),
    ])
    scene_file: StringProperty(name="场景文件", subtype='FILE_PATH')
    profile: EnumProperty(name="渲染设置", items=[
        ('scene', '使用场景设置', ''),
        ('ruins-hip256', 'Ruins 最终渲染 · RX 7800 XT', 'HIP、256 采样、自适应阈值 0.01、CPU OIDN、持久化数据'),
    ])
    output: StringProperty(name="PNG 输出目录", subtype='DIR_PATH', default="//流水线输出/")
    mode: EnumProperty(name="帧尾处理", items=[
        ('native', 'Cycles 原生降噪与输出', '配套引擎可与下一帧并行；官方 Blender 串行输出'),
        ('serial', 'Cycles 原生同步输出', '可独立验证提前建树，并与相同引擎同步出图对照'),
        ('compositor', '合成器降噪（旧版）', '使用独立合成器降噪，成片可能与原作业有差异'),
    ], default='native')
    lookahead: BoolProperty(name="优化原版 BVH（配套引擎）", default=False)
    bvh_input: EnumProperty(name="BVH 输入", items=[
        ('auto', '按渲染预设选择', 'Ruins 优先复用上一帧原版树，其他场景提前求值下一帧'),
        ('next', '提前求值下一帧', 'GPU 采样当前帧期间构建下一帧的原版树'),
        ('previous', '复用上一帧相同的子树', '每帧只求值一次，变化的区域按原版构建'),
        ('prepared', '并行准备下一正式帧', 'GPU 采样时求值下一帧，完成原生 BVH 校验和打包'),
    ], default='auto')
    threads: IntProperty(name="降噪线程数", default=6, min=1, max=128)
    existing: EnumProperty(name="已有 PNG", items=[
        ('error', '遇到已有帧时退出', ''),
        ('skip', '跳过已有帧', ''),
        ('replace', '覆盖已有帧', ''),
    ])


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
        if line.startswith('PIPELINE_MODE serial'):
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
            state = f"任务退出（{code}），请查看日志"
        elif job['done'] + job['skipped'] == job['total']:
            state = f"已输出 {job['done']} 帧，跳过 {job['skipped']} 帧"
        elif job['stop'].exists():
            state = f"已停止，完成 {job['done']} 帧"
        else:
            state = f"进程已退出，仅确认 {job['done']} / {job['total']} 帧"
        _last = {'state': state, 'log': str(job['log']), 'fallback': job.get('fallback', ''),
                 'lookahead': job['lookahead'], 'bvh_hits': job['bvh_hits'],
                 'bvh_partial': job['bvh_partial'], 'bvh_partial_detail': job.get('bvh_partial_detail'),
                 'bvh_last_miss': job.get('bvh_last_miss', '')}
        _active = None
    _refresh()
    return 0.7 if _active else None


class FRAMEPIPE_OT_start(Operator):
    bl_idname = 'render.frame_pipeline_start'
    bl_label = '启动流水线渲染'
    bl_description = '后台渲染场景帧范围，并在 PNG 写好之后报告该帧完成'

    def execute(self, context):
        global _active, _last
        if _active:
            self.report({'ERROR'}, '已有流水线任务在运行')
            return {'CANCELLED'}
        scene = context.scene
        cfg = context.window_manager.frame_pipeline
        external = cfg.source == 'file'
        snapshot = None
        try:
            if not external and scene.render.engine != 'CYCLES':
                raise ValueError('请先将场景渲染引擎设为 Cycles')
            if not external and scene.frame_end < scene.frame_start:
                raise ValueError('结束帧早于起始帧')
            exe = Path(bpy.app.binary_path)
            if cfg.lookahead and cfg.bvh_input == 'prepared' and cfg.mode != 'native':
                raise ValueError('并行准备正式帧需要选择“Cycles 原生降噪与输出”')
            backend = context.preferences.addons[__package__].preferences.backend
            if cfg.lookahead and not backend:
                import _cycles
                if not getattr(_cycles, 'with_exact_bvh', False):
                    raise ValueError('请先在插件偏好设置中选择配套的 Blender 程序')
            if backend and (cfg.lookahead or cfg.mode != 'compositor'):
                exe = Path(bpy.path.abspath(backend))
            if not exe.is_file():
                raise ValueError('找不到选定的 Blender 可执行文件')
            if not cfg.output.strip():
                raise ValueError('请选择 PNG 输出目录')
            if external:
                if not cfg.scene_file.strip():
                    raise ValueError('请选择需要渲染的 .blend 文件')
                source_path = Path(bpy.path.abspath(cfg.scene_file)).resolve()
                if not source_path.is_file() or source_path.suffix.lower() != '.blend':
                    raise ValueError('找不到选定的 .blend 文件')
            elif not bpy.data.filepath and cfg.output.startswith('//'):
                raise ValueError('未保存的场景需要选择绝对输出目录')
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
                    raise RuntimeError('无法为当前更改创建渲染副本')
                scene_file = str(snapshot)
            entry = Path(__file__).parent / 'pipeline' / 'render.py'
            if not entry.is_file():
                raise RuntimeError('安装包缺少流水线入口，请使用完整插件 ZIP')
            args = [str(exe), '-b', scene_file]
            if not external:
                args += ['-S', scene.name]
            args += ['--python-exit-code', '9', '-P', str(entry), '--', '--output', str(output),
                     '--post-threads', str(cfg.threads), '--stop-file', str(stop), '--existing', cfg.existing,
                     '--profile', cfg.profile, '--mode', cfg.mode,
                     '--bvh-input', cfg.bvh_input if cfg.lookahead else 'off']
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
            self.report({'ERROR'}, str(exc))
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
    bl_label = '完成在途帧后停止'

    def execute(self, context):
        if _active:
            try:
                _active['stop'].touch()
            except OSError as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}
        return {'FINISHED'}


class FRAMEPIPE_OT_log(Operator):
    bl_idname = 'render.frame_pipeline_log'
    bl_label = '打开任务日志'

    def execute(self, context):
        job = _active or _last
        if not job or not job.get('log'):
            return {'CANCELLED'}
        return bpy.ops.wm.path_open(filepath=str(job['log']))


class FRAMEPIPE_PT_render(Panel):
    bl_label = 'Cycles 帧间流水线'
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
        if cfg.lookahead or cfg.mode != 'compositor':
            group.prop(context.preferences.addons[__package__].preferences, 'backend')
        group.operator(FRAMEPIPE_OT_start.bl_idname, icon='RENDER_ANIMATION')
        if _active:
            job = _active
            ui.label(text=f"已输出 {job['done']} / {job['total'] or '…'} 帧" + (f" · 正在渲染 {job['frame']}" if job['frame'] else ''))
            row = ui.row()
            row.enabled = not job['stop'].exists()
            row.operator(FRAMEPIPE_OT_stop.bl_idname, icon='CANCEL')
        elif _last:
            ui.label(text=_last['state'])
        if _active or _last:
            job = _active or _last
            if job.get('lookahead'):
                msg = f"BVH 整树复用 {job['bvh_hits'] - job['bvh_partial']} 次，部分复用 {job['bvh_partial']} 次"
                if job.get('bvh_last_miss'):
                    msg += f" · 最近回退 {job['bvh_last_miss']}"
                ui.label(text=msg)
                if job.get('bvh_partial_detail'):
                    refs, total, branches = job['bvh_partial_detail']
                    ui.label(text=f"最近部分复用 {branches} 个分支，{refs:,} / {total:,} 条引用")
            if job.get('fallback'):
                ui.label(text="部分设置使用原生渲染，详见日志", icon='INFO')
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
