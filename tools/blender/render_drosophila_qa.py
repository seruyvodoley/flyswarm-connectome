"""Render matching front, side and dorsal QA views from the exported GLB."""
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
MODEL = Path(os.environ.get("FLYSWARM_QA_MODEL", ROOT / "frontend/godot/assets/environment/fly/fly.glb"))
OUT = Path(os.environ.get("FLYSWARM_QA_OUT", "/Volumes/RisingSail/FlySwarm-Build/redesign-qa"))
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(MODEL))
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
world = bpy.data.worlds.new("FlySwarm studio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.028, 0.038, 0.036, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.48
scene.world = world

bpy.ops.object.light_add(type="AREA", location=(2.2, -3.0, 3.7))
key = bpy.context.object
key.data.energy = 760
key.data.shape = "DISK"
key.data.size = 3.0
bpy.ops.object.light_add(type="AREA", location=(-2.7, 2.8, 1.5))
fill = bpy.context.object
fill.data.energy = 380
fill.data.color = (0.72, 0.83, 0.77)
fill.data.size = 3.5
bpy.ops.object.light_add(type="AREA", location=(1.2, 2.0, 2.8))
rim = bpy.context.object
rim.data.energy = 530
rim.data.color = (1.0, 0.69, 0.39)
rim.data.size = 2.0

camera_data = bpy.data.cameras.new("QA Camera")
camera = bpy.data.objects.new("QA Camera", camera_data)
scene.collection.objects.link(camera)
camera_data.type = "ORTHO"
camera_data.lens = 55
scene.camera = camera

model_objects = [o for o in scene.objects if o.type in {"MESH", "EMPTY"} and o.name not in {"WingPivot_L", "WingPivot_R"}]
coords = [o.matrix_world @ Vector(corner) for o in model_objects if o.type == "MESH" for corner in o.bound_box]
minimum = Vector((min(p.x for p in coords), min(p.y for p in coords), min(p.z for p in coords)))
maximum = Vector((max(p.x for p in coords), max(p.y for p in coords), max(p.z for p in coords)))
center = (minimum + maximum) * 0.5
size = maximum - minimum
camera_data.ortho_scale = max(size.x, size.y, size.z) * 1.20

views = {
    "front": Vector((1, -0.15, 0.18)),
    "side": Vector((0.12, -1, 0.18)),
    "top": Vector((0.05, -0.05, 1)),
}
for name, direction in views.items():
    direction.normalize()
    camera.location = center + direction * 5
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(OUT / ("fly-after-" + name + ".png"))
    bpy.ops.render.render(write_still=True)

# Capture both wing-flap extremes for the runtime animation reference.
for suffix, angle in [("upstroke", -0.20), ("downstroke", 0.20)]:
    for pivot in [o for o in scene.objects if o.name.startswith("WingPivot_")]:
        pivot.rotation_euler.x = angle * (-1 if pivot.name.endswith("L") else 1)
    direction = Vector((0.55, -0.65, 0.34)).normalized()
    camera.location = center + direction * 5
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(OUT / ("fly-after-" + suffix + ".png"))
    bpy.ops.render.render(write_still=True)
