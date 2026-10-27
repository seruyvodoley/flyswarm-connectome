extends Node3D

const TREE_ASSETS={
	"maple":"res://assets/environment/vegetation/maple-light.glb",
	"conifer":"res://assets/environment/vegetation/conifer-light.glb",
	"oak":"res://assets/environment/vegetation/oak-detailed.glb"
}
const SHRUB_ASSET="res://assets/environment/vegetation/elder-bush.glb"
const GRASS_ASSET="res://assets/environment/vegetation/meadow-grass.glb"
const ROCK_ASSET="res://assets/environment/rocks/rock-cluster.glb"
const FARM_ASSET="res://assets/environment/ruins/farmhouse-barn.glb"
const COTTAGE_ASSET="res://assets/environment/ruins/thatched-cottage.glb"
const RUIN_ASSET="res://assets/environment/ruins/broken-masonry-wall.glb"
const WALL_ASSET="res://assets/environment/ruins/stone-cottage-wall.glb"
const FENCE_ASSET="res://assets/environment/props/cow-pen-fence.glb"
const RUBBLE_ASSET="res://assets/environment/props/stone-rubble-pile.glb"
const DestructibleSection=preload("res://scripts/demo/destructible_section.gd")
const DestructibleTree=preload("res://scripts/demo/destructible_tree.gd")

const Layout=preload("res://scripts/demo/arena_layout.gd")
var collision_cache={}
var visual_cache={}
var generation_ms=0.0
var terrain_source: Node3D
var vegetation_density=1.0
var rng=RandomNumberGenerator.new()

func configure(terrain: Node3D,density: float):
	terrain_source=terrain
	vegetation_density=clampf(density,0.25,1.0)

func _ready():
	rng.seed=19441004
	var started=Time.get_ticks_usec()
	build_layout()
	generation_ms=(Time.get_ticks_usec()-started)/1000.0

func ground(x: float,z: float) -> float:
	return terrain_source.height_at(x,z) if is_instance_valid(terrain_source) else 0.0

func build_layout():
	# Ten buildings frame two streets and connected yards. Keep models at
	# authored metre scale and use their real destructible mesh sections.
	for building in Layout.BUILDINGS:
		var farm=bool(building[3]);var x=float(building[0]);var z=float(building[1])
		add_building(FARM_ASSET if farm else COTTAGE_ASSET,Vector3(x,ground(x,z)-.12,z),float(building[2]),Vector3(13.4,7.02,6.8) if farm else Vector3(6.22,5.36,5.08))
	for p in [Vector2(-45,-28),Vector2(44,30),Vector2(-120,83),Vector2(117,-83)]:
		add_barrier(WALL_ASSET,Vector3(p.x,ground(p.x,p.y),p.y),0,Vector3(8,2.4,.25),true)
	add_barrier(RUIN_ASSET,Vector3(82,ground(82,24),24),PI/2,Vector3(2,1.91,.36),true)
	add_instanced(RUBBLE_ASSET,_rubble_points(),false)
	build_fences();build_rocks();build_vegetation()

func add_building(path: String,position: Vector3,rotation: float,dimensions: Vector3):
	var body=Node3D.new()
	body.name=path.get_file().get_basename().to_pascal_case()
	body.position=position
	body.rotation.y=rotation
	add_child(body)
	var instance=_instantiate_model(path)
	if instance==null:return
	body.add_child(instance)
	if _add_mesh_sections(body,instance,"MASONRY",620_000.0,Color("b5a781"))==0:
		# Fallback for a future model with no mesh surfaces: maintain the original
		# dimension-based collision proxy, divided into independently removable sides.
		var wall_h=dimensions.y*.68
		var wall_y=wall_h*.5
		var wall_t=maxf(.22,dimensions.z*.065)
		_add_destructible_box(body,Vector3(0,wall_y,dimensions.z*.5),Vector3(dimensions.x,wall_h,wall_t),"MASONRY",620_000.0,Color("b5a781"))
		_add_destructible_box(body,Vector3(0,wall_y,-dimensions.z*.5),Vector3(dimensions.x,wall_h,wall_t),"MASONRY",620_000.0,Color("b5a781"))
		_add_destructible_box(body,Vector3(-dimensions.x*.5,wall_y,0),Vector3(wall_t,wall_h,dimensions.z),"MASONRY",620_000.0,Color("b5a781"))
		_add_destructible_box(body,Vector3(dimensions.x*.5,wall_y,0),Vector3(wall_t,wall_h,dimensions.z),"MASONRY",620_000.0,Color("b5a781"))

