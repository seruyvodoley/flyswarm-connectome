"""Rig Lotnik's CC0 T-34 source scene without changing any source mesh.

Only the source objects' parent nodes and the model root transform are changed.
No mesh vertices, faces, materials, tracks, or wheel shapes are generated or
edited. Run in Blender background mode with ``-- --output <path.glb>``.
"""
import bpy
import hashlib
import json
import struct
import sys
from pathlib import Path
from mathutils import Matrix, Vector


ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    try:
        return Path(ARGS[ARGS.index(name) + 1]).expanduser().resolve()
    except (ValueError, IndexError):
        return default


output = arg("--output")
if output is None:
    raise SystemExit("required: --output <path.glb>")
blend_output = arg("--blend-out", output.with_suffix(".blend"))
report_path = arg("--report", output.with_suffix(".json"))
for path in (output, blend_output, report_path):
    path.parent.mkdir(parents=True, exist_ok=True)

SOURCE_CENTER = Vector((-0.0985, -0.1307, 0.4032))
SOURCE_SCALE = 3.30  # uniform scene scale; source mesh data stays untouched
TURRET_SOURCE = {
    "Circle.018", "Plane.002", "Circle.003", "Circle.004", "Circle.030",
    "Circle.011", "Circle.014", "Cube.008", "Cube.006", "Cube.009",
    "Cube.017", "Cube.007", "Cube.004", "Cube.011",
}
GUN_SOURCE = {"Circle"}
TRACK_NAMES = {"Cube.016": "TrackLeft", "Cube.015": "TrackRight"}

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if len(meshes) != 41:
    raise RuntimeError(f"Expected all 41 source meshes, got {len(meshes)}")
names = {obj.name for obj in meshes}
required = TURRET_SOURCE | GUN_SOURCE | set(TRACK_NAMES)
if not required <= names:
    raise RuntimeError(f"Source scene is missing named mechanical parts: {sorted(required - names)}")

source_triangles = sum(sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons) for obj in meshes)
source_mesh_counts = {obj.name: (len(obj.data.vertices), len(obj.data.polygons)) for obj in meshes}


def geometry_signature(obj):
    digest = hashlib.sha256()
    for vertex in obj.data.vertices:
        digest.update(struct.pack("<3d", *vertex.co))
    for polygon in obj.data.polygons:
        digest.update(struct.pack("<I", len(polygon.vertices)))
        digest.update(struct.pack("<%dI" % len(polygon.vertices), *polygon.vertices))
    return digest.hexdigest()


source_geometry_signatures = {obj.data.as_pointer(): geometry_signature(obj) for obj in meshes}

root = bpy.data.objects.new("VehicleModel", None)
bpy.context.scene.collection.objects.link(root)
root.empty_display_type = "PLAIN_AXES"
root.empty_display_size = 0.25
root.location = -SOURCE_CENTER * SOURCE_SCALE
root.scale = (SOURCE_SCALE,) * 3

hull = bpy.data.objects.new("HullPivot", None)
bpy.context.scene.collection.objects.link(hull)
hull.parent = root
hull.location = (0.0, 0.0, 0.0)
hull.empty_display_type = "PLAIN_AXES"

turret_position = Vector((-0.1001, -0.2731, 0.9030))
gun_position = Vector((-0.1200, -0.6620, 0.9302))
muzzle_position = Vector((-0.1200, -1.3525, 0.9302))

turret = bpy.data.objects.new("TurretPivot", None)
bpy.context.scene.collection.objects.link(turret)
turret.parent = root
turret.location = turret_position
turret.empty_display_type = "CIRCLE"
turret.empty_display_size = 0.16

gun = bpy.data.objects.new("GunElevationPivot", None)
bpy.context.scene.collection.objects.link(gun)
gun.parent = turret
gun.location = gun_position - turret_position
gun.empty_display_type = "CIRCLE"
gun.empty_display_size = 0.10

muzzle = bpy.data.objects.new("Muzzle", None)
bpy.context.scene.collection.objects.link(muzzle)
muzzle.parent = gun
muzzle.location = muzzle_position - gun_position
muzzle.empty_display_type = "SPHERE"
muzzle.empty_display_size = 0.035


def parent_source_mesh(obj, parent):
    """Reparent an unchanged object while preserving source mesh data and pose."""
    source_world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    if parent == hull:
        obj.matrix_basis = source_world
    elif parent == turret:
        local = Matrix.Translation(-turret_position) @ source_world
        obj.matrix_basis = local
    elif parent == gun:
        local = Matrix.Translation(-gun_position) @ source_world
        obj.matrix_basis = local
    else:
        raise RuntimeError("Unexpected source mesh parent")


for obj in meshes:
    if obj.name in GUN_SOURCE:
        parent = gun
        obj.name = "GunBarrel"
    elif obj.name in TURRET_SOURCE:
        parent = turret
    else:
        parent = hull
    parent_source_mesh(obj, parent)

for source_name, runtime_name in TRACK_NAMES.items():
    bpy.data.objects[source_name].name = runtime_name

bpy.context.view_layer.update()

# Prove the source's mesh payloads are unchanged before exporting.
for obj in bpy.context.scene.objects:
    if obj.type == "MESH":
        original_pointer = obj.data.as_pointer()
        if original_pointer not in source_geometry_signatures or geometry_signature(obj) != source_geometry_signatures[original_pointer]:
            raise RuntimeError(f"Generated or modified mesh detected: {obj.name}")
for original_name, counts in source_mesh_counts.items():
    obj = bpy.data.objects.get({"Circle": "GunBarrel", **TRACK_NAMES}.get(original_name, original_name))
    if obj is None or (len(obj.data.vertices), len(obj.data.polygons)) != counts:
        raise RuntimeError(f"Source mesh changed or missing: {original_name}")

bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))
bpy.ops.export_scene.gltf(
    filepath=str(output), export_format="GLB", export_apply=False,
    export_yup=True, export_cameras=False, export_lights=False,
    export_materials="EXPORT", export_keep_originals=True,
)

report = {
    "asset": "T-34/85 full-source articulated model",
    "source_author": "Lotnik",
    "source_license": "CC0 1.0",
    "source_url": "https://opengameart.org/content/t-3485",
    "source_blend": "candidates/Rudy.blend",
    "source_mesh_objects": len(meshes),
    "source_triangles": source_triangles,
    "runtime_mesh_objects": len(meshes),
    "runtime_triangles": source_triangles,
    "runtime_glb_bytes": output.stat().st_size,
    "source_geometry_modified": False,
    "source_geometry_sha256": hashlib.sha256("".join(sorted(source_geometry_signatures.values())).encode("ascii")).hexdigest(),
    "nodes": {"root": "VehicleModel", "hull": "HullPivot", "turret": "TurretPivot", "gun": "GunElevationPivot", "muzzle": "Muzzle", "tracks": ["TrackLeft", "TrackRight"]},
    "notes": [
        "All 41 original source meshes are retained; no geometry, material, or wheel was added, deleted, redrawn, rescaled, or reshaped.",
        "Only a uniform root scale/ground offset and mechanical parenting pivots were added.",
        "Track loops and all original road-wheel meshes remain exactly as authored by Lotnik.",
        "The source does not claim a verified factory/year configuration.",
    ],
}
report_path.write_text(json.dumps(report, indent=2) + "\n")
print("SOURCE_RIG_EXPORT", json.dumps(report), flush=True)
