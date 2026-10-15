"""Build a minimal articulated T-34/85 scene from Lotnik's CC0 Blender file.

Run with Blender: blender -b <Rudy.blend> --python tools/blender/build_lotnik_t34_candidate.py -- --output <path.glb>
The source scene is never saved over. Mesh geometry is preserved; this script
groups source meshes under hull, turret, and gun pivots, adds simple circular
wheel rollers, and normalizes the model to the current vehicle scale/axis.
"""
import bpy
import bmesh
import json
import math
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
output.parent.mkdir(parents=True, exist_ok=True)
report_path = arg("--report", output.with_suffix(".json"))
report_path.parent.mkdir(parents=True, exist_ok=True)

# Reviewed from the source render and measured component bounds.  Coordinates
# are the authored Blender scene axes: +Z up, -Y forward, +X right.
SOURCE_CENTER_X = -0.0985
SOURCE_CENTER_Y = -0.1307
SOURCE_GROUND_Z = 0.4032
SCALE = 3.30
TURRET_SOURCE = {
    "Circle.018", "Plane.002", "Circle.003", "Circle.004", "Circle.030",
    "Circle.011", "Circle.014", "Cube.008", "Cube.006", "Cube.009",
    "Cube.017", "Cube.007", "Cube.004", "Cube.011",
}
GUN_SOURCE = {"Circle"}
TRACK_NAMES = {"Cube.016": "TrackLeft", "Cube.015": "TrackRight"}

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if len(meshes) != 41:
    raise SystemExit(f"source structure changed: expected 41 mesh objects, found {len(meshes)}")
names = {obj.name for obj in meshes}
required = TURRET_SOURCE | GUN_SOURCE | set(TRACK_NAMES)
if not required.issubset(names):
    raise SystemExit(f"source object names changed; missing {sorted(required - names)}")

offset = Vector((SOURCE_CENTER_X * -SCALE, SOURCE_CENTER_Y * -SCALE, SOURCE_GROUND_Z * -SCALE))
normalization = Matrix.Translation(offset) @ Matrix.Scale(SCALE, 4)

root = bpy.data.objects.new("VehicleModel", None)
bpy.context.scene.collection.objects.link(root)
root.empty_display_type = "PLAIN_AXES"
root.empty_display_size = 0.25
hull = bpy.data.objects.new("HullPivot", None)
bpy.context.scene.collection.objects.link(hull)
hull.parent = root
hull.matrix_parent_inverse = Matrix.Identity(4)

turret_source = Vector((-0.1001, -0.2731, 0.9030))
turret_position = normalization @ turret_source.to_4d()
turret = bpy.data.objects.new("TurretPivot", None)
bpy.context.scene.collection.objects.link(turret)
turret.parent = root
turret.matrix_parent_inverse = Matrix.Identity(4)
turret.location = turret_position.xyz
turret.empty_display_type = "CIRCLE"
turret.empty_display_size = 0.16
bpy.context.view_layer.update()

gun_source = Vector((-0.1200, -0.6620, 0.9302))
gun_position = normalization @ gun_source.to_4d()
gun = bpy.data.objects.new("GunElevationPivot", None)
bpy.context.scene.collection.objects.link(gun)
gun.parent = turret
gun.matrix_parent_inverse = Matrix.Identity(4)
gun.location = (turret.matrix_world.inverted() @ gun_position).xyz
gun.empty_display_type = "CIRCLE"
gun.empty_display_size = 0.10
bpy.context.view_layer.update()

for obj in meshes:
    source_world = obj.matrix_world.copy()
    target_world = normalization @ source_world
    if obj.name in GUN_SOURCE:
        parent = gun
        obj.name = "GunBarrel"
    elif obj.name in TURRET_SOURCE:
        parent = turret
    else:
        parent = hull
    obj.parent = parent
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = target_world
# The two track loops are hull-mounted static meshes in the source. Keep them
# as separate model nodes so later running-gear work can address each side.
for source_name, runtime_name in TRACK_NAMES.items():
    obj = bpy.data.objects.get(source_name)
    if obj is not None:
        obj.name = runtime_name

# The gun ends at y=-1.3525 in the source; keep its muzzle attached to elevation.
muzzle_source = Vector((-0.1200, -1.3525, 0.9302))
muzzle_position = normalization @ muzzle_source.to_4d()
muzzle = bpy.data.objects.new("Muzzle", None)
bpy.context.scene.collection.objects.link(muzzle)
muzzle.parent = gun
muzzle.matrix_parent_inverse = Matrix.Identity(4)
muzzle.location = (gun.matrix_world.inverted() @ muzzle_position).xyz
muzzle.empty_display_type = "SPHERE"
muzzle.empty_display_size = 0.035

# The source contains track loops but no complete, independently addressable
# road-wheel set. Add only simple cylindrical rollers inside those loops; the
# source hull, turret, tracks, and gun remain untouched. These nodes reuse the
# runtime's existing wheel spin animation.
def make_wheel(name, x, y, z, radius, depth, segments=16):
    vertices = []
    for axial in (-depth * 0.5, depth * 0.5):
        for index in range(segments):
            angle = math.tau * index / segments
            vertices.append((axial, math.cos(angle) * radius, math.sin(angle) * radius))
    faces = []
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple(range(segments, 2 * segments)))
    for index in range(segments):
        nxt = (index + 1) % segments
        faces.append((index, nxt, segments + nxt, segments + index))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = hull
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = (x, y, z)
    return obj

wheel_layout = [
    ("FrontIdler", -2.62, 0.35),
    ("Road01", -1.75, 0.30),
    ("Road02", -0.88, 0.30),
    ("Road03", -0.01, 0.30),
    ("Road04", 0.86, 0.30),
    ("Road05", 1.73, 0.30),
    ("RearDrive", 2.40, 0.35),
]
for side, x in (("Left", -1.34), ("Right", 1.34)):
    for role, y, radius in wheel_layout:
        make_wheel("WheelGeometry%s%s" % (side, role), x, y, 0.37, radius, 0.28)

# Write source review metadata beside the generated pilot for repeatability.
triangle_count = sum(sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons) for obj in meshes)
report = {
    "asset": "T-34/85 low-poly pilot",
    "source_author": "Lotnik",
    "source_license": "CC0 1.0",
    "source_url": "https://opengameart.org/content/t-3485",
    "source_blend": "Rudy.blend",
    "mesh_object_count": len(meshes),
    "triangles": triangle_count,
    "added_simplified_wheels": 14,
    "runtime_mesh_node_count": len(meshes) + 14,
    "runtime_triangles": triangle_count + 14 * (4 * 16 - 4),
    "scale": SCALE,
    "runtime_axes": "right +X, forward +Z in Godot (authored Blender -Y), up +Y in Godot",
    "nodes": {"hull": "HullPivot", "turret": "TurretPivot", "gun": "GunElevationPivot", "muzzle": "Muzzle", "tracks": ["TrackLeft", "TrackRight"]},
    "notes": ["No source geometry was cut or repaired.", "Turret/gun pivots are manually placed from measured source bounds.", "Track loops are separate static meshes; their motion is static.", "Fourteen simple cylindrical rollers were added as separate wheel-animation nodes.", "The source does not establish factory, year, or exact 1944 configuration."],
}

bpy.context.view_layer.update()
bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_apply=True,
                          export_yup=True, export_cameras=False, export_lights=False,
                          export_materials="EXPORT", export_keep_originals=True)
report["runtime_glb_bytes"] = output.stat().st_size
report_path.write_text(json.dumps(report, indent=2) + "\n")
print("PILOT_EXPORT", json.dumps(report), flush=True)
