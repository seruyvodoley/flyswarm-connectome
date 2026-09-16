extends Node3D
var training = false
var range_flat=false
var mobility_course=false
var vegetation_density=1.0
var map_seed = 1944
var extent = 750.0
var forest_center = Vector2(-380, -20)
var forest_radius = 170.0

func height_at(x: float, z: float) -> float:
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
	var st=SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var steps=100
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
	m.shader=load("res://shaders/ground.gdshader")
	terrain_mesh.material_override=m
	add_child(terrain_mesh)
	terrain_mesh.create_trimesh_collision()
	if range_flat:return
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

func forest_blocks(a: Vector3,b: Vector3) -> bool:
	if training: return false
	var length_inside=0.0
	for i in range(20):
		var p=a.lerp(b,(i+.5)/20.0)
		if Vector2(p.x,p.z).distance_to(forest_center)<forest_radius:
			length_inside+=a.distance_to(b)/20
	return length_inside>55