func add_collision_building(path:String,position:Vector3,yaw:float,dimensions:Vector3)->void:
	var body:=StaticBody3D.new()
	body.name="FlankFarmsteadLeft" if position.x<0.0 else "FlankFarmsteadRight"
	body.position=position
	body.rotation.y=yaw
	body.collision_layer=9
	body.collision_mask=0
	add_child(body)
	var model:=_instantiate_model(path)
	if model!=null:body.add_child(model)
	var collision:=CollisionShape3D.new()
	var proxy:=BoxShape3D.new()
	proxy.size=Vector3(dimensions.x*.9,dimensions.y*.78,dimensions.z*.88)
	collision.shape=proxy
	collision.position.y=dimensions.y*.39
	body.add_child(collision)

func add_barrier(path: String,position: Vector3,rotation: float,dimensions: Vector3,with_collision: bool):
	var root=Node3D.new()
	root.position=position
	root.rotation.y=rotation
	add_child(root)
	var model=_instantiate_model(path)
	if model==null:return
	root.add_child(model)
	if with_collision:
		var kind="MASONRY" if path==RUIN_ASSET or path==WALL_ASSET else "WOOD"
		var threshold=420_000.0 if kind=="MASONRY" else 90_000.0
		if _add_mesh_sections(root,model,kind,threshold,Color("b8aa86") if kind=="MASONRY" else Color("765638"))==0:
			_add_destructible_box(root,Vector3(0,dimensions.y*.5,0),dimensions,kind,threshold,Color("b8aa86") if kind=="MASONRY" else Color("765638"))

func _add_mesh_sections(parent: Node3D,model: Node3D,kind: String,threshold_j: float,color: Color) -> int:
	var added=0
	var parent_inverse=parent.global_transform.affine_inverse()
	for node in model.find_children("*","MeshInstance3D",true,false):
		var mesh_node:=node as MeshInstance3D
		if mesh_node.mesh==null:continue
		var key=mesh_node.mesh.get_instance_id()
		if not collision_cache.has(key):collision_cache[key]=mesh_node.mesh.create_trimesh_shape()
		var trimesh=collision_cache[key]
		if trimesh==null:continue
		var section: DestructibleSection=DestructibleSection.new()
		section.name="Section_%s" % mesh_node.name.to_pascal_case()
		section.transform=parent_inverse*mesh_node.global_transform
		var volume=maxf(.5,mesh_node.get_aabb().size.x*mesh_node.get_aabb().size.y*mesh_node.get_aabb().size.z)
		var section_strength=threshold_j*clampf(sqrt(volume/3.0),.55,1.5)
		if mesh_node.name.to_lower().contains("door") or mesh_node.name.to_lower().contains("wood"):
			section.configure("WOOD",minf(section_strength,480_000.0),Color("765638"))
		else:
			section.configure(kind,section_strength,color)
		section.collision_layer=9
		section.collision_mask=0
		section.bind_visual_piece(mesh_node)
		var collision=CollisionShape3D.new()
		collision.shape=trimesh
		section.add_child(collision)
		parent.add_child(section)
		added+=1
	return added

func _add_destructible_box(parent: Node3D,center: Vector3,size: Vector3,kind: String,threshold_j: float,color: Color) -> DestructibleSection:
	var section: DestructibleSection=DestructibleSection.new()
	section.name="%sSection" % kind.to_pascal_case()
	section.position=center
	section.configure(kind,threshold_j,color)
	section.collision_layer=9
	section.collision_mask=0
	var shape=CollisionShape3D.new()
	var box=BoxShape3D.new()
	box.size=size
	shape.shape=box
	section.add_child(shape)
	parent.add_child(section)
	return section

