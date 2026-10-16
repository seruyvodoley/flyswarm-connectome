"""Split and optimize selected MetaWorldOS CC0 tank GLBs for FlySwarm."""

import argparse
import os
import sys

import bpy
from mathutils import Matrix, Vector


SPECS = {
    "is2_1944": {
        "width_m": 3.07,
        "overall_length_m": 9.80,
        "height_m": 2.73,
        "turret_z_min": 0.20,
        "turret_y_max": 0.30,
        "barrel_y_cut": -0.28,
    },
    "panther_g": {
        "width_m": 3.42,
        "overall_length_m": 8.86,
        "height_m": 2.99,
        "turret_z_min": 0.20,
        "turret_y_max": 0.34,
        "barrel_y_cut": -0.27,
    },
}

DECIMATE = {
    "track_left": 0.16,
    "track_right": 0.16,
    "running_left": 0.055,
    "running_right": 0.055,
    "hull": 0.22,
    "turret": 0.24,
    "gun": 0.45,
}
TEXTURE_MAX_SIZE = 2048


def world_bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in pts) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in pts) for i in range(3)))
    return low, high


def classify(center, bounds, spec):
    low, high, source_size = bounds
    width, length, height = source_size
    x, y, z = center
    if abs(x) < width * 0.25 and y < spec["barrel_y_cut"] and z > low.z + height * 0.45:
        return "gun"
    if z > low.z + spec["turret_z_min"] and -0.37 < y < spec["turret_y_max"]:
        return "turret"
    if abs(x) > width * 0.34 and z < low.z + height * 0.56:
        return "tracks_right" if x > 0.0 else "tracks_left"
    return "hull"


def transform_mesh_world(obj, point_transform):
    inv = obj.matrix_world.inverted()
    for vertex in obj.data.vertices:
        world = obj.matrix_world @ vertex.co
        vertex.co = inv @ point_transform(world)
    obj.data.update()


def join_group(objects, name):
    if not objects:
        raise RuntimeError("Cannot create empty model group: " + name)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    joined.data.name = name + "Mesh"
    joined.select_set(False)
    return joined


def empty(name, parent, world_position):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.2
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation(world_position)
    if parent is not None:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
    return obj


