class_name VehicleAppearance
extends RefCounted

const LIVERY_SHADER = preload("res://shaders/vehicle_livery.gdshader")

const PROFILES = {
	"t34_85": {"base": Color("3c4b2c"), "secondary": Color("485638"), "tertiary": Color("66513b"), "style": 0, "wear": 0.30},
	"panther_g": {"base": Color("b5a06a"), "secondary": Color("526346"), "tertiary": Color("76503a"), "style": 1, "wear": 0.23},
	"tiger_i": {"base": Color("b49c62"), "secondary": Color("66704a"), "tertiary": Color("72523a"), "style": 2, "wear": 0.42},
	"is2_1944": {"base": Color("34462c"), "secondary": Color("425536"), "tertiary": Color("62503a"), "style": 0, "wear": 0.34},
	"jagdpanther": {"base": Color("b6a16e"), "secondary": Color("59694b"), "tertiary": Color("76503c"), "style": 1, "wear": 0.30},
	"su100": {"base": Color("3b4b2f"), "secondary": Color("48563a"), "tertiary": Color("635039"), "style": 0, "wear": 0.28},
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
		var mesh_to_model: Transform3D = model.global_transform.affine_inverse() * mesh_instance.global_transform
		for surface in mesh_instance.mesh.get_surface_count():
			var source := mesh_instance.mesh.surface_get_material(surface)
			var instance_source := mesh_instance.get_surface_override_material(surface)
			if instance_source != null and not instance_source is ShaderMaterial:
				source = instance_source
			if source is StandardMaterial3D and source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED:
				continue
			var name := source.resource_name.to_lower() if source else ""
			var kind := 0
			if name.contains("recess") or name.contains("rubber"):
				kind = 2 if name.contains("recess") else 1
			elif name.contains("track") or name.contains("wheel"):
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
			material.set_shader_parameter("material_kind", kind)
			material.set_shader_parameter("weathering", profile.wear)
			material.set_shader_parameter("charred", destroyed)
			mesh_instance.set_surface_override_material(surface, material)
			count += 1
	return count

static func set_destroyed(model: Node3D, vehicle_id: String, destroyed: bool) -> void:
	apply(model, vehicle_id, destroyed)
