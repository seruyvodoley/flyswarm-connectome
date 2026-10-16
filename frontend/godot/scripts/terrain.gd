extends Node3D
var training = false
var range_flat=false
var mobility_course=false
var vegetation_density=1.0
var demo_mode=false
var map_seed = 1944
var extent = 750.0
var forest_center = Vector2(-380, -20)
var forest_radius = 170.0
var forest_zones:Array=[]
var relief_mounds:Array[Dictionary]=[]
const HistoricalEnvironmentScript=preload("res://scripts/maps/historical_environment.gd")

func height_at(x: float, z: float) -> float:
	if demo_mode:
		return demo_height_at(x,z)
	if range_flat:
		if mobility_course:return 9*exp(-pow((x-80)/45,2))*exp(-pow(z/250,2))
		return 0.0
	if training:
		return 7.0 * exp(-pow((x-120)/55,2)) * exp(-pow(z/150,2))
	var phase = float(map_seed % 37) * .03
	var rolling = 3.7*sin(x/205.0+phase)*cos(z/218.0)+2.8*sin(z/126.0+phase*.7)*sin(x/188.0)
	var ridge_axis=13.0*sin(x/360.0+phase)
	var north_ridge=9.0*exp(-pow((z-(132.0+ridge_axis))/82.0,2))
	var south_ridge=8.0*exp(-pow((z-(-132.0+ridge_axis))/88.0,2))
	var central_hollow=-3.5*exp(-pow(z/91.0,2))
	var river=-2.2*exp(-pow((z-22.0*sin(x/230.0+phase))/31.0,2))
	var landform=0.0
	for mound in relief_mounds:
		var dx=(x-float(mound.x))/float(mound.rx);var dz=(z-float(mound.z))/float(mound.rz)
		landform+=float(mound.height)*exp(-.5*(dx*dx+dz*dz))
	return rolling+north_ridge+south_ridge+central_hollow+river+landform

func demo_height_at(x: float,z: float) -> float:
	# Low, broad shoulders give hull-down approaches without putting a hard wall
	# across the short 1v1 sight line or making any vehicle-class slope unsafe.
	var base=.38*sin(x/78.0)*cos(z/92.0)+.22*sin(z/46.0)*sin(x/61.0)
	var shoulders=2.4*exp(-pow((x+105.0)/48.0,2.0)-pow((z-32.0)/40.0,2.0))
	shoulders+=2.6*exp(-pow((x-105.0)/50.0,2.0)-pow((z+34.0)/40.0,2.0))
	var swales=-.9*exp(-pow(x/42.0,2.0)-pow((z-54.0)/33.0,2.0))-.8*exp(-pow(x/44.0,2.0)-pow((z+54.0)/33.0,2.0))
	return base+shoulders+swales

func material(c: Color) -> StandardMaterial3D:
	var m=StandardMaterial3D.new()
	m.albedo_color=c
	m.roughness=.92
	return m

func box(at: Vector3, size: Vector3, colour: Color, solid: bool=true) -> Node3D:
	var root = StaticBody3D.new() if solid else Node3D.new()
	add_child(root)
	root.position=at
	var mesh=MeshInstance3D.new()
	var shape=BoxMesh.new()
	shape.size=size
	mesh.mesh=shape
	mesh.material_override=material(colour)
	root.add_child(mesh)
	if solid:
		var collider=CollisionShape3D.new()
		var cs=BoxShape3D.new()
		cs.size=size
		collider.shape=cs
		root.add_child(collider)
	return root

