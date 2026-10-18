shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D grass_diffuse : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D grass_roughness : filter_linear_mipmap, repeat_enable;
uniform sampler2D dirt_diffuse : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D dirt_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D dirt_roughness : filter_linear_mipmap, repeat_enable;
uniform sampler2D road_diffuse : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D road_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D road_roughness : filter_linear_mipmap, repeat_enable;
uniform vec2 forest_center = vec2(-380.0, -20.0);
uniform float forest_radius = 170.0;
uniform float environment_seed = 1944.0;
uniform float main_road_offset = -92.0;
uniform bool physical_profile = false;

varying vec3 world_position;
varying vec3 world_normal;

float hash21(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7)) + environment_seed) * 43758.5453);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x),
		mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
}

float main_road_z(float x) {
	return sin(x * 0.012) * 11.0 + sin(x * 0.031 + 0.8) * 3.5 + main_road_offset;
}

float north_road_x(float z) {
	return 176.0 + sin(z * 0.014) * 12.0;
}

float west_road_x(float z) {
	return -248.0 + sin(z * 0.011 + 1.2) * 9.0;
}

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
}

void fragment() {
	vec2 p = world_position.xz;
	float broad_noise = value_noise(p * 0.009);
	float fine_noise = value_noise(p * 0.21);
	vec2 uv = p * 0.075;
	vec3 grass = texture(grass_diffuse, uv).rgb * vec3(0.78, 0.88, 0.68);
	vec3 earth = texture(dirt_diffuse, uv * 0.82 + vec2(0.19, -0.11)).rgb * vec3(0.91, 0.83, 0.69);
	vec3 lane = texture(road_diffuse, vec2(p.x * 0.043, p.y * 0.083)).rgb * vec3(0.79, 0.71, 0.59);

	float road_a = abs(p.y - main_road_z(p.x));
	float road_b = abs(p.x - north_road_x(p.y));
	float road_c = abs(p.x - west_road_x(p.y));
	float main_lane = 1.0 - smoothstep(5.7, 10.3, road_a);
	float side_lanes = max(1.0 - smoothstep(4.5, 8.5, road_b), 1.0 - smoothstep(4.0, 7.7, road_c));
	float road = max(main_lane, side_lanes);
	float shoulder = max(1.0 - smoothstep(9.0, 21.0, road_a), max(1.0 - smoothstep(7.0, 16.0, road_b), 1.0 - smoothstep(6.5, 15.0, road_c)));
	float forest = 1.0 - smoothstep(forest_radius - 13.0, forest_radius + 17.0, distance(p, forest_center));
	float forest_variation = 0.34 + 0.2 * broad_noise;
	float worn = clamp(shoulder * 0.34 + forest * forest_variation + (1.0 - smoothstep(0.1, 0.8, world_normal.y)) * 0.18, 0.0, 0.72);
	if (physical_profile) {
		float patch_a = 1.0 - smoothstep(119.0, 145.0, distance(p, vec2(-560.0, -350.0)));
		float patch_b = 1.0 - smoothstep(124.0, 151.0, distance(p, vec2(-530.0, 385.0)));
		float patch_c = 1.0 - smoothstep(112.0, 138.0, distance(p, vec2(510.0, -410.0)));
		float patch_d = 1.0 - smoothstep(106.0, 132.0, distance(p, vec2(535.0, 390.0)));
		worn = max(worn, max(max(patch_a, patch_b), max(patch_c, patch_d)) * (0.34 + broad_noise * 0.2));
	}
	vec3 color = mix(grass, earth, worn);
	color = mix(color, lane, road);
	color *= 0.93 + broad_noise * 0.12 + fine_noise * 0.035;
	color = mix(color, color * vec3(0.91, 0.86, 0.78), smoothstep(0.72, 1.0, broad_noise) * 0.12);

	vec3 grass_n = texture(grass_normal, uv).rgb;
	vec3 dirt_n = texture(dirt_normal, uv * 0.82).rgb;
	vec3 road_n = texture(road_normal, vec2(p.x * 0.043, p.y * 0.083)).rgb;
	vec3 soil_n = mix(grass_n, dirt_n, worn);
	vec3 normal_map = mix(soil_n, road_n, road);
	float rough = mix(texture(grass_roughness, uv).r, texture(dirt_roughness, uv * 0.82).r, worn);
	rough = mix(rough, texture(road_roughness, vec2(p.x * 0.043, p.y * 0.083)).r, road);

	ALBEDO = color;
	NORMAL_MAP = normal_map;
	NORMAL_MAP_DEPTH = 0.24;
	ROUGHNESS = clamp(rough, 0.68, 1.0);
	METALLIC = 0.0;
}
