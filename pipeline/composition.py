"""Prepare a standalone compositor without copying any render scene geometry."""

import bpy


class Unsupported(ValueError):
    pass


SOCKET_TAG = "_cycles_pipeline_input"
DEVICE_OPTIONS = ("denoising_input_passes", "denoising_prefilter", "denoising_quality")
VIEW_OPTIONS = (
    "view_transform", "look", "exposure", "gamma", "use_white_balance",
    "white_balance_temperature", "white_balance_tint",
)
RENDER_OPTIONS = (
    "resolution_x", "resolution_y", "resolution_percentage", "pixel_aspect_x",
    "pixel_aspect_y", "dither_intensity", "fps", "fps_base", "compositor_precision",
    "compositor_denoise_final_quality",
)


def snapshot(obj, keys):
    return {k: getattr(obj, k) for k in keys}


def apply(obj, values):
    for key, value in values.items():
        setattr(obj, key, value)


def settings(scene):
    im = scene.render.image_settings
    color_source = im if im.color_management == "OVERRIDE" else scene
    if color_source.view_settings.use_curve_mapping:
        raise Unsupported("custom view curves need the original scene")
    return {
        "render": snapshot(scene.render, RENDER_OPTIONS),
        "png": {"color_mode": im.color_mode, "color_depth": im.color_depth,
                "compression": im.compression},
        "display": color_source.display_settings.display_device,
        "view": snapshot(color_source.view_settings, VIEW_OPTIONS),
        "denoise": snapshot(scene.cycles, DEVICE_OPTIONS),
    }


def enabled_layer(scene):
    layers = [vl for vl in scene.view_layers if vl.use]
    if len(layers) != 1:
        raise Unsupported("multiple enabled view layers")
    return layers[0]


def qualify(scene):
    if scene.render.engine != 'CYCLES':
        raise Unsupported("the render engine is not Cycles")
    layer = enabled_layer(scene)
    if not (layer.cycles.use_denoising and scene.cycles.use_denoising):
        raise Unsupported("Cycles final denoising is off")
    # The raw legacy OptiX enum may have no Python identifier on an AMD-only system.
    # A generic scene keeps the engine's own device fallback via the synchronous path.
    if scene.cycles.get("denoiser") == 2:
        raise Unsupported("saved OptiX selection uses the original render engine's device choice")
    if scene.cycles.denoiser != 'OPENIMAGEDENOISE' or scene.cycles.denoising_use_gpu:
        raise Unsupported("the source scene did not select CPU OpenImageDenoise")
    if not layer.use_pass_combined:
        raise Unsupported("the enabled layer does not output Combined")
    render = scene.render
    if render.use_multiview:
        raise Unsupported("multi-view output requires native rendering")
    if render.use_border:
        bounds = (render.border_min_x, render.border_max_x, render.border_min_y, render.border_max_y)
        if bounds != (0.0, 1.0, 0.0, 1.0):
            raise Unsupported(f"partial render border (xmin, xmax, ymin, ymax)={bounds}")
    if render.use_stamp:
        raise Unsupported("visible metadata stamps require native output")
    if scene.render.use_sequencer and scene.sequence_editor and len(scene.sequence_editor.strips):
        raise Unsupported("the video sequencer contributes to this scene")
    if scene.render.image_settings.file_format != 'PNG':
        raise Unsupported("the external PNG writer only supports source PNG settings")
    if getattr(layer, "use_pass_shadow_catcher", False):
        raise Unsupported("shadow catcher pass denoising requires the original render engine")
    settings(scene)
    return layer


def check_tree(tree, scene, layer, nested=False, seen=None):
    seen = set() if seen is None else seen
    if tree in seen:
        return
    seen.add(tree)
    if tree.animation_data:
        raise Unsupported("animated or driven compositor node tree")
    for node in tree.nodes:
        if node.type == 'R_LAYERS':
            if nested or node.scene not in (None, scene) or node.layer not in ('', layer.name):
                raise Unsupported("render-layer node uses another scene, layer or nested group")
            for link in tree.links:
                if link.from_node == node and link.from_socket.name not in ("Image", "Alpha"):
                    raise Unsupported("compositor uses render pass " + link.from_socket.name)
            continue
        if node.type in {'OUTPUT_FILE', 'CRYPTOMATTE_V2', 'CRYPTOMATTE', 'MOVIECLIP',
                         'MASK', 'KEYINGSCREEN', 'STABILIZE2D', 'TRACKPOS', 'DOUBLEEDGEMASK',
                         'TIME', 'SCENE_TIME'}:
            raise Unsupported("compositor node requires original scene state: " + node.name)
        for prop in node.bl_rna.properties:
            if prop.type != 'POINTER' or prop.identifier in ('rna_type', 'id_data'):
                continue
            ref = getattr(node, prop.identifier, None)
            if isinstance(ref, bpy.types.NodeTree):
                check_tree(ref, scene, layer, True, seen)
            elif isinstance(ref, bpy.types.Image):
                if ref.source not in ('FILE', 'GENERATED') or ref.animation_data:
                    raise Unsupported("compositor image is time-dependent: " + ref.name)
            elif isinstance(ref, bpy.types.ID):
                raise Unsupported("compositor node references a scene asset: " + node.name)


def save_graph(scene, layer, path):
    tree = scene.compositing_node_group if scene.render.use_compositing else None
    if tree:
        check_tree(tree, scene, layer)
        copy = tree.copy()
    else:
        copy = bpy.data.node_groups.new("Pipeline composite", "CompositorNodeTree")
    try:
        if tree:
            for node in list(copy.nodes):
                if node.type != 'R_LAYERS':
                    continue
                for name in ("Image", "Alpha"):
                    output = node.outputs.get(name)
                    if not output or not output.is_linked:
                        continue
                    destinations = [link.to_socket for link in output.links]
                    route = copy.nodes.new('NodeReroute')
                    route[SOCKET_TAG] = name
                    for dest in destinations:
                        copy.links.new(route.outputs[0], dest)
                copy.nodes.remove(node)
        else:
            copy.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
            output = copy.nodes.new('NodeGroupOutput')
            route = copy.nodes.new('NodeReroute')
            route[SOCKET_TAG] = "Image"
            copy.links.new(route.outputs[0], output.inputs[0])
        bpy.data.libraries.write(str(path), {copy}, path_remap='ABSOLUTE', fake_user=True)
        return copy.name
    finally:
        bpy.data.node_groups.remove(copy)
