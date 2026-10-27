extends Node3D
var training = false
var range_flat=false
var mobility_course=false
var vegetation_density=1.0
var demo_mode=false
var environment_profile := "legacy"
var map_seed = 1944
var extent = 750.0
var forest_center = Vector2(-380, -20)
var forest_radius = 170.0
var forest_zones:Array[Dictionary]=[]
var relief_mounds:Array[Dictionary]=[]
const HistoricalEnvironmentScript=preload("res://scripts/maps/historical_environment.gd")

func height_at(x: float, z: float) -> float:
	if demo_mode:
		return demo_height_at(x,z)
	var h := _historical_height_at(x,z) if environment_profile=="historical_krasny" else _legacy_height_at(x,z)
	if environment_profile == "enhanced_physical" and not training and not range_flat:
		# Preserve the valley, ridge, and dry wash while adding gentle, repeatable
		# field undulation. Road shoulders ease back to the original height field.
		var phase := float(map_seed % 97) * 0.071
		h += 0.72 * sin(x * 0.073 + phase) * sin(z * 0.061 - phase * 0.4)
		h += 0.28 * sin(x * 0.19 + z * 0.14 + phase)
		var road_z := _main_road_z(x)
		var road_weight := 1.0 - smoothstep(5.5, 12.0, absf(z - road_z))
		h = lerpf(h, _legacy_height_at(x,road_z), road_weight)
		for road_x in [_north_south_road_x(z), _west_road_x(z)]:
			var side_weight := 1.0 - smoothstep(4.0, 9.0, absf(x - road_x))
			h = lerpf(h, _legacy_height_at(road_x,z), side_weight)
	return h

func _legacy_height_at(x: float, z: float) -> float:
	if range_flat:
		if mobility_course:return 9*exp(-pow((x-80)/45,2))*exp(-pow(z/250,2))
		return 0.0
	if training:
		return 7.0 * exp(-pow((x-120)/55,2)) * exp(-pow(z/150,2))
	var phase = float(map_seed % 37) * .03
	var hills = 9*sin(x/170+phase)*cos(z/200) + 5*sin(z/83)*sin(x/150)
	var ridge = 28*exp(-pow((x-330)/95,2))*(.6+.4*cos(z/310))
	var valley = -7*exp(-pow(x/170,2))
	var river = -4*exp(-pow((z-25*sin(x/180))/15,2))
	# broad, gently graded crossing; no water volume in this dry riverbed scenario
	if absf(x)<30: river = -1
	return hills+ridge+valley+river

func _historical_height_at(x:float,z:float)->float:
	var phase=float(map_seed%37)*.03
	var rolling=3.7*sin(x/205.0+phase)*cos(z/218.0)+2.8*sin(z/126.0+phase*.7)*sin(x/188.0)
	var ridge_axis=13.0*sin(x/360.0+phase)
	var north_ridge=9.0*exp(-pow((z-(132.0+ridge_axis))/82.0,2.0))
	var south_ridge=8.0*exp(-pow((z-(-132.0+ridge_axis))/88.0,2.0))
	var central_hollow=-3.5*exp(-pow(z/91.0,2.0))
	var river=-2.2*exp(-pow((z-22.0*sin(x/230.0+phase))/31.0,2.0))
	var landform=0.0
	for mound in relief_mounds:
		var dx=(x-float(mound.x))/float(mound.rx);var dz=(z-float(mound.z))/float(mound.rz)
		landform+=float(mound.height)*exp(-.5*(dx*dx+dz*dz))
	return rolling+north_ridge+south_ridge+central_hollow+river+landform

func _main_road_z(x: float) -> float:
	return sin(x * 0.012) * 11.0 + sin(x * 0.031 + 0.8) * 3.5 - 92.0

func _north_south_road_x(z: float) -> float:
	return 176.0 + sin(z * 0.014) * 12.0

func _west_road_x(z: float) -> float:
	return -248.0 + sin(z * 0.011 + 1.2) * 9.0

