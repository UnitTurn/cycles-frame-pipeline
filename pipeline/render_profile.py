# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional settings from the production Ruins worker, scoped to this render."""
from contextlib import contextmanager
import bpy


@contextmanager
def apply_profile(scene, profile):
    if profile == 'scene':
        yield
        return
    if profile != 'ruins-hip256':
        raise ValueError(f"Unknown render profile: {profile}")
    if scene.render.engine != 'CYCLES':
        raise ValueError("Ruins HIP profile requires a Cycles scene")
    cycles = scene.cycles
    prefs = bpy.context.preferences.addons['cycles'].preferences
    settings = ('samples', 'use_adaptive_sampling', 'adaptive_threshold', 'device')
    saved = {name: getattr(cycles, name) for name in settings}
    # A saved OptiX enum is still valid project data even when this HIP build cannot expose it.
    denoiser_raw = cycles.get('denoiser')
    denoise_gpu_raw = cycles.get('denoising_use_gpu')
    # Cycles enum value 2 is OptiX. No HIP device can provide the OptiX denoiser.
    # This preset selects exclusively RX 7800 XT HIP below; official Cycles therefore
    # resolves this exact request to CPU OIDN, preserving quality, guides and prefilter.
    resolve_optix = denoiser_raw == 2
    persistent = scene.render.use_persistent_data
    layers = [(layer, layer.samples) for layer in scene.view_layers]
    device_type, hiprt = prefs.compute_device_type, prefs.use_hiprt
    enabled = {device.id: device.use for device in prefs.devices}
    try:
        prefs.compute_device_type = 'HIP'
        prefs.use_hiprt = False
        prefs.refresh_devices()
        # Detect newly discovered devices before changing any selection.
        for device in prefs.devices:
            enabled.setdefault(device.id, device.use)
        cards = [d.id for d in prefs.devices if d.type == 'HIP' and '7800 XT' in d.name]
        if not cards:
            raise RuntimeError('Ruins preset requires an AMD Radeon RX 7800 XT on the HIP backend')
        for device in prefs.devices:
            device.use = device.id in cards
        cycles.device = 'GPU'
        cycles.samples = 256
        cycles.use_adaptive_sampling = True
        cycles.adaptive_threshold = 0.01
        if resolve_optix:
            cycles.denoiser = 'OPENIMAGEDENOISE'
            cycles.denoising_use_gpu = False
        scene.render.use_persistent_data = True
        for layer, samples in layers:
            if samples:
                layer.samples = 256
        denoise_note = ('saved OptiX -> CPU OpenImageDenoise (HIP fallback)' if resolve_optix
                        else 'scene denoiser and device preserved')
        print('PIPELINE_PROFILE ruins-hip256: RX 7800 XT HIP, hardware RT off, 256 samples, '
              f'adaptive 0.01, persistent data, {denoise_note}', flush=True)
        yield
    finally:
        for name, value in saved.items():
            setattr(cycles, name, value)
        if resolve_optix:
            cycles['denoiser'] = denoiser_raw
            if denoise_gpu_raw is None:
                cycles.property_unset('denoising_use_gpu')
            else:
                cycles['denoising_use_gpu'] = denoise_gpu_raw
        scene.render.use_persistent_data = persistent
        for layer, samples in layers:
            layer.samples = samples
        for device in prefs.devices:
            if device.id in enabled:
                device.use = enabled[device.id]
        prefs.use_hiprt = hiprt
        prefs.compute_device_type = device_type