def parent_preserving_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def simplify(obj, ratio):
    bpy.ops.object.select_all(action="DESELECT")
    modifier = obj.modifiers.new("FlySwarm_GameBudget", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.select_set(False)


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--vehicle", choices=sorted(SPECS), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--blend-out", required=True)
    parser.add_argument("--glb-out", required=True)
    args = parser.parse_args(argv)
    spec = SPECS[args.vehicle]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.source)
    scene = bpy.context.scene
    source_meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    if len(source_meshes) != 1:
        raise RuntimeError("Expected a single imported MetaWorldOS mesh")
    source = source_meshes[0]
    original_low, original_high = world_bounds(source)
    source_size = original_high - original_low
    if min(source_size) <= 0.0:
        raise RuntimeError("Source tank has invalid bounds")

    # Split disconnected islands from the combined GLB mesh. The source has
    # many tiny detail islands; they are regrouped into five logical rig parts.
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    components = [obj for obj in scene.objects if obj.type == "MESH"]
    groups = {key: [] for key in DECIMATE}

    # Use the center of the lower hull and ground plane as the model origin.
    raw_centers = {}
    hull_y_extents = []
    source_bounds = (original_low, original_high, source_size)
    for obj in components:
        low, high = world_bounds(obj)
        center = (low + high) * 0.5
        key = classify(center, source_bounds, spec)
        if key.startswith("tracks_"):
            extent = high - low
            side = key.removeprefix("tracks_")
            # The long, thin disconnected islands are the continuous belt
            # silhouette; the remaining side islands are wheels and fittings.
            key = "track_" + side if extent.y > 0.20 and extent.z < 0.055 and extent.x < 0.14 else "running_" + side
        groups[key].append(obj)
        raw_centers[obj.name] = (low, high, center, key)
        if key not in ("gun", "turret"):
            hull_y_extents.append((low.y, high.y))
    hull_center_y = (min(v[0] for v in hull_y_extents) + max(v[1] for v in hull_y_extents)) * 0.5
    ground_z = original_low.z
    sx = spec["width_m"] / source_size.x
    sy = spec["overall_length_m"] / source_size.y
    sz = spec["height_m"] / source_size.z

    def scale_point(point):
        return Vector((point.x * sx, (point.y - hull_center_y) * sy, (point.z - ground_z) * sz))

    # Keep cylindrical road-wheel faces round while stretching track spacing
    # and armor length to match the vehicle's approximate overall dimensions.
    wheel_compensation = 0
    transformed_bounds = {key: [Vector((float("inf"),) * 3), Vector((float("-inf"),) * 3)] for key in groups}
    for obj in components:
        low, high, center, key = raw_centers[obj.name]
        extent = high - low
        is_wheel_piece = (
            key.startswith("running_")
            and 0.045 < extent.y < 0.19
            and 0.045 < extent.z < 0.19
            and 0.60 < extent.y / max(extent.z, 1e-6) < 1.45
            and extent.x < 0.14
            and 0.035 < center.z - ground_z < source_size.z * 0.58
        )

        def transform(point):
            scaled = scale_point(point)
            if is_wheel_piece:
                scaled.y = (center.y - hull_center_y) * sy + (point.y - center.y) * sz
            return scaled

        transform_mesh_world(obj, transform)
        if is_wheel_piece:
            wheel_compensation += 1
        low2, high2 = world_bounds(obj)
        target = transformed_bounds[key]
        target[0] = Vector(tuple(min(target[0][i], low2[i]) for i in range(3)))
        target[1] = Vector(tuple(max(target[1][i], high2[i]) for i in range(3)))

    # Merge hundreds/thousands of loose detail objects per side into manageable
    # meshes, then decimate them while retaining UVs and the embedded PBR map.
    names = {
        "hull": "HullGeometry",
        "track_left": "TrackLeft",
        "track_right": "TrackRight",
        "running_left": "RoadWheelsLeft",
        "running_right": "RoadWheelsRight",
        "turret": "TurretGeometry",
        "gun": "GunBarrel",
    }
    merged = {key: join_group(groups[key], names[key]) for key in names}
    for key, obj in merged.items():
        simplify(obj, DECIMATE[key])

    # Use the final joined meshes' evaluated world bounds. During separation
    # Blender keeps the original GLB node transform on each loose island, so
    # accumulating pre-join vertex bounds can place pivots below the vehicle.
    turret_low, turret_high = world_bounds(merged["turret"])
    gun_low, gun_high = world_bounds(merged["gun"])
    turret_pos = Vector((0.0, (turret_low.y + turret_high.y) * 0.5, turret_low.z))
    gun_pos = Vector((0.0, gun_high.y, (gun_low.z + gun_high.z) * 0.5))
    muzzle_pos = Vector((0.0, gun_low.y, gun_pos.z))

    root = empty("VehicleModel", None, Vector((0.0, 0.0, 0.0)))
    hull_pivot = empty("HullPivot", root, Vector((0.0, 0.0, 0.0)))
    turret_pivot = empty("TurretPivot", root, turret_pos)
    gun_pivot = empty("GunElevationPivot", turret_pivot, gun_pos)
    muzzle = empty("Muzzle", gun_pivot, muzzle_pos)
    parent_preserving_world(merged["hull"], hull_pivot)
    parent_preserving_world(merged["track_left"], hull_pivot)
    parent_preserving_world(merged["track_right"], hull_pivot)
    parent_preserving_world(merged["running_left"], hull_pivot)
    parent_preserving_world(merged["running_right"], hull_pivot)
    parent_preserving_world(merged["turret"], turret_pivot)
    parent_preserving_world(merged["gun"], gun_pivot)

    # 4K source maps dominate each runtime GLB. 2K retains ample detail for
    # FlySwarm's camera distance while keeping downloads and VRAM reasonable.
    for image in bpy.data.images:
        if image.source != "FILE" or max(image.size) <= TEXTURE_MAX_SIZE:
            continue
        factor = TEXTURE_MAX_SIZE / max(image.size)
        image.scale(round(image.size[0] * factor), round(image.size[1] * factor))
        image.pack()

    os.makedirs(os.path.dirname(os.path.abspath(args.blend_out)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.glb_out)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend_out)
    bpy.ops.export_scene.gltf(
        filepath=args.glb_out,
        export_format="GLB",
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    counts = {key: len(obj.data.polygons) for key, obj in merged.items()}
    print("METAWORLDOS_BUILD_OK", args.vehicle, "triangles", counts, "wheel_parts_shape_preserved", wheel_compensation)


if __name__ == "__main__":
    main()