func demo_height_at(x: float,z: float) -> float:
	# Broad ridges and reverse slopes: up to 11 m, with traversable grades.
	# The village has a gentle foundation; all three approaches retain relief.
	var base=.65*sin(x/91.0)*cos(z/112.0)
	var west=10.5*exp(-pow((x+182.0)/70.0,2.0)-pow((z-18.0)/100.0,2.0))
	west+=7.8*exp(-pow((x+156.0)/72.0,2.0)-pow((z+134.0)/65.0,2.0))
	var east=8.8*exp(-pow((x-185.0)/82.0,2.0)-pow((z+30.0)/84.0,2.0))
	east+=6.5*exp(-pow((x-140.0)/90.0,2.0)-pow((z-164.0)/62.0,2.0))
	var swale=-3.6*exp(-pow((x+100.0+12.0*sin(z/74.0))/29.0,2.0)-pow(z/185.0,2.0))
	swale-=2.7*exp(-pow((x-93.0)/32.0,2.0)-pow((z-28.0)/154.0,2.0))
	return base+west+east+swale

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
	if environment_profile=="historical_krasny" and not training and not range_flat:
		for i in 10:
			var mx=relief_rng.randf_range(-extent*.72,extent*.72);var mz=relief_rng.randf_range(-260.0,260.0)
			if absf(mx)<78.0:mx=signf(mx if not is_zero_approx(mx) else 1.0)*relief_rng.randf_range(100.0,260.0)
			relief_mounds.append({"x":mx,"z":mz,"rx":relief_rng.randf_range(105.0,195.0),"rz":relief_rng.randf_range(75.0,145.0),"height":relief_rng.randf_range(2.8,7.5)*(1.0 if i%2==0 else -0.62)})
	if demo_mode:
		build_demo_ground(size)
		return
	var st=SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps=100 if environment_profile == "legacy" else (128 if environment_profile == "historical_krasny" else (200 if environment_profile == "enhanced_visual" else 180))
	var spacing=size/steps
	# Cache the regular height grid once. The old path recomputed five height
	# samples for every duplicated triangle vertex (nearly a million terrain
	# function calls per map). Shared samples preserve the same surface positions
	# while making dense terrain practical during battle startup.
	var grid_stride: int = steps + 3
	var height_grid := PackedFloat32Array()
	height_grid.resize(grid_stride * grid_stride)
	for grid_z in range(-1,steps+2):
		for grid_x in range(-1,steps+2):
			var grid_world_x: float = -extent + float(grid_x) * spacing
			var grid_world_z: float = -extent + float(grid_z) * spacing
			var grid_height: float = _legacy_collision_surface_height(grid_world_x,grid_world_z) if environment_profile == "enhanced_visual" else height_at(grid_world_x,grid_world_z)
			height_grid[(grid_z+1)*grid_stride+(grid_x+1)] = grid_height
	var normal_grid := PackedVector3Array()
	normal_grid.resize(grid_stride * grid_stride)
	for grid_z in range(steps+1):
		for grid_x in range(steps+1):
			var grid_index: int = (grid_z+1)*grid_stride+(grid_x+1)
			var left_height: float = height_grid[grid_index-1]
			var right_height: float = height_grid[grid_index+1]
			var near_height: float = height_grid[grid_index-grid_stride]
			var far_height: float = height_grid[grid_index+grid_stride]
			normal_grid[grid_index] = Vector3(left_height-right_height,2.0*spacing,near_height-far_height).normalized()
	for zi in range(steps):
		for xi in range(steps):
			var x=-extent+xi*spacing
			var z=-extent+zi*spacing
			for off in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var vertex_xi: int = xi + int(off.x)
				var vertex_zi: int = zi + int(off.y)
				var px=x+float(vertex_xi-xi)*spacing
				var pz=z+float(vertex_zi-zi)*spacing
				var grid_index: int = (vertex_zi+1)*grid_stride+(vertex_xi+1)
				var h: float = height_grid[grid_index]
				var vertex_color := Color.WHITE
				if environment_profile == "legacy":
					vertex_color=Color(.28,.32,.17).lerp(Color(.48,.43,.29),clampf((h+10)/50,0,1))
					if absf(px)<20 or absf(pz)<12:vertex_color=Color(.43,.38,.27)
					if absf(pz-25*sin(px/180))<13 and absf(px)>30:vertex_color=Color(.29,.26,.21)
				st.set_color(vertex_color)
				st.set_normal(normal_grid[grid_index])
				st.set_uv(Vector2(px,pz)/30)
				st.add_vertex(Vector3(px,h,pz))
	st.generate_tangents()
	var terrain_mesh=MeshInstance3D.new()
	terrain_mesh.name="FieldGround"
	terrain_mesh.mesh=st.commit()
	var m=ShaderMaterial.new()
	if environment_profile=="historical_krasny":
		m.shader=load("res://shaders/historical_ground.gdshader")
		_configure_historical_ground(m)
	else:
		m.shader=load("res://shaders/field_ground.gdshader") if environment_profile != "legacy" else load("res://shaders/ground.gdshader")
	if environment_profile != "legacy" and environment_profile!="historical_krasny":
		_configure_field_material(m)
	terrain_mesh.material_override=m
	add_child(terrain_mesh)
	if environment_profile == "enhanced_visual":
		_create_legacy_resolution_collision()
	else:
		terrain_mesh.create_trimesh_collision()
	if range_flat:return
	if environment_profile=="historical_krasny" and not training:
		var historical_environment:Node3D=HistoricalEnvironmentScript.new()
		add_child(historical_environment)
		historical_environment.build(self,vegetation_density,map_seed)
		return
	if environment_profile != "legacy":return
	var rng=RandomNumberGenerator.new()
	rng.seed=map_seed
	for i in range(18 if not training else 4):
		var x=(55+i%3*25)*(-1 if i%2==0 else 1)
		var z=-180+int(i/3)*60
		var base=Vector3(x,height_at(x,z)+4,z)
		box(base,Vector3(13,8,18),Color(.55,.49,.37))
		var roof=box(base+Vector3(0,5,0),Vector3(10,2,20),Color(.27,.19,.14),false)
		roof.rotation.z=.15
		box(base+Vector3(0,-2,10),Vector3(19,3,.6),Color(.38,.37,.31))
		for wx in [-4,4]: box(base+Vector3(wx,0,9.05),Vector3(2,2,.1),Color(.09,.12,.13),false)
	for i in range(26 if not training else 5):
		var x=rng.randf_range(-extent*.85,extent*.85)
		var z=rng.randf_range(-extent*.65,extent*.65)
		if absf(x)<45: continue
		var rock=box(Vector3(x,height_at(x,z)+2,z),Vector3(8,5,6),Color(.35,.36,.32))
		rock.rotation.y=rng.randf_range(-PI,PI)
	var mm=MultiMesh.new()
	mm.transform_format=MultiMesh.TRANSFORM_3D
	var cone=CylinderMesh.new()
	cone.top_radius=0
	cone.bottom_radius=3.4
	cone.height=13
	cone.radial_segments=7
	mm.mesh=cone
	mm.instance_count=int(350*vegetation_density) if not training else 0
	for i in range(mm.instance_count):
		var a=rng.randf()*TAU
		var r=sqrt(rng.randf())*forest_radius
		var x=forest_center.x+cos(a)*r
		var z=forest_center.y+sin(a)*r
		mm.set_instance_transform(i,Transform3D(Basis(),Vector3(x,height_at(x,z)+6.5,z)))
	var trees=MultiMeshInstance3D.new()
	trees.multimesh=mm
	trees.material_override=material(Color(.11,.19,.10))
	trees.visibility_range_end=1100
	add_child(trees)
	# Decorative bridge deck follows crossing, solid approach slopes remain terrain.
	box(Vector3(0,height_at(0,0)-.1,0),Vector3(22,.3,42),Color(.28,.25,.19),false)

