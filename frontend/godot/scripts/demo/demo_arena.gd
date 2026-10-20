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

var terrain_source: Node3D
var vegetation_density=1.0
var rng=RandomNumberGenerator.new()

func configure(terrain: Node3D,density: float):
	terrain_source=terrain
	vegetation_density=clampf(density,0.25,1.0)

func _ready():
	rng.seed=19441004
	build_layout()

func ground(x: float,z: float) -> float:
	return terrain_source.height_at(x,z) if is_instance_valid(terrain_source) else 0.0

func build_layout():
	# The three full imported models frame a small country lane. One hut is
	# visually damaged with separate rubble and a broken masonry wall section.
	add_building(FARM_ASSET,Vector3(-48,ground(-48,-14),-14),deg_to_rad(22),Vector3(13.4,7.02,6.8))
	add_building(COTTAGE_ASSET,Vector3(48,ground(48,10),10),deg_to_rad(198),Vector3(6.22,5.36,5.08))
	# Two outlying farm buildings add flank cover while keeping both spawn points
	# and the central approach clear. Their conservative box proxies share a
	# single collider each to stay within the arena physics-body budget.
	add_collision_building(COTTAGE_ASSET,Vector3(-108,ground(-108,-58),-58),deg_to_rad(34),Vector3(6.22,5.36,5.08))
	add_collision_building(FARM_ASSET,Vector3(108,ground(108,58),58),deg_to_rad(214),Vector3(11.6,6.4,6.0))
	add_barrier(RUIN_ASSET,Vector3(-38,ground(-38,37),37),deg_to_rad(90),Vector3(2.0,1.91,.36),true)
	add_barrier(WALL_ASSET,Vector3(42,ground(42,42),42),deg_to_rad(0),Vector3(8.0,2.4,.25),true)
	add_instanced(RUBBLE_ASSET,_rubble_points(),false)
	build_fences()
	build_rocks()
	build_vegetation()

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
	body.collision_layer=1
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
		var trimesh=mesh_node.mesh.create_trimesh_shape()
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
		section.collision_layer=1
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
	section.collision_layer=1
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
	var template=_instantiate_model(path)
	if template==null:return batches
	add_child(template)
	var template_inverse=template.global_transform.affine_inverse()
	var mesh_nodes=template.find_children("*","MeshInstance3D",true,false)
	for mesh_node in mesh_nodes:
		if mesh_node.mesh==null:continue
		var relative=template_inverse*mesh_node.global_transform
		var multi=MultiMesh.new()
		multi.transform_format=MultiMesh.TRANSFORM_3D
		multi.mesh=mesh_node.mesh
		multi.instance_count=placements.size()
		for i in range(placements.size()):
			var placement=placements[i]
			var scale_value=float(placement.scale)
			var base=Transform3D(Basis(Vector3.UP,float(placement.yaw)).scaled(Vector3.ONE*scale_value),placement.position)
			multi.set_instance_transform(i,base*relative)
		var batch=MultiMeshInstance3D.new()
		batch.multimesh=multi
		batch.material_override=mesh_node.material_override
		batch.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		batch.visibility_range_end=330.0
		add_child(batch)
		batches.append(batch)
	template.queue_free()
	return batches

func _tree_points(count: int,variant: int) -> Array:
	var points=[]
	for i in range(count):
		var angle=TAU*float(i)/float(count)+rng.randf_range(-.14,.14)
		var radius=rng.randf_range(137.0,181.0)
		var x=cos(angle)*radius
		var z=sin(angle)*radius
		if absf(x)<62.0 and absf(z)<100.0:continue
		if Vector2(x+116,z+31).length()<34.0 or Vector2(x-112,z-38).length()<28.0:continue
		var scale_value=rng.randf_range(.74,1.08)
		if variant==2:scale_value=rng.randf_range(.52,.70)
		points.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":scale_value})
	return points

func build_vegetation():
	var maple_count=maxi(8,roundi(17*vegetation_density))
	var pine_count=maxi(5,roundi(11*vegetation_density))
	var oak_count=maxi(2,roundi(4*vegetation_density))
	var maple=_tree_points(maple_count,0)
	var pine=_tree_points(pine_count,1)
	var oak=_tree_points(oak_count,2)
	# Every visible tree now has a matching trunk collider and destruction state.
	# Previously the distant forest was a MultiMesh with no physics, which made
	# those trees purely visual and let a tank drive straight through them.
	_add_tree_group(maple,"maple")
	_add_tree_group(pine,"conifer")
	_add_tree_group(oak,"oak")
	# Keep nine additional trees close to the lane as interactive obstacles.
	var near_positions=[Vector2(-32,-24),Vector2(-25,34),Vector2(-18,-43),Vector2(18,42),Vector2(28,-31),Vector2(38,16),Vector2(-44,12),Vector2(46,-8),Vector2(8,-52)]
	for i in range(near_positions.size()):
		var p: Vector2=near_positions[i]
		var kind="maple" if i%3==0 else ("conifer" if i%3==1 else "oak")
		var path=TREE_ASSETS[kind]
		_add_interactive_tree(path,{"position":Vector3(p.x,ground(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.58,.82)},kind)
	var shrubs=[];var grasses=[]
	for i in range(roundi(56*vegetation_density)):
		var x=rng.randf_range(-165,165);var z=rng.randf_range(-165,165)
		if absf(x)<46 and absf(z)<82:continue
		if Vector2(x+48,z+14).length()<22 or Vector2(x-48,z-10).length()<19:continue
		var item={"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.75,1.35)}
		if i%3==0:grasses.append(item)
		else:shrubs.append(item)
	add_instanced(SHRUB_ASSET,shrubs,false)
	add_instanced(GRASS_ASSET,grasses,false)

func _add_interactive_tree(path: String,placement: Dictionary,kind: String,batches: Array[MultiMeshInstance3D]=[],instance_index: int=-1) -> void:
	var tree: DestructibleTree=DestructibleTree.new()
	tree.name="InteractiveTree_%s" % kind
	tree.position=placement.position
	tree.rotation.y=float(placement.yaw)
	var scale_value=float(placement.scale)
	var threshold=180_000.0 if kind=="maple" else (260_000.0 if kind=="conifer" else 340_000.0)
	tree.configure("WOOD",threshold,Color("62513b"))
	tree.collision_layer=1
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
	for i in range(26):
		var x=rng.randf_range(-170,170);var z=rng.randf_range(-160,160)
		if absf(x)<48 and absf(z)<86:continue
		result.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.55,1.15)})
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
	for i in range(8):
		var x=-38+rng.randf_range(-4.0,4.0);var z=37+rng.randf_range(-3.0,3.0)
		points.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-.5,.5),"scale":rng.randf_range(.55,1.0)})
	return points

func _fence_points() -> Array:
	var points=[]
	for i in range(10):
		var x=-102.0+i*3.2;var z=72.0+sin(x*.035)*4.0
		points.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-.025,.025),"scale":1.0})
	for i in range(8):
		var x=72.0+i*3.2;var z=-78.0+sin(x*.04)*3.0
		points.append({"position":Vector3(x,ground(x,z),z),"yaw":PI+rng.randf_range(-.025,.025),"scale":1.0})
	return points
