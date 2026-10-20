"""Generate FlySwarm's original Drosophila melanogaster male preview mesh.

The mesh is authored from scratch with Blender primitives and curve-built anatomy.
It is a visual educational model and does not participate in MaleCNS calculations.
Run with Blender 4.5+ in background mode from the repository root.
"""

import math
import random
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "frontend/godot/assets/environment/fly/fly.glb"
random.seed(41)


def make_material(name, color, roughness=0.38, metallic=0.0, alpha=1.0, coat=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, alpha)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Alpha"].default_value = alpha
    if "Coat Weight" in shader.inputs:
        shader.inputs["Coat Weight"].default_value = coat
        shader.inputs["Coat Roughness"].default_value = 0.24
    if alpha < 1.0:
        # Blender's dithered transparency exported as a speckled membrane in
        # the Godot preview. BLENDED maps to glTF alphaMode=BLEND.
        material.surface_render_method = "BLENDED"
    material.use_backface_culling = False
    return material


def init_materials():
    global CHITIN, THORAX, GOLD, DARK, LEG, JOINT, EYE, FACETS, WING, VEIN, BRISTLE, HALTERE, BODY_MATERIALS
    CHITIN = make_material("Cuticle · umber", (0.16, 0.078, 0.039), 0.48, 0.015, coat=0.045)
    THORAX = make_material("Thorax · chestnut amber", (0.34, 0.18, 0.072), 0.5, 0.012, coat=0.05)
    GOLD = make_material("Abdominal tergites · ochre", (0.46, 0.29, 0.12), 0.52, 0.0, coat=0.035)
    DARK = make_material("Abdominal terminal segments", (0.105, 0.038, 0.026), 0.48, 0.01, coat=0.05)
    LEG = make_material("Legs · dark amber", (0.24, 0.105, 0.044), 0.5, 0.0, coat=0.035)
    JOINT = make_material("Leg joints", (0.15, 0.06, 0.03), 0.5)
    EYE = make_material("Compound eye · deep carmine", (0.22, 0.008, 0.016), 0.36, 0.005, coat=0.12)
    FACETS = [
        make_material("Ommatidium · carmine", (0.36, 0.012, 0.022), 0.34, 0.003, coat=0.12),
        make_material("Ommatidium · ruby", (0.22, 0.006, 0.014), 0.36, 0.003, coat=0.11),
        make_material("Ommatidium · glint", (0.48, 0.035, 0.04), 0.32, 0.0, coat=0.14),
    ]
    WING = make_material("Wing membrane · translucent amber", (0.48, 0.40, 0.28), 0.66, 0.0, alpha=0.30)
    VEIN = make_material("Wing veins · ochre", (0.27, 0.15, 0.065), 0.56)
    BRISTLE = make_material("Sensory bristles", (0.105, 0.051, 0.026), 0.65)
    HALTERE = make_material("Halteres · amber", (0.56, 0.37, 0.17), 0.48, 0.0, coat=0.04)
    BODY_MATERIALS = []
    for name, color in [("Body ochre", (0.46, 0.29, 0.12)),
                        ("Body terminal umber", (0.105, 0.038, 0.026)),
                        ("Body thorax", (0.34, 0.18, 0.072)),
                        ("Body head", (0.16, 0.078, 0.039))]:
        material = make_material(name, color, 0.56, 0.012, coat=0.035)
        BODY_MATERIALS.append(material)