func build_demo_ground(size: float):
	var surface=SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps=140
	var spacing=size/float(steps)
	# Cache the shared grid and normals once, rather than five height-function
	# evaluations for every duplicated triangle vertex.
	var stride=steps+3
	var heights=PackedFloat32Array();heights.resize(stride*stride)
	for zi in range(-1,steps+2):
		for xi in range(-1,steps+2):
			heights[(zi+1)*stride+xi+1]=height_at(-extent+xi*spacing,-extent+zi*spacing)
	var normals=PackedVector3Array();normals.resize(stride*stride)
	for zi in range(steps+1):
		for xi in range(steps+1):
			var index=(zi+1)*stride+xi+1
			normals[index]=Vector3(heights[index-1]-heights[index+1],2.0*spacing,heights[index-stride]-heights[index+stride]).normalized()
	for zi in range(steps):
		for xi in range(steps):
			for offset in [Vector2i(0,0),Vector2i(1,0),Vector2i(0,1),Vector2i(1,0),Vector2i(1,1),Vector2i(0,1)]:
				var gx=xi+offset.x;var gz=zi+offset.y
				var px=-extent+gx*spacing;var pz=-extent+gz*spacing
				var index=(gz+1)*stride+gx+1
				surface.set_normal(normals[index]);surface.set_uv(Vector2(px,pz)/16.0)
				surface.add_vertex(Vector3(px,heights[index],pz))
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

