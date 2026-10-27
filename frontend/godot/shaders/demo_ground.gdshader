shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

uniform sampler2D grass_diffuse : source_color, repeat_enable;
uniform sampler2D grass_normal : hint_normal, repeat_enable;
uniform sampler2D grass_roughness : repeat_enable;
uniform sampler2D dirt_diffuse : source_color, repeat_enable;
uniform sampler2D dirt_normal : hint_normal, repeat_enable;
uniform sampler2D dirt_roughness : repeat_enable;
uniform sampler2D road_diffuse : source_color, repeat_enable;
uniform sampler2D road_normal : hint_normal, repeat_enable;
uniform sampler2D road_roughness : repeat_enable;

varying vec3 world_position;

void vertex() {
	world_position = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float segment_distance(vec2 p, vec2 a, vec2 b) {
	vec2 d=b-a;
	return length(p-a-d*clamp(dot(p-a,d)/dot(d,d),0.0,1.0));
}

void fragment() {
	vec2 p=world_position.xz;
	float center=-28.0+18.0*smoothstep(40.0,150.0,p.y);
	float across=length(vec2(p.x-center,max(abs(p.y)-205.0,0.0)));
	across=min(across,length(vec2(p.x-142.0-10.0*sin(p.y*.012),max(abs(p.y)-140.0,0.0))));
	across=min(across,length(vec2(p.x+142.0-10.0*sin(p.y*.012),max(abs(p.y)-140.0,0.0))));
	across=min(across,segment_distance(p,vec2(-24,-205),vec2(142,-120)));
	across=min(across,segment_distance(p,vec2(-24,-205),vec2(-142,-120)));
	across=min(across,segment_distance(p,vec2(24,205),vec2(142,120)));
	across=min(across,segment_distance(p,vec2(24,205),vec2(-142,120)));
	across=min(across,segment_distance(p,vec2(-85,30),vec2(85,30)));
	across=min(across,segment_distance(p,vec2(-85,-28),vec2(85,-28)));
	float road=1.0-smoothstep(3.6,7.8,across);
	float shoulder=1.0-smoothstep(7.0,14.0,across);
	vec2 ground_uv=p*.024;
	vec2 road_uv=p*.065;

	vec3 grass_color = texture(grass_diffuse, ground_uv).rgb * vec3(0.75, 0.82, 0.58);
	vec3 dirt_color = texture(dirt_diffuse, ground_uv * 0.72).rgb * vec3(0.80, 0.74, 0.63);
	vec3 road_color = texture(road_diffuse, road_uv).rgb * vec3(0.72, 0.66, 0.54);
	float worn = shoulder * 0.28;
	float field_variation=0.94+0.06*sin(p.x*.071)*cos(p.y*.045)+0.045*sin(p.x*.012+p.y*.025);
	vec3 color = mix(grass_color, dirt_color, worn)*field_variation;
	color = mix(color, road_color, road);

	vec3 grass_n = texture(grass_normal, ground_uv).rgb;
	vec3 dirt_n = texture(dirt_normal, ground_uv * 0.85).rgb;
	vec3 road_n = texture(road_normal, road_uv).rgb;
	vec3 normal_map = mix(grass_n, dirt_n, worn);
	normal_map = mix(normal_map, road_n, road);
	float rough = texture(grass_roughness, ground_uv).r;
	rough = mix(rough, texture(dirt_roughness, ground_uv * 0.85).r, worn);
	rough = mix(rough, texture(road_roughness, road_uv).r, road);

	ALBEDO = color;
	NORMAL_MAP = normal_map;
	NORMAL_MAP_DEPTH = 0.2;
	ROUGHNESS = clamp(rough, 0.68, 1.0);
}