def uv_sphere(name, center, scale, material, segments=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def tapered_segment(name, a, b, radius_a, radius_b, material, vertices=12):
    start, end = Vector(a), Vector(b)
    direction = end - start
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius_a,
        radius2=radius_b,
        depth=direction.length,
        location=(start + end) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def tube_curve(name, points, radius, material, resolution=2):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = resolution
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinate in zip(spline.points, points):
        point.co = (*coordinate, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def make_faceted_eye(name, center, radii, side):
    center = Vector(center)
    rx, ry, rz = radii
    vertices, faces, material_ids = [], [], []
    rows, columns = 17, 31
    for row in range(rows):
        latitude = -0.94 + 1.88 * row / (rows - 1)
        for column in range(columns):
            longitude = -1.34 + 2.68 * column / (columns - 1)
            cp, sp = math.cos(latitude), math.sin(latitude)
            sl, cl = math.sin(longitude), math.cos(longitude)
            point = Vector((center.x + rx * cp * sl, center.y + side * ry * cp * cl, center.z + rz * sp))
            normal = Vector((cp * sl / rx, side * cp * cl / ry, sp / rz)).normalized()
            tangent = normal.cross(Vector((0, 0, 1)))
            if tangent.length < 0.1:
                tangent = normal.cross(Vector((1, 0, 0)))
            tangent.normalize()
            bitangent = normal.cross(tangent).normalized()
            point += normal * 0.006
            radius = 0.0065
            base = len(vertices)
            for depth in (-0.003, 0.003):
                for corner in range(6):
                    angle = 2.0 * math.pi * corner / 6.0
                    p = point + normal * depth + radius * (math.cos(angle) * tangent + math.sin(angle) * bitangent)
                    vertices.append(tuple(p))
            faces.append(tuple(base + i for i in range(5, -1, -1)))
            material_ids.append(random.choices([0, 1, 2], [0.52, 0.36, 0.12])[0])
            faces.append(tuple(base + 6 + i for i in range(6)))
            material_ids.append(material_ids[-1])
            for corner in range(6):
                nxt = (corner + 1) % 6
                faces.append((base + corner, base + nxt, base + 6 + nxt, base + 6 + corner))
                material_ids.append(material_ids[-1])
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.clear()
    for material in FACETS:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for polygon, material_index in zip(mesh.polygons, material_ids):
        polygon.material_index = material_index
    return obj


def make_wing(side, root):
    label = "L" if side < 0 else "R"
    pivot = bpy.data.objects.new("WingPivot_" + label, None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = (0.06, side * 0.17, 0.30)
    pivot.parent = root

    def local_point(t, across=0.0):
        width = 0.255 * (math.sin(math.pi * t) ** 0.82)
        return Vector((-0.66 * t + 0.34 * across * width,
                       side * (1.42 * t + 0.13 * across * width),
                       0.10 * math.sin(math.pi * t) + 0.035 * across * width))

    verts, faces = [], []
    longitudinal, crosswise = 24, 8
    for i in range(longitudinal + 1):
        t = i / longitudinal
        for j in range(crosswise + 1):
            across = -1.0 + 2.0 * j / crosswise
            verts.append(tuple(local_point(t, across)))
    for i in range(longitudinal):
        for j in range(crosswise):
            a = i * (crosswise + 1) + j
            b = a + crosswise + 1
            face = (a, a + 1, b + 1, b)
            faces.append(face if side > 0 else tuple(reversed(face)))
    mesh = bpy.data.meshes.new("Wing membrane " + label)
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(WING)
    for poly in mesh.polygons:
        poly.use_smooth = True
    membrane = bpy.data.objects.new("WingMembrane_" + label, mesh)
    bpy.context.collection.objects.link(membrane)
    membrane.parent = pivot
    membrane.data.materials[0].use_backface_culling = False

    # Leading/trailing edges and the costa, subcosta and radial cross-veins.
    veins = []
    for edge in (-0.96, 0.0, 0.96):
        points = [local_point(i / 24.0, edge) for i in range(25)]
        veins.append(tube_curve("WingVein_" + label, points, 0.0042 if edge == 0 else 0.0032, VEIN))
    for index in range(1, 7):
        t = index / 8.0
        start = local_point(t, 0.0)
        end_t = min(0.97, t + 0.24)
        end = local_point(end_t, 0.91 if index % 2 else -0.91)
        mid = local_point((t + end_t) * 0.5, 0.62 if index % 2 else -0.62)
        veins.append(tube_curve("WingCrossvein_" + label, [start, mid, end], 0.0025, VEIN, 1))
    for vein in veins:
        vein.parent = pivot
    return pivot


def join_by_material(objects, root):
    buckets = {}
    for obj in objects:
        if obj.type != "MESH" or not obj.data.materials:
            continue
        key = obj.data.materials[0].name
        buckets.setdefault(key, []).append(obj)
    for name, group in buckets.items():
        if len(group) == 1:
            active = group[0]
        else:
            bpy.ops.object.select_all(action="DESELECT")
            for obj in group:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = group[0]
            bpy.ops.object.join()
            active = bpy.context.object
        active.name = "Anatomy_" + name.replace(" ", "_").replace("·", "")
        active.parent = root


def profile_body():
    """One continuous cuticle surface, with natural taper and male tergite bands."""
    profile = [
        (-1.34, 0.025, 0.035, -0.045), (-1.25, 0.090, 0.100, -0.045),
        (-1.08, 0.160, 0.165, -0.040), (-0.88, 0.205, 0.200, -0.030),
        (-0.67, 0.235, 0.220, -0.015), (-0.46, 0.255, 0.230, 0.005),
        (-0.27, 0.275, 0.250, 0.018), (-0.10, 0.340, 0.300, 0.020),
        (0.08, 0.365, 0.330, 0.025), (0.24, 0.315, 0.290, 0.038),
        (0.40, 0.205, 0.205, 0.060), (0.51, 0.180, 0.195, 0.078),
        (0.63, 0.235, 0.245, 0.085), (0.78, 0.275, 0.290, 0.088),
        (0.91, 0.235, 0.250, 0.070), (1.00, 0.115, 0.135, 0.035),
        (1.035, 0.018, 0.030, 0.005),
    ]
    rings, radial = 180, 64

    def sample(t):
        i = min(int(t), len(profile) - 2)
        u = t - i
        p0 = profile[max(0, i - 1)]
        p1 = profile[i]
        p2 = profile[i + 1]
        p3 = profile[min(len(profile) - 1, i + 2)]
        values = []
        for c in range(4):
            values.append(0.5 * ((2 * p1[c]) + (-p0[c] + p2[c]) * u
                                 + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * u * u
                                 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * u * u * u))
        return values

    vertices, faces = [], []
    for i in range(rings + 1):
        x, ry, rz, zc = sample((len(profile) - 1) * i / rings)
        for j in range(radial):
            a = math.tau * j / radial
            vertices.append((x, ry * math.sin(a), zc + rz * math.cos(a)))
    for i in range(rings):
        for j in range(radial):
            a = i * radial + j
            b = i * radial + (j + 1) % radial
            c = (i + 1) * radial + (j + 1) % radial
            d = (i + 1) * radial + j
            faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new("Continuous adult male body")
    mesh.from_pydata(vertices, [], faces)
    for material in BODY_MATERIALS:
        mesh.materials.append(material)
    body = bpy.data.objects.new("Continuous male cuticle", mesh)
    bpy.context.collection.objects.link(body)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        x = sum(mesh.vertices[index].co.x for index in polygon.vertices) / len(polygon.vertices)
        if x < -1.02:
            polygon.material_index = 1
        elif x < -0.28:
            segment_edges = (-1.00, -0.81, -0.62, -0.43)
            polygon.material_index = 1 if any(abs(x - edge) < 0.018 for edge in segment_edges) else 0
        else:
            polygon.material_index = 2 if x < 0.48 else 3

    # Fine raised tergite margins sit on the surface; they do not split the body mesh.
    body_parts = [body]
    for x in (-1.00, -0.81, -0.62, -0.43):
        point = min(range(len(profile) - 1), key=lambda i: abs(profile[i][0] - x))
        _, ry, rz, zc = profile[point]
        points = [(x, ry * math.sin(math.tau * j / 96), zc + rz * math.cos(math.tau * j / 96)) for j in range(97)]
        seam = tube_curve("Tergite suture", points, 0.0034, DARK if x < -0.81 else CHITIN, 1)
        seam.parent = body
        body_parts.append(seam)
    return body_parts


def swept_leg(name, path, radii, material, sides=12):
    """Smooth tapered leg mesh following a curved, jointed centerline."""
    samples = []
    for i in range(len(path) - 1):
        p0 = Vector(path[max(0, i - 1)])
        p1 = Vector(path[i])
        p2 = Vector(path[i + 1])
        p3 = Vector(path[min(len(path) - 1, i + 2)])
        for step in range(5):
            t = step / 5.0
            t2, t3 = t * t, t * t * t
            point = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2*p0 - 5*p1 + 4*p2 - p3)*t2 + (-p0 + 3*p1 - 3*p2 + p3)*t3)
            r0, r1, r2, r3 = radii[max(0, i-1)], radii[i], radii[i+1], radii[min(len(radii)-1, i+2)]
            radius = max(0.003, 0.5 * ((2*r1) + (-r0+r2)*t + (2*r0-5*r1+4*r2-r3)*t2 + (-r0+3*r1-3*r2+r3)*t3))
            samples.append((point, radius))
    samples.append((Vector(path[-1]), radii[-1]))
    vertices, faces = [], []
    for index, (point, radius) in enumerate(samples):
        tangent = (samples[min(index + 1, len(samples)-1)][0] - samples[max(0, index - 1)][0]).normalized()
        axis = tangent.cross(Vector((0, 0, 1)))
        if axis.length < 0.1:
            axis = tangent.cross(Vector((0, 1, 0)))
        axis.normalize()
        other = tangent.cross(axis).normalized()
        for j in range(sides):
            a = math.tau * j / sides
            v = point + radius * (math.cos(a) * axis + math.sin(a) * other)
            vertices.append(tuple(v))
    for i in range(len(samples) - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            c = (i + 1) * sides + (j + 1) % sides
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    init_materials()
    scene = bpy.context.scene
    root = bpy.data.objects.new("Drosophila_melanogaster_male", None)
    bpy.context.collection.objects.link(root)
    anatomy = []

    # One continuous, adult-male body silhouette with seven abdominal tergites.
    anatomy.extend(profile_body())

    # Paired faceted eyes, three ocelli, mouthparts and fine aristae.
    eye_radii = (0.184, 0.132, 0.198)
    for side, suffix in [(-1, "L"), (1, "R")]:
        eye_center = (0.73, side * 0.247, 0.105)
        anatomy.append(uv_sphere("Compound eye base " + suffix, eye_center, eye_radii, EYE, 36, 24))
        anatomy.append(make_faceted_eye("Ommatidial facets " + suffix, eye_center, eye_radii, side))
        anatomy.append(uv_sphere("Lateral ocellus " + suffix, (0.79, side * 0.055, 0.325), (0.014, 0.013, 0.014), HALTERE, 12, 8))
        arista_base = (0.91, side * 0.075, 0.25)
        anatomy.append(tube_curve("Arista " + suffix, [arista_base, (1.00, side * 0.11, 0.34), (1.16, side * 0.14, 0.38)], 0.0035, LEG))
        for n in range(4):
            t = n / 4.0
            p = Vector(arista_base).lerp(Vector((1.16, side * 0.14, 0.38)), t)
            anatomy.append(tube_curve("Arista branch " + suffix, [p, p + Vector((0.018, side * 0.009, 0.024))], 0.0012, BRISTLE, 1))
    anatomy.append(uv_sphere("Median ocellus", (0.80, 0.0, 0.337), (0.014, 0.012, 0.014), HALTERE, 12, 8))
    anatomy.append(uv_sphere("Frons", (0.93, 0.0, 0.026), (0.065, 0.105, 0.087), THORAX, 24, 16))
    anatomy.append(uv_sphere("Rostrum", (0.985, 0.0, -0.105), (0.043, 0.058, 0.047), CHITIN, 20, 12))
    for side in (-1, 1):
        anatomy.append(tube_curve("Maxillary palp", [(0.92, side * 0.085, -0.11), (0.99, side * 0.12, -0.18), (1.045, side * 0.115, -0.15)], 0.0048, LEG))

    # Scutellum sits on the dorsal posterior thorax, not as a second body sphere.
    anatomy.append(uv_sphere("Scutellum", (-0.245, 0.0, 0.235), (0.105, 0.205, 0.075), CHITIN, 32, 20))
    for side in (-1, 1):
        anatomy.append(tube_curve("Haltere stalk", [(-0.24, side * 0.255, 0.11), (-0.34, side * 0.29, 0.17), (-0.405, side * 0.30, 0.19)], 0.011, LEG))
        anatomy.append(uv_sphere("Haltere knob", (-0.42, side * 0.30, 0.19), (0.038, 0.031, 0.026), HALTERE, 18, 12))

    # Three bilateral leg pairs with continuous, tapered femur-to-tarsus contours.
    leg_paths = {
        "Fore": [(0.12, 0.24, -0.16), (0.25, 0.37, -0.21), (0.45, 0.52, -0.28), (0.62, 0.61, -0.43), (0.60, 0.77, -0.60), (0.77, 0.96, -0.71), (0.92, 1.04, -0.80)],
        "Mid": [(-0.02, 0.25, -0.17), (-0.05, 0.40, -0.23), (-0.09, 0.62, -0.32), (-0.04, 0.72, -0.47), (0.02, 0.84, -0.64), (0.13, 1.02, -0.73), (0.19, 1.12, -0.81)],
        "Hind": [(-0.18, 0.23, -0.17), (-0.26, 0.39, -0.22), (-0.43, 0.56, -0.29), (-0.57, 0.64, -0.44), (-0.52, 0.81, -0.60), (-0.70, 0.99, -0.67), (-0.88, 1.04, -0.74)],
    }
    for label, points in leg_paths.items():
        for side, suffix in [(-1, "L"), (1, "R")]:
            path = [(x, side * y, z) for x, y, z in points]
            anatomy.append(swept_leg(label + " articulated leg " + suffix, path, [0.042, 0.036, 0.034, 0.026, 0.019, 0.011, 0.006], LEG))
            for joint_index in (1, 3, 5):
                x, y, z = points[joint_index]
                anatomy.append(uv_sphere(label + " joint " + suffix, (x, side * y, z), (0.021, 0.020, 0.020), JOINT, 14, 10))
            foot = Vector(path[-1])
            for claw_side in (-1, 1):
                claw = [(foot.x, foot.y, foot.z), (foot.x + 0.018, foot.y + claw_side * 0.018, foot.z - 0.015), (foot.x + 0.04, foot.y + claw_side * 0.028, foot.z - 0.012)]
                anatomy.append(tube_curve(label + " paired pretarsal claw", claw, 0.0033, CHITIN, 1))

    # Thoracic and abdominal setae; short, sparse hairs catch light without becoming spikes.
    for index in range(104):
        x = random.uniform(-0.12, 0.24)
        y = random.uniform(-0.24, 0.24)
        z = 0.025 + 0.33 * math.sqrt(max(0.05, 1.0 - ((x - 0.08) / 0.365) ** 2 - (y / 0.365) ** 2))
        direction = Vector((random.uniform(-0.15, 0.12), random.uniform(-0.15, 0.15), random.uniform(0.8, 1.0))).normalized()
        start = Vector((x, y, z - 0.01))
        end = start + direction * random.uniform(0.018, 0.032)
        anatomy.append(tube_curve("Thoracic microchaete", [start, start.lerp(end, 0.6), end], 0.00105, BRISTLE, 1))

    # A single homologous wing pair, each with a translucent membrane and raised venation.
    wings = [make_wing(-1, root), make_wing(1, root)]
    # Convert curve bevels into meshes before joining by material to keep draw calls low.
    for group in [anatomy] + [[child for child in wing.children if child.type == "CURVE"] for wing in wings]:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in group:
            if obj.type == "CURVE":
                obj.select_set(True)
        selected = list(bpy.context.selected_objects)
        if selected:
            bpy.context.view_layer.objects.active = selected[0]
            bpy.ops.object.convert(target="MESH")
    join_by_material(anatomy, root)
    for wing in wings:
        wing.rotation_mode = "XYZ"
        join_by_material([child for child in wing.children if child.type == "MESH"], wing)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(
        filepath=str(OUTPUT),
        export_format="GLB",
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_keep_originals=False,
    )
    print("Wrote %s (%d meshes)" % (OUTPUT, sum(obj.type == "MESH" for obj in scene.objects)))


if __name__ == "__main__":
    build()