func _create_legacy_resolution_collision() -> void:
	var collision_surface := SurfaceTool.new()
	collision_surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps := 100
	var spacing := float(extent * 2.0) / float(steps)
	for zi in range(steps):
		for xi in range(steps):
			var x: float = -extent + float(xi) * spacing
			var z: float = -extent + float(zi) * spacing
			for off in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var px: float = x + off.x * spacing
				var pz: float = z + off.y * spacing
				collision_surface.add_vertex(Vector3(px,_legacy_height_at(px,pz),pz))
	var collision_mesh := MeshInstance3D.new()
	collision_mesh.name = "LegacyResolutionTerrainCollision"
	collision_mesh.mesh = collision_surface.commit()
	collision_mesh.visible = false
	add_child(collision_mesh)
	collision_mesh.create_trimesh_collision()

func _legacy_collision_surface_height(x: float,z: float) -> float:
	# Sample the same 100×100 legacy triangulation used by its original
	# trimesh. Enhanced visual geometry subdivides those exact triangles so the
	# denser render surface cannot drift away from the collision surface.
	var steps := 100
	var spacing: float = float(extent) * 2.0 / float(steps)
	var gx := clampf((x + extent) / spacing,0.0,float(steps) - 0.00001)
	var gz := clampf((z + extent) / spacing,0.0,float(steps) - 0.00001)
	var cell_x := floori(gx)
	var cell_z := floori(gz)
	var tx := gx - float(cell_x)
	var tz := gz - float(cell_z)
	var x0: float = -float(extent) + float(cell_x) * spacing
	var z0: float = -float(extent) + float(cell_z) * spacing
	var h00 := _legacy_height_at(x0,z0)
	var h10 := _legacy_height_at(x0+spacing,z0)
	var h01 := _legacy_height_at(x0,z0+spacing)
	if tx + tz <= 1.0:
		return h00 + tx * (h10-h00) + tz * (h01-h00)
	var h11 := _legacy_height_at(x0+spacing,z0+spacing)
	return (1.0-tz)*h10 + (tx+tz-1.0)*h11 + (1.0-tx)*h01

func forest_blocks(a: Vector3,b: Vector3) -> bool:
	if training or range_flat or demo_mode: return false
	var length_inside=0.0
	for i in range(20):
		var p=a.lerp(b,(i+.5)/20.0)
		var blocked: bool = Vector2(p.x,p.z).distance_to(forest_center)<forest_radius
		for zone in forest_zones:
			if Vector2(p.x,p.z).distance_to(zone.center)<float(zone.radius):blocked=true;break
		if environment_profile == "enhanced_physical":
			for patch in _physical_forest_patches():
				if Vector2(p.x,p.z).distance_to(patch[0]) < patch[1]:
					blocked = true
		if blocked:
			length_inside+=a.distance_to(b)/20
	return length_inside>55

func _physical_forest_patches() -> Array:
	return [
		[Vector2(-560.0,-350.0),132.0],
		[Vector2(-530.0,385.0),138.0],
		[Vector2(510.0,-410.0),126.0],
		[Vector2(535.0,390.0),120.0]
	]

func _configure_field_material(material_value: ShaderMaterial) -> void:
	for key in ["grass_diffuse","grass_normal","grass_roughness","dirt_diffuse","dirt_normal","dirt_roughness","road_diffuse","road_normal","road_roughness"]:
		var suffix := "diffuse" if key.ends_with("diffuse") else ("normal" if key.ends_with("normal") else "roughness")
		var resource_path: String = "res://assets/environment/textures/" + key.replace("_" + suffix, "") + "_" + suffix + "_1k.jpg"
		material_value.set_shader_parameter(key,load(resource_path))
	material_value.set_shader_parameter("forest_center",forest_center)
	material_value.set_shader_parameter("forest_radius",forest_radius)
	material_value.set_shader_parameter("environment_seed",float(map_seed % 997))
	material_value.set_shader_parameter("physical_profile",environment_profile == "enhanced_physical")
	material_value.set_shader_parameter("main_road_offset",-92.0)

func _configure_historical_ground(material_value:ShaderMaterial)->void:
	for key in ["grass_diffuse","grass_normal","grass_roughness","dirt_diffuse","dirt_normal","dirt_roughness","road_diffuse","road_normal","road_roughness"]:
		var suffix:="diffuse" if key.ends_with("diffuse") else ("normal" if key.ends_with("normal") else "roughness")
		var resource_path:String="res://assets/environment/textures/"+key.replace("_"+suffix,"")+"_"+suffix+"_1k.jpg"
		material_value.set_shader_parameter(key,load(resource_path))
