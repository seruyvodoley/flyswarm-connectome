shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled;

uniform vec4 tint : source_color = vec4(1.0, 0.45, 0.12, 0.9);
uniform float irregularity = 0.12;
uniform float glow = 0.0;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float angle = atan(p.y, p.x);
	float radius = length(p);
	float edge_noise = sin(angle * 7.0 + 0.4) * 0.045 + sin(angle * 13.0 + 1.7) * 0.025;
	float radial = 1.0 - smoothstep(0.68 + edge_noise * irregularity * 8.0, 1.0 + edge_noise, radius);
	float center = 1.0 - smoothstep(0.0, 0.85, radius);
	ALBEDO = tint.rgb;
	EMISSION = tint.rgb * glow * center;
	ALPHA = tint.a * radial;
}