func build(is_training: bool, seed_value: int, size: float):
	training=is_training
	map_seed=seed_value
	extent=size/2
	relief_mounds.clear();forest_zones.clear()
	var relief_rng=RandomNumberGenerator.new();relief_rng.seed=map_seed^0x4b56594
	if not training and not range_flat:
		for i in 10:
			var mx=relief_rng.randf_range(-extent*.72,extent*.72);var mz=relief_rng.randf_range(-260.0,260.0)
			if absf(mx)<78.0:mx=signf(mx if not is_zero_approx(mx) else 1.0)*relief_rng.randf_range(100.0,260.0)
			relief_mounds.append({"x":mx,"z":mz,"rx":relief_rng.randf_range(105.0,195.0),"rz":relief_rng.randf_range(75.0,145.0),"height":relief_rng.randf_range(2.8,7.5)*(1.0 if i%2==0 else -0.62)})
	if demo_mode:
		build_demo_ground(size)
		return
	var st=SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps=128
	var spacing=size/steps
	for zi in range(steps):
		for xi in range(steps):
			var x=-extent+xi*spacing
			var z=-extent+zi*spacing
			for off in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var px=x+off.x*spacing
				var pz=z+off.y*spacing
				var h=height_at(px,pz)
				var c=Color(.28,.32,.17).lerp(Color(.48,.43,.29),clampf((h+10)/50,0,1))
				if absf(px)<20 or absf(pz)<12: c=Color(.43,.38,.27)
				if absf(pz-25*sin(px/180))<13 and absf(px)>30: c=Color(.29,.26,.21)
				st.set_color(c)
				st.set_normal(Vector3(height_at(px-1,pz)-height_at(px+1,pz),2,height_at(px,pz-1)-height_at(px,pz+1)).normalized())
				st.set_uv(Vector2(px,pz)/30)
				st.add_vertex(Vector3(px,h,pz))
	var terrain_mesh=MeshInstance3D.new()
	terrain_mesh.mesh=st.commit()
	var m=ShaderMaterial.new()
	m.shader=load("res://shaders/historical_ground.gdshader")
	for key in ["grass_diffuse","grass_normal","grass_roughness","dirt_diffuse","dirt_normal","dirt_roughness","road_diffuse","road_normal","road_roughness"]:
		var suffix="diffuse" if key.ends_with("diffuse") else ("normal" if key.ends_with("normal") else "roughness")
		m.set_shader_parameter(key,load("res://assets/environment/textures/"+key.replace("_"+suffix,"")+"_"+suffix+"_1k.jpg"))
	m.set_shader_parameter("yard_a",Vector2(-424.0,-82.0));m.set_shader_parameter("yard_b",Vector2(-460.0,72.0));m.set_shader_parameter("yard_c",Vector2(536.0,132.0));m.set_shader_parameter("yard_d",Vector2(118.0,-193.0))
	terrain_mesh.material_override=m
	add_child(terrain_mesh)
	terrain_mesh.create_trimesh_collision()
	if range_flat:return
	var rng=RandomNumberGenerator.new()
	rng.seed=map_seed
	if not training:
		var scenery:Node3D=HistoricalEnvironmentScript.new()
		add_child(scenery)
		scenery.build(self,vegetation_density,map_seed)
	else:
		_build_training_cover()

func build_demo_ground(size: float):
	var surface=SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps=112
	var spacing=size/float(steps)
	for zi in range(steps):
		for xi in range(steps):
			var x=-extent+xi*spacing
			var z=-extent+zi*spacing
			for offset in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var px=x+offset.x*spacing
				var pz=z+offset.y*spacing
				var normal=Vector3(height_at(px-1,pz)-height_at(px+1,pz),2.0,height_at(px,pz-1)-height_at(px,pz+1)).normalized()
				surface.set_normal(normal)
				surface.set_uv(Vector2(px,pz)/16.0)
				surface.add_vertex(Vector3(px,height_at(px,pz),pz))
	var ground=MeshInstance3D.new()
	ground.name="DemoArenaGround"
	ground.mesh=surface.commit()
	var mat=ShaderMaterial.new()
	mat.shader=load("res://shaders/demo_ground.gdshader")
	for key in ["grass_diffuse","grass_normal","grass_roughness","dirt_diffuse","dirt_normal","dirt_roughness","road_diffuse","road_normal","road_roughness"]:
		var texture_name=key
		var suffix="diffuse" if key.ends_with("diffuse") else ("normal" if key.ends_with("normal") else "roughness")
		var resource=load("res://assets/environment/textures/"+texture_name.replace("_"+suffix,"")+"_"+suffix+"_1k.jpg")
		mat.set_shader_parameter(key,resource)
	ground.material_override=mat
	add_child(ground)
	# A single static terrain mesh is the only arena collision surface.
	ground.create_trimesh_collision()

func forest_blocks(a: Vector3,b: Vector3) -> bool:
	if training: return false
	var length_inside=0.0
	for i in range(20):
		var p=a.lerp(b,(i+.5)/20.0)
		var inside=Vector2(p.x,p.z).distance_to(forest_center)<forest_radius
		for zone in forest_zones:
			if Vector2(p.x,p.z).distance_to(zone.center)<float(zone.radius):inside=true;break
		if inside:
			length_inside+=a.distance_to(b)/20
	return length_inside>55

func _build_training_cover()->void:
	for i in 5:
		var x=55.0+float(i%2)*18.0;var z=-150.0+float(i)*52.0
		box(Vector3(x,height_at(x,z)+2.5,z),Vector3(6.0,5.0,9.0),Color(.43,.39,.31))
