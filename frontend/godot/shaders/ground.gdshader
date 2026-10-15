shader_type spatial;
render_mode cull_back;
varying vec3 ground_position;
varying vec3 tint;
void vertex(){ground_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;tint=COLOR.rgb;}
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
void fragment(){
 vec2 p=ground_position.xz;
 float grain=hash(floor(p*5.0));
 float broad=sin(p.x*.31)*sin(p.y*.27)*.03;
 vec3 soil=tint*(.72+.22*grain)+vec3(broad);
 bool field=p.x>120.0 && p.x<500.0 && p.y>120.0 && p.y<420.0;
 if(field){soil=mix(soil,vec3(.36,.29,.15),.28+.12*sin(p.x*2.5));}
 ALBEDO=soil;ROUGHNESS=1.0;
}
