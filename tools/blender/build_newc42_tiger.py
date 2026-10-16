"""Prepare Newc42's CC0 Tiger I Blender source for FlySwarm's vehicle rig."""

import argparse
import os
import sys

import bpy
from mathutils import Matrix, Vector


def parent_preserving_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def make_empty(name, location, parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.2
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    if parent is not None:
        # Force Blender to evaluate the new object's world matrix before
        # parenting it; otherwise empty pivots can export at the origin.
        bpy.context.view_layer.update()
        obj.parent = parent
        bpy.context.view_layer.update()
        obj.matrix_world = Matrix.Translation(location)
    return obj


def bounds_world(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


def export_glb(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--blend-out", required=True)
    parser.add_argument("--glb-out", required=True)
    args = parser.parse_args(argv)

    bpy.ops.wm.open_mainfile(filepath=args.source)
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    hull = next((obj for obj in meshes if obj.name == "Pz-VI-Tiger"), None)
    turret_mesh = next((obj for obj in meshes if obj.name == "Turret"), None)
    barrel = next((obj for obj in meshes if obj.name == "Barrel"), None)
    tracks = {obj.name: obj for obj in meshes if obj.name in ("TracksLeft", "TracksRight")}
    if not hull or not turret_mesh or not barrel or len(tracks) != 2:
        raise RuntimeError("Newc42 Tiger source is missing hull, turret, gun, or tracks")

    # The source is already at useful real-world scale and has separately
    # modeled wheels/track runs; keep its silhouette and topology intact.
    turret_origin = turret_mesh.matrix_world.translation.copy()
    gun_origin = barrel.matrix_world.translation.copy()
    gun_low, gun_high = bounds_world(barrel)
    muzzle_world = Vector((
        (gun_low.x + gun_high.x) * 0.5,
        gun_low.y,
        (gun_low.z + gun_high.z) * 0.5,
    ))

    # Remove any authoring cameras/lights while preserving the included mesh
    # hierarchy and the atlas material.
    for obj in list(scene.objects):
        if obj.type not in ("MESH", "EMPTY"):
            bpy.data.objects.remove(obj, do_unlink=True)

    root = make_empty("VehicleModel", Vector((0.0, 0.0, 0.0)))
    hull_pivot = make_empty("HullPivot", Vector((0.0, 0.0, 0.0)), root)
    turret_pivot = make_empty("TurretPivot", turret_origin, root)
    gun_pivot = make_empty("GunElevationPivot", gun_origin, turret_pivot)

    hull.name = "HullGeometry"
    parent_preserving_world(hull, hull_pivot)
    for track_name, track_obj in tracks.items():
        track_obj.name = "TrackLeft" if track_name == "TracksLeft" else "TrackRight"
        parent_preserving_world(track_obj, hull_pivot)
    for obj in meshes:
        if obj.name.startswith("Wheel"):
            # Preserve the source's nested track/wheel hierarchy for the
            # existing vehicle wheel-spin behavior.
            continue
    parent_preserving_world(turret_mesh, turret_pivot)
    turret_mesh.name = "TurretGeometry"
    parent_preserving_world(barrel, gun_pivot)
    barrel.name = "GunBarrel"
    muzzle = make_empty("Muzzle", muzzle_world, gun_pivot)

    # Wheels retain their original parent track loops, which are now under the
    # hull pivot. All other auxiliary meshes remain with the hull.
    for obj in meshes:
        if obj in (hull, turret_mesh, barrel) or obj in tracks.values():
            continue
        if obj.name.startswith("Wheel"):
            continue
        parent_preserving_world(obj, hull_pivot)

    for image in bpy.data.images:
        if image.source != "FILE":
            continue
        image_path = bpy.path.abspath(image.filepath)
        if os.path.isfile(image_path):
            image.filepath = image_path
            image.pack()
    os.makedirs(os.path.dirname(os.path.abspath(args.blend_out)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.blend_out)
    export_glb(args.glb_out)
    print(
        "NEWC42_TIGER_OK",
        "mesh_nodes", sum(1 for obj in scene.objects if obj.type == "MESH"),
        "wheel_nodes", sum(1 for obj in scene.objects if obj.type == "MESH" and obj.name.startswith("Wheel")),
        "turret", turret_pivot.name,
        "gun", gun_pivot.name,
        "muzzle", muzzle.name,
    )


if __name__ == "__main__":
    main()
