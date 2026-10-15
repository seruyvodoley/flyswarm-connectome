class_name VehicleAppearance
extends RefCounted

const LIVERY_SHADER = preload("res://shaders/vehicle_livery.gdshader")

# Visual approximations for the 1944-45 theatre, NOT sampled or certified RAL/4BO
# standards.  See docs/vehicle_art_reference_audit.md for evidence and limitations.
# 0 = wartime Soviet single-colour green, 1 = field-applied German three-colour
# bands, 2 = late-1944 German spotted three-colour (Hinterhalt-inspired).
const PROFILES = {
	"t34_85":   {"base": Color("424c32"), "secondary": Color("424c32"), "tertiary": Color("424c32"), "style": 0, "scale": 1.0, "wear": 0.25},
	"panther_g": {"base": Color("aa9a72"), "secondary": Color("4d5b45"), "tertiary": Color("785541"), "style": 2, "scale": 0.85, "wear": 0.25},
	"tiger_i":  {"base": Color("ac9c73"), "secondary": Color("566347"), "tertiary": Color("74523d"), "style": 1, "scale": 1.1, "wear": 0.30},
	"is2_1944": {"base": Color("3d4931"), "secondary": Color("3d4931"), "tertiary": Color("3d4931"), "style": 0, "scale": 1.0, "wear": 0.27},
	"jagdpanther":{"base": Color("af9d74"), "secondary": Color("4e5941"), "tertiary": Color("75513c"), "style": 1, "scale": 0.90, "wear": 0.29},
	"su100":    {"base": Color("404c33"), "secondary": Color("404c33"), "tertiary": Color("404c33"), "style": 0, "scale": 1.0, "wear": 0.29},
}

static func apply(model: Node3D, vehicle_id: String, destroyed: bool = false) -> int:
	if not PROFILES.has(vehicle_id):
		push_warning("No vehicle livery profile for %s" % vehicle_id)
		return 0
	var profile: Dictionary = PROFILES[vehicle_id]
	var count := 0
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh == null:
			continue
		var mesh_to_model := relative_transform(model, mesh_instance)
		for surface in mesh_instance.mesh.get_surface_count():
			var source := mesh_instance.mesh.surface_get_material(surface)
			var instance_source := mesh_instance.get_surface_override_material(surface)
			if instance_source != null and not instance_source is ShaderMaterial:
				source = instance_source
			if source is StandardMaterial3D and source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				continue
			# Do not paint road wheels as dark track steel: this was a major
			# source of visually flat running gear in the original livery.
			var name := source.resource_name.to_lower() if source else ""
			var part := mesh_instance.name.to_lower()
			var kind := 0
			if name.contains("recess") or part.contains("recess") or part.contains("bore"):
				kind = 2
			elif name.contains("rubber") or part.contains("tyre") or part.contains("tire"):
				kind = 4
			elif part.contains("track") or part.contains("shoe") or part.contains("guidehorn") or part.contains("crossrib") or part.contains("drive tooth"):
				kind = 1
			elif part.contains("wheel") or part.contains("hub") or part.contains("sprocket") or part.contains("idler"):
				kind = 3
			elif name.contains("track"):
				kind = 1
			var material := ShaderMaterial.new()
			material.shader = LIVERY_SHADER
			material.set_shader_parameter("mesh_to_model", mesh_to_model)
			material.set_shader_parameter("source_tint", source.albedo_color if source is StandardMaterial3D else Color.WHITE)
			var arrays := mesh_instance.mesh.surface_get_arrays(surface)
			var has_uv := arrays.size() > Mesh.ARRAY_TEX_UV and arrays[Mesh.ARRAY_TEX_UV] is PackedVector2Array and not (arrays[Mesh.ARRAY_TEX_UV] as PackedVector2Array).is_empty()
			var texture: Texture2D = source.albedo_texture if source is StandardMaterial3D else null
			var normal: Texture2D = source.normal_texture if source is StandardMaterial3D else null
			var roughness_map: Texture2D = source.roughness_texture if source is StandardMaterial3D else null
			material.set_shader_parameter("has_source_texture", has_uv and texture != null)
			material.set_shader_parameter("has_source_normal", has_uv and normal != null)
			material.set_shader_parameter("has_source_roughness", has_uv and roughness_map != null)
			if has_uv and texture != null:material.set_shader_parameter("source_texture", texture)
			if has_uv and normal != null:material.set_shader_parameter("source_normal", normal)
			if has_uv and roughness_map != null:material.set_shader_parameter("source_roughness_map", roughness_map)
			material.set_shader_parameter("source_roughness", source.roughness if source is StandardMaterial3D else 0.82)
			material.set_shader_parameter("source_metallic", source.metallic if source is StandardMaterial3D else 0.12)
			material.set_shader_parameter("paint_base", profile.base)
			material.set_shader_parameter("paint_secondary", profile.secondary)
			material.set_shader_parameter("paint_tertiary", profile.tertiary)
			material.set_shader_parameter("pattern_style", profile.style)
			material.set_shader_parameter("pattern_scale", profile.scale)
			material.set_shader_parameter("material_kind", kind)
			material.set_shader_parameter("weathering", profile.wear)
			material.set_shader_parameter("charred", destroyed)
			mesh_instance.set_surface_override_material(surface, material)
			count += 1
	return count

static func relative_transform(ancestor: Node3D, descendant: Node3D) -> Transform3D:
	# Resource previews can render before their SubViewport joins the scene tree;
	# local ancestry is stable in both that case and the live battle scene.
	var result := Transform3D.IDENTITY
	var current: Node3D = descendant
	while current != ancestor and current != null:
		result = current.transform * result
		current = current.get_parent() as Node3D
	return result

static func set_destroyed(model: Node3D, vehicle_id: String, destroyed: bool) -> void:
	apply(model, vehicle_id, destroyed)
