shader_type spatial;
// Imported historical vehicle meshes do not all share consistent winding.
// Keep livery visible on both sides instead of culling whole mis-wound surfaces.
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

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
uniform int pattern_style = 0; // 0 solid, 1 three-tone bands, 2 spotted three-tone
uniform float pattern_scale : hint_range(0.5, 2.0) = 1.0;
uniform int material_kind = 0; // 0 armour, 1 tracks, 2 recess, 3 road wheel, 4 rubber
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
		// 1944-45 paint schemes: broad field-applied bands, or late German
		// three-tone patches with contrast-colour dots.  Decorative/approximate,
		// NOT an assertion of factory-specific historical vehicle identity.
		color = paint_base.rgb;
		if (pattern_style == 1 || pattern_style == 2) {
			vec3 p = model_position * pattern_scale;
			float green_field = field(p * vec3(0.78, 1.0, 0.66));
			float brown_field = field(p * vec3(0.92, 0.75, 1.05) + vec3(3.4, 0.6, -2.7));
			float edge = pattern_style == 1 ? 0.29 : 0.12;
			float green = smoothstep(-0.12 - edge, -0.12 + edge, green_field);
			float brown = smoothstep(0.47 - edge, 0.47 + edge, brown_field);
			color = mix(color, paint_secondary.rgb, green * 0.90);
			color = mix(color, paint_tertiary.rgb, brown * 0.90);
			if (pattern_style == 2) {
				// Small, deliberately irregular late-war "light spots".
				// No baked-in unit insignia or unsupported exact factory scheme.
				vec3 dots_p = model_position * 5.2;
				vec3 cell = floor(dots_p);
				float random_cell = fract(sin(dot(cell, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
				float dot_shape = 1.0 - smoothstep(0.23, 0.33, length(fract(dots_p) - vec3(0.5)));
				float spots = step(0.74, random_cell) * dot_shape;
				color = mix(color, paint_base.rgb, spots * 0.84);
			}
		}
		if (has_source_texture) {
			// Preserve low-frequency authored PBR albedo variations instead of
			// discarding the source texture with a flat solid shader colour.
			float tex_luma = dot(texel.rgb, vec3(0.2126, 0.7152, 0.0722));
			float tint_luma = max(dot(source_tint.rgb, vec3(0.2126, 0.7152, 0.0722)), 0.08);
			float source_detail = clamp(tex_luma / tint_luma, 0.70, 1.30);
			color *= mix(1.0, source_detail, 0.26);
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
		// Polished steel track contact faces, dusty recesses.
		color = mix(vec3(0.19, 0.20, 0.19), vec3(0.33, 0.29, 0.22), dirt_band * 0.57);
		color = mix(color, vec3(0.45, 0.43, 0.38), fine_wear * 0.16);
		rough = clamp(0.74 + dirt_band * 0.14, 0.60, 0.98);
		metal = 0.46;
	} else if (material_kind == 3) {
		// Painted road-wheel faces should not inherit the dark track material.
		color = mix(paint_base.rgb, vec3(0.31, 0.28, 0.22), dirt_band * weathering * 0.34);
		rough = clamp(rough + dirt_band * 0.13, 0.62, 0.98);
		metal = min(metal, 0.18);
	} else if (material_kind == 4) {
		// Rubber tyres on the steel/road-wheel assemblies.
		color = mix(vec3(0.072, 0.078, 0.075), vec3(0.21, 0.20, 0.17), dirt_band * 0.44);
		rough = 0.94;
		metal = 0.01;
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
