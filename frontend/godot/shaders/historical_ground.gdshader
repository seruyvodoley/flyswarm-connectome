shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D grass_diffuse : source_color, repeat_enable;
uniform sampler2D grass_normal : hint_normal, repeat_enable;
uniform sampler2D grass_roughness : repeat_enable;
uniform sampler2D dirt_diffuse : source_color, repeat_enable;
uniform sampler2D dirt_normal : hint_normal, repeat_enable;
uniform sampler2D dirt_roughness : repeat_enable;
uniform sampler2D road_diffuse : source_color, repeat_enable;
uniform sampler2D road_normal : hint_normal, repeat_enable;
uniform sampler2D road_roughness : repeat_enable;
uniform vec2 yard_a=vec2(-424.0,-82.0);
uniform vec2 yard_b=vec2(-460.0,72.0);
uniform vec2 yard_c=vec2(536.0,132.0);
uniform vec2 yard_d=vec2(118.0,-193.0);

varying vec3 world_position;
void vertex(){world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;}

float main_track(float x){return 5.0*sin(x*.008)+2.3*sin(x*.021+.8)+8.0;}
float diagonal_track(float x){return .43*x-142.0+5.0*sin(x*.012);}
float yard_mask(vec2 p,vec2 center,vec2 radius){
	float distance=length((p-center)/radius);
	return 1.0-smoothstep(.78,1.18,distance);
}

void fragment(){
	vec2 p=world_position.xz;
	vec2 uv=p*.026;
	vec2 main_path=vec2(p.x*.038,(p.y-main_track(p.x))*.085);
	vec2 diagonal_path=vec2((p.x*.91+p.y*.39)*.047,(p.y-diagonal_track(p.x))*.07);
	float main_road=1.0-smoothstep(5.0,10.5,abs(p.y-main_track(p.x)));
	float branch_road=1.0-smoothstep(3.2,7.0,abs(p.y-diagonal_track(p.x)));
	float wheel_wear=1.0-smoothstep(.7,1.7,abs(abs(p.y-main_track(p.x))-1.25));
	float yard=max(max(yard_mask(p,yard_a,vec2(20,15)),yard_mask(p,yard_b,vec2(14,12))),max(yard_mask(p,yard_c,vec2(19,16)),yard_mask(p,yard_d,vec2(14,12))));
	float field=step(.70,fract(sin(floor(p.x/115.0)*29.0+floor(p.y/90.0)*7.0)*43758.5453));
	float furrow=sin(p.x*.31+sin(p.y*.013)*3.0)*.5+.5;
	vec3 grass=texture(grass_diffuse,uv).rgb*vec3(.78,.85,.64);
	vec3 worn_soil=texture(dirt_diffuse,uv*.78).rgb*vec3(.82,.75,.62);
	vec3 road_surface=texture(road_diffuse,main_path).rgb*vec3(.76,.69,.57);
	vec3 branch_surface=texture(dirt_diffuse,diagonal_path).rgb*vec3(.78,.70,.57);
	vec3 field_tint=mix(vec3(.88,.90,.69),vec3(.73,.78,.56),field*.28+furrow*.08);
	vec3 color=grass*field_tint;
	color=mix(color,worn_soil,max(yard*.72,wheel_wear*.58));
	color=mix(color,branch_surface,branch_road*.92);
	color=mix(color,road_surface,main_road);
	vec3 grass_n=texture(grass_normal,uv).rgb;
	vec3 dirt_n=texture(dirt_normal,uv*.78).rgb;
	vec3 road_n=texture(road_normal,main_path).rgb;
	vec3 normal_map=mix(grass_n,dirt_n,max(yard*.72,wheel_wear*.58));
	normal_map=mix(normal_map,dirt_n,branch_road*.85);
	normal_map=mix(normal_map,road_n,main_road);
	float rough=texture(grass_roughness,uv).r;
	rough=mix(rough,texture(dirt_roughness,uv*.78).r,max(yard*.72,wheel_wear*.58));
	rough=mix(rough,texture(road_roughness,main_path).r,main_road);
	ALBEDO=color;
	NORMAL_MAP=normal_map;
	NORMAL_MAP_DEPTH=.22;
	ROUGHNESS=clamp(rough,.68,1.0);
}