func _instantiate_model(path: String) -> Node3D:
	var packed=load(path) as PackedScene
	if packed==null:
		push_error("DemoArena missing imported model: "+path)
		return null
	var instance=packed.instantiate() as Node3D
	if instance==null:push_error("DemoArena model root must be Node3D: "+path)
	return instance

func add_instanced(path: String,placements: Array,cast_shadows: bool) -> Array[MultiMeshInstance3D]:
	var batches: Array[MultiMeshInstance3D] = []
	if placements.is_empty():return batches
	# Imported trees contain hundreds of separate twig/leaf objects but only
	# 2–4 materials. Merge their static geometry once per asset/material, then
	# instance the merged surfaces: hundreds of draw calls become a handful.
	if not visual_cache.has(path):
		var template=_instantiate_model(path)
		if template==null:return batches
		add_child(template)
		var inverse=template.global_transform.affine_inverse()
		var groups={}
		for mesh_node in template.find_children("*","MeshInstance3D",true,false):
			if mesh_node.mesh==null:continue
			for surface in mesh_node.mesh.get_surface_count():
				var mat=mesh_node.get_active_material(surface)
				if not groups.has(mat):
					var builder=SurfaceTool.new();builder.begin(Mesh.PRIMITIVE_TRIANGLES);groups[mat]=builder
				groups[mat].append_from(mesh_node.mesh,surface,inverse*mesh_node.global_transform)
		var merged=[]
		for mat in groups:
			groups[mat].index()
			merged.append({"mesh":groups[mat].commit(),"material":mat})
		visual_cache[path]=merged
		template.free()
	for surface in visual_cache[path]:
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D
		multi.mesh=surface.mesh;multi.instance_count=placements.size()
		for i in range(placements.size()):
			var placement=placements[i];var scale_value=float(placement.scale)
			multi.set_instance_transform(i,Transform3D(Basis(Vector3.UP,float(placement.yaw)).scaled(Vector3.ONE*scale_value),placement.position))
		var batch=MultiMeshInstance3D.new();batch.multimesh=multi
		batch.material_override=surface.material
		batch.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		batch.visibility_range_end=1500.0;batch.visibility_range_end_margin=30.0
		add_child(batch);batches.append(batch)
	return batches

