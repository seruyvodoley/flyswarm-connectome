"""Optimize and rig the user-selected Ebony female Drosophila GLB.

The asset remains a visual preview only. No simulation or MaleCNS inputs are
read or changed. Run with Blender 5.x from the repository root. Place the
Sketchfab CC BY source GLB at SOURCE (or set FLYSWARM_FLY_SOURCE); the raw
download is kept outside the distributable application.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/blender/upstream/ebony_mutation_female_drosophila_melanogaster.glb"
OUTPUT = Path(os.environ.get(
    "FLYSWARM_FLY_OUTPUT",
    str(ROOT / "frontend/godot/assets/environment/fly/fly.glb"),
))
BODY_RATIO = float(os.environ.get("FLYSWARM_BODY_DECIMATE", "0.32"))
WING_RATIO = float(os.environ.get("FLYSWARM_WING_DECIMATE", "0.46"))


def make_material(name: str, color: tuple[float, float, float], roughness: float,
                  *, metallic: float = 0.0, alpha: float = 1.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Coat Weight"].default_value = 0.22 if metallic else 0.08
    shader.inputs["Coat Roughness"].default_value = 0.24
    shader.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        mat.surface_render_method = "BLENDED"
    return mat


def import_meshes() -> list[bpy.types.Object]:
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    meshes = [obj for obj in bpy.context.scene.objects
              if obj.type == "MESH" and len(obj.data.polygons) > 100]
    if not meshes:
        raise RuntimeError("The Ebony Drosophila GLB has no usable mesh parts")
    for obj in meshes:
        # Bake the original Sketchfab hierarchy (including its axis conversion)
        # before adding a shared preview skeleton.
        obj.data.transform(obj.matrix_world.copy())
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        obj.data.materials.clear()
        source_name = obj.name
        if source_name in {"Object_8", "Object_9"}:
            obj.name = "Drosophila_Wing_L" if source_name == "Object_8" else "Drosophila_Wing_R"
        elif source_name == "Object_10":
            obj.name = "Drosophila_Compound_Eyes"
        else:
            obj.name = "Drosophila_" + source_name.removeprefix("Object_")
        bpy.context.view_layer.objects.active = obj
        decimate = obj.modifiers.new("Runtime mesh reduction", "DECIMATE")
        decimate.ratio = WING_RATIO if "Wing_" in obj.name else BODY_RATIO
        bpy.ops.object.modifier_apply(modifier=decimate.name)
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or obj not in meshes:
            bpy.data.objects.remove(obj, do_unlink=True)
    return meshes


def add_materials(meshes: list[bpy.types.Object]) -> None:
    body = make_material("Ebony cuticle · blue-black graphite", (0.004, 0.006, 0.009), 0.66, metallic=0.015)
    eye = make_material("Compound eyes · deep scarlet", (0.16, 0.002, 0.009), 0.32, metallic=0.01)
    wing = make_material("Wing membrane · pale blue glass", (0.48, 0.70, 0.91), 0.48, alpha=0.14)
    wing_shader = wing.node_tree.nodes.get("Principled BSDF")
    wing_shader.inputs["Emission Color"].default_value = (0.34, 0.54, 0.78, 1.0)
    wing_shader.inputs["Emission Strength"].default_value = 0.28
    hair = make_material("Fine cuticular setae", (0.026, 0.034, 0.042), 0.62, metallic=0.02)
    for obj in meshes:
        if obj.name == "Drosophila_Compound_Eyes":
            selected = eye
        elif "Wing_" in obj.name:
            selected = wing
        else:
            selected = body
        obj.data.materials.clear()
        obj.data.materials.append(selected)
        for poly in obj.data.polygons:
            poly.material_index = 0


def add_fine_setae(meshes: list[bpy.types.Object]) -> bpy.types.Object:
    """Add sparse, fine anatomical hairs as one light-weight mesh."""
    rng = random.Random(4702)
    body_parts = [obj for obj in meshes
                  if obj.name != "Drosophila_Compound_Eyes" and "Wing_" not in obj.name]
    vertices: list[tuple[Vector, Vector, float]] = []
    for obj in body_parts:
        obj.data.update()
        count = max(18, min(180, len(obj.data.vertices) // 110))
        step = max(1, len(obj.data.vertices) // count)
        for index in range(0, len(obj.data.vertices), step):
            vertex = obj.data.vertices[index]
            normal = (obj.matrix_world.to_3x3() @ vertex.normal).normalized()
            if normal.length < 0.5:
                continue
            # Short bristles on limbs, slightly longer tactile setae on thorax
            # and abdomen. The small spread keeps the scan silhouette natural.
            length = rng.uniform(0.025, 0.052)
            vertices.append((obj.matrix_world @ vertex.co, normal, length))

    coords: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    sides = 4
    for point, normal, length in vertices:
        tangent = normal.cross(Vector((0, 0, 1)))
        if tangent.length < 0.05:
            tangent = normal.cross(Vector((0, 1, 0)))
        tangent.normalize()
        bitangent = normal.cross(tangent).normalized()
        tip = point + normal * length
        base_radius = 0.0065
        tip_index = len(coords)
        coords.append(tuple(tip))
        ring_start = len(coords)
        for side in range(sides):
            angle = (side / sides) * 6.28318530718
            radial = tangent * __import__("math").cos(angle) + bitangent * __import__("math").sin(angle)
            coords.append(tuple(point + radial * base_radius))
        for side in range(sides):
            a = ring_start + side
            b = ring_start + (side + 1) % sides
            faces.append((tip_index, a, b))

    data = bpy.data.meshes.new("Fine cuticular setae mesh")
    data.from_pydata(coords, [], faces)
    data.update()
    hairs = bpy.data.objects.new("Drosophila_Fine_Setae", data)
    bpy.context.scene.collection.objects.link(hairs)
    hairs.data.materials.append(bpy.data.materials.get("Fine cuticular setae"))
    for poly in data.polygons:
        poly.use_smooth = True
    return hairs


def v3(value: Vector | np.ndarray) -> Vector:
    return value if isinstance(value, Vector) else Vector(value.tolist())


def new_bone(armature: bpy.types.Armature, name: str, head: Vector,
             tail: Vector, parent: bpy.types.EditBone) -> bpy.types.EditBone:
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail if (tail - head).length > 0.01 else head + Vector((0, 0.05, 0))
    bone.parent = parent
    bone.use_connect = False
    return bone


def rig(meshes: list[bpy.types.Object]) -> bpy.types.Object:
    bounds_min = Vector(tuple(min(v.co[i] for obj in meshes for v in obj.data.vertices) for i in range(3)))
    bounds_max = Vector(tuple(max(v.co[i] for obj in meshes for v in obj.data.vertices) for i in range(3)))
    bounds_size = bounds_max - bounds_min
    center = (bounds_min + bounds_max) * 0.5

    # The named source meshes identify the two independently modeled wings.
    wings = [obj for obj in meshes if "Wing_" in obj.name]
    body_parts = [obj for obj in meshes if obj.name not in {"Drosophila_Compound_Eyes"}
                  and "Wing_" not in obj.name]
    body_vertices = [obj.matrix_world @ Vector(tuple(v.co))
                     for obj in body_parts for v in obj.data.vertices]
    body_center = sum(body_vertices, Vector()) / max(1, len(body_vertices))

    armature_data = bpy.data.armatures.new("Drosophila preview skeleton")
    armature = bpy.data.objects.new("DrosophilaPreviewRig", armature_data)
    bpy.context.scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    for obj in meshes:
        obj.select_set(False)
    bpy.ops.object.mode_set(mode="EDIT")
    root = armature_data.edit_bones.new("root")
    root.head = body_center
    root.tail = body_center + Vector((0, 0, 0.18))

    wing_bones: dict[str, bpy.types.EditBone] = {}
    for obj in wings:
        coords = [Vector(tuple(v.co)) for v in obj.data.vertices]
        nearest_index = min(range(len(coords)), key=lambda i: (coords[i] - body_center).length)
        root_point = coords[nearest_index]
        tip_point = max(coords, key=lambda p: (p - root_point).length)
        bone_name = "wing_left" if obj.name.endswith("_L") else "wing_right"
        wing_bones[bone_name] = new_bone(armature_data, bone_name, root_point, tip_point, root)

    # Two compact, independent foreleg controls drive the rubbing/grooming
    # motion. Vertex falloff is tied only to the corresponding scan surface.
    center_vec = center
    front_legs: dict[str, list[tuple[Vector, Vector, str]]] = {"left": [], "right": []}
    for sign, side in [(-1.0, "left"), (1.0, "right")]:
        hip = Vector((center_vec.x + sign * bounds_size.x * 0.035,
                      bounds_min.y + bounds_size.y * 0.34,
                      bounds_min.z + bounds_size.z * 0.54))
        elbow = Vector((center_vec.x + sign * bounds_size.x * 0.16,
                        bounds_min.y + bounds_size.y * 0.27,
                        bounds_min.z + bounds_size.z * 0.38))
        foot = Vector((center_vec.x + sign * bounds_size.x * 0.23,
                       bounds_min.y + bounds_size.y * 0.17,
                       bounds_min.z + bounds_size.z * 0.24))
        upper_name = f"foreleg_upper_{side}"
        lower_name = f"foreleg_lower_{side}"
        upper = new_bone(armature_data, upper_name, hip, elbow, root)
        new_bone(armature_data, lower_name, elbow, foot, upper)
        front_legs[side].extend([(hip, elbow, upper_name), (elbow, foot, lower_name)])

    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in meshes:
        group_weights: dict[str, np.ndarray] = {}
        coords = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", coords)
        points = coords.reshape((-1, 3))
        root_weight = np.ones(len(points), dtype=np.float64)

        if obj in wings:
            bone_name = "wing_left" if obj.name.endswith("_L") else "wing_right"
            group_weights[bone_name] = np.ones(len(points), dtype=np.float64)
            root_weight.fill(0.0)
        else:
            for side, segments in front_legs.items():
                for start, end, bone_name in segments:
                    delta = np.asarray(end - start, dtype=np.float64)
                    p = points - np.asarray(start, dtype=np.float64)
                    t = np.clip((p @ delta) / max(float(delta @ delta), 1e-9), 0.0, 1.0)
                    dist = np.linalg.norm(p - t[:, None] * delta, axis=1)
                    falloff = np.clip(1.0 - dist / 0.25, 0.0, 1.0) ** 2
                    group_weights[bone_name] = falloff
                    root_weight = np.minimum(root_weight, 1.0 - falloff)
        group_weights["root"] = root_weight

        obj.parent = armature
        obj.matrix_parent_inverse = armature.matrix_world.inverted()
        mod = obj.modifiers.new("Drosophila preview articulation", "ARMATURE")
        mod.object = armature
        obj.vertex_groups.clear()
        groups = {name: obj.vertex_groups.new(name=name) for name in group_weights}
        for name, values in group_weights.items():
            buckets = np.clip(np.rint(values * 100.0), 0, 100).astype(np.uint8)
            for bucket in np.unique(buckets):
                if bucket == 0:
                    continue
                indices = np.flatnonzero(buckets == bucket).tolist()
                groups[name].add(indices, float(bucket) / 100.0, "REPLACE")
    return armature


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Missing selected licensed model: {SOURCE}")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    meshes = import_meshes()
    add_materials(meshes)
    hairs = add_fine_setae(meshes)
    meshes.append(hairs)
    rig_obj = rig(meshes)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    rig_obj.select_set(True)
    bpy.context.view_layer.objects.active = rig_obj
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT), export_format="GLB", export_apply=True,
        export_skins=True, export_animations=False, export_materials="EXPORT",
        export_image_format="AUTO",
    )
    total = sum(len(obj.data.polygons) for obj in meshes)
    print(f"Wrote {OUTPUT}; {len(meshes)} mesh objects; {total:,} faces")


if __name__ == "__main__":
    main()
