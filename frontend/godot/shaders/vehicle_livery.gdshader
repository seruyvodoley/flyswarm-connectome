shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform mat4 mesh_to_model = mat4(1.0);
uniform vec4 source_tint : source_color = vec4(0.62, 0.64, 0.60, 1.0);
uniform sampler2D source_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D source_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D source_roughness_map : filter_linear_mipmap, repeat_enable;
uniform bool has_source_texture = false;
uniform bool has_source_normal = false;
uniform bool has_source_roughness = false;
uniform vec4 paint_base : source_color = vec4(0.22, 0.28, 0.16, 1.0);
uniform vec4 paint_secondary : source_color = vec4(0.28, 0.34, 0.20, 1.0);
uniform vec4 paint_tertiary : source_color = vec4(0.30, 0.20, 0.12, 1.0);
uniform float source_roughness : hint_range(0.0, 1.0) = 0.82;
uniform float source_metallic : hint_range(0.0, 1.0) = 0.18;
uniform int pattern_style = 0;
uniform int material_kind = 0; // 0 armour, 1 track, 2 recess
uniform float weathering = 0.25;
uniform bool charred = false;

varying vec3 model_position;
varying vec2 surface_uv;

void vertex() {
	model_position = (mesh_to_model * vec4(VERTEX, 1.0)).xyz;
	surface_uv = UV;
}

float field(vec3 p) {
	return sin(p.x * 2.13 + sin(p.y * 1.71 + p.z * 0.55) * 1.05)
		+ 0.58 * sin(p.z * 2.62 - p.y * 1.83 + sin(p.x * 1.11) * 0.82)
		+ 0.26 * sin((p.x + p.z) * 4.1 + p.y * 2.0);
}

void fragment() {
	vec4 texel = source_tint;
	if (has_source_texture) {
		texel *= texture(source_texture, surface_uv);
	}
	vec3 color = texel.rgb;
	float rough = source_roughness;
	float metal = source_metallic;
	float grit = sin(dot(floor(model_position * 53.0), vec3(12.9898, 78.233, 37.719)));
	float dirt_band = 1.0 - smoothstep(0.08, 0.88, model_position.y + grit * 0.08);
	float fine_wear = smoothstep(0.965, 0.995, sin(model_position.x * 46.0 + sin(model_position.z * 5.0) * 2.0) * 0.5 + 0.5);

	if (material_kind == 0) {
		color *= paint_base.rgb / max(source_tint.rgb, vec3(0.08));
		if (pattern_style == 1) {
			float patches = field(model_position);
			color = mix(paint_base.rgb, paint_secondary.rgb, smoothstep(-0.16, 0.40, patches));
			color = mix(color, paint_tertiary.rgb, smoothstep(0.92, 1.22, patches + 0.18 * sin(model_position.z * 1.7)));
		} else if (pattern_style == 2) {
			float patches = field(model_position * vec3(0.92, 1.06, 0.88));
			color = mix(paint_base.rgb, paint_secondary.rgb, smoothstep(-0.08, 0.42, patches));
			color = mix(color, paint_tertiary.rgb, smoothstep(0.90, 1.20, patches + 0.22 * sin(model_position.x * 1.3)));
		}
		float dust = dirt_band * weathering * 0.30;
		color = mix(color, vec3(0.34, 0.29, 0.20), dust);
		color = mix(color, vec3(0.43, 0.39, 0.30), fine_wear * weathering * 0.08);
		float exhaust = smoothstep(-3.25, -2.30, -model_position.z)
			* (1.0 - smoothstep(0.15, 0.65, abs(model_position.x)))
			* smoothstep(0.65, 1.25, model_position.y)
			* (1.0 - smoothstep(1.25, 2.0, model_position.y));
		color = mix(color, vec3(0.105, 0.092, 0.075), exhaust * weathering * 0.30);
		rough = clamp(rough + dust * 0.12 + grit * 0.018, 0.58, 1.0);
		metal = clamp(metal + fine_wear * weathering * 0.10, 0.0, 0.65);
	} else if (material_kind == 1) {
		color = mix(color * vec3(0.48, 0.46, 0.40), vec3(0.26, 0.23, 0.17), dirt_band * 0.46);
		color = mix(color, vec3(0.39, 0.36, 0.29), fine_wear * 0.12);
		rough = clamp(rough + 0.12 + dirt_band * 0.08, 0.65, 1.0);
		metal = clamp(metal * 0.78 + fine_wear * 0.16, 0.0, 0.8);
	} else {
		color *= vec3(0.56, 0.55, 0.50);
		rough = max(rough, 0.82);
	}

	if (charred) {
		float soot = material_kind == 2 ? 0.78 : 0.62;
		color = mix(color, vec3(0.065, 0.057, 0.049), soot);
		rough = 0.96;
		metal *= 0.30;
	}

	ALBEDO = color;
	ROUGHNESS = rough;
	METALLIC = metal;
	if (has_source_normal) {
		NORMAL_MAP = texture(source_normal, surface_uv).rgb;
	}
	if (has_source_roughness) {
		rough *= texture(source_roughness_map, surface_uv).r;
		ROUGHNESS = clamp(rough, 0.0, 1.0);
	}
}