func _tree_points(count: int,variant: int) -> Array:
	var points=[]
	# Discontinuous groves and field margins, never an impassable tree ring.
	for i in range(count):
		var centers=[Vector2(-240,-110),Vector2(-210,160),Vector2(220,95),Vector2(220,-175),Vector2(-60,270),Vector2(85,-280)]
		var p=centers[i%centers.size()]+Vector2(rng.randf_range(-43,43),rng.randf_range(-40,40))
		if Layout.route_distance(p)<12.0 or Layout.building_blocked(p,10):continue
		var scale_value=rng.randf_range(.74,1.08) if variant!=2 else rng.randf_range(.52,.70)
		points.append({"position":Vector3(p.x,ground(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":scale_value})
	return points

func build_vegetation():
	_add_tree_group(_tree_points(roundi(38*vegetation_density),0),"maple")
	_add_tree_group(_tree_points(roundi(30*vegetation_density),1),"conifer")
	_add_tree_group(_tree_points(maxi(1,roundi(3*vegetation_density)),2),"oak")
	var shrubs=[];var grasses=[]
	for i in range(roundi(150*vegetation_density)):
		var x=rng.randf_range(-310,310);var z=rng.randf_range(-310,310)
		if Layout.route_distance(Vector2(x,z))<7 or Layout.building_blocked(Vector2(x,z),5):continue
		var item={"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.75,1.35)}
		if i%3==0:grasses.append(item)
		else:shrubs.append(item)
	add_instanced(SHRUB_ASSET,shrubs,false);add_instanced(GRASS_ASSET,grasses,false)

func _add_interactive_tree(path: String,placement: Dictionary,kind: String,batches: Array[MultiMeshInstance3D]=[],instance_index: int=-1) -> void:
	var tree: DestructibleTree=DestructibleTree.new()
	tree.name="InteractiveTree_%s" % kind
	tree.position=placement.position
	tree.rotation.y=float(placement.yaw)
	var scale_value=float(placement.scale)
	var threshold=180_000.0 if kind=="maple" else (260_000.0 if kind=="conifer" else 340_000.0)
	tree.configure("WOOD",threshold,Color("62513b"))
	tree.collision_layer=9
	tree.collision_mask=0
	var collider=CollisionShape3D.new()
	var trunk=CapsuleShape3D.new()
	trunk.radius=(.27 if kind!="oak" else .38)*scale_value
	trunk.height=(3.1 if kind!="oak" else 4.4)*scale_value
	collider.shape=trunk
	collider.position.y=trunk.height*.5
	tree.add_child(collider)
	if instance_index>=0:
		tree.bind_batched_visual(path,scale_value,batches,instance_index)
	else:
		var visual=_instantiate_model(path)
		if visual!=null:
			visual.scale=Vector3.ONE*scale_value
			tree.add_child(visual)
	add_child(tree)

func _add_tree_group(points: Array,kind: String) -> void:
	var batches: Array[MultiMeshInstance3D] = add_instanced(TREE_ASSETS[kind],points,true)
	for index in range(points.size()):
		_add_interactive_tree(TREE_ASSETS[kind],points[index],kind,batches,index)

func build_fences() -> void:
	var placements := _fence_points()
	for index in range(placements.size()):
		var placement: Dictionary = placements[index]
		var fence := Node3D.new()
		fence.name = "DestructibleFence_%02d" % index
		fence.position = placement.position
		fence.rotation.y = float(placement.yaw)
		add_child(fence)
		var model := _instantiate_model(FENCE_ASSET)
		if model == null:
			continue
		fence.add_child(model)
		if _add_mesh_sections(fence,model,"WOOD",90_000.0,Color("765638")) == 0:
			_add_destructible_box(fence,Vector3(0,.55,0),Vector3(3.2,1.1,.18),"WOOD",90_000.0,Color("765638"))

func _rock_points() -> Array:
	var result=[]
	for center in Layout.ROCKS:
		for i in 2:
			var p=center+Vector2(i*4.8,0)
			result.append({"position":Vector3(p.x,ground(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.85,1.3)})
	return result

func build_rocks() -> void:
	var placements := _rock_points()
	for index in range(placements.size()):
		var placement: Dictionary = placements[index]
		var rock := Node3D.new()
		rock.name = "DestructibleRock_%02d" % index
		rock.position = placement.position
		rock.rotation.y = float(placement.yaw)
		add_child(rock)
		var model := _instantiate_model(ROCK_ASSET)
		if model == null:
			continue
		model.scale = Vector3.ONE * float(placement.scale)
		rock.add_child(model)
		if _add_mesh_sections(rock,model,"STONE",2_400_000.0,Color("77766f")) == 0:
			var section: DestructibleSection = DestructibleSection.new()
			section.name = "StoneSection"
			section.position.y = .65 * float(placement.scale)
			section.configure("STONE",2_400_000.0,Color("77766f"))
			var collider := CollisionShape3D.new()
			var sphere := SphereShape3D.new()
			sphere.radius = .9 * float(placement.scale)
			collider.shape = sphere
			section.add_child(collider)
			rock.add_child(section)

func _rubble_points() -> Array:
	var points=[]
	for i in range(10):
		var x=82+rng.randf_range(-4,4);var z=24+rng.randf_range(-3,3)
		points.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-.5,.5),"scale":rng.randf_range(.55,1.0)})
	return points

func _fence_points() -> Array:
	var points=[]
	for center in [Vector2(-57,-82),Vector2(54,80),Vector2(86,-55)]:
		for i in 6:
			var x=center.x+i*3.2;var z=center.y
			points.append({"position":Vector3(x,ground(x,z),z),"yaw":0.0,"scale":1.0})
	return points
