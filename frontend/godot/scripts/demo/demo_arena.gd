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
	add_barrier(RUIN_ASSET,Vector3(-38,ground(-38,37),37),deg_to_rad(90),Vector3(2.0,1.91,.36),true)
	add_barrier(WALL_ASSET,Vector3(42,ground(42,42),42),deg_to_rad(0),Vector3(8.0,2.4,.25),true)
	add_instanced(RUBBLE_ASSET,_rubble_points(),false)
	add_instanced(FENCE_ASSET,_fence_points(),false)
	add_instanced(ROCK_ASSET,_rock_points(),false)
	build_vegetation()

func add_building(path: String,position: Vector3,rotation: float,dimensions: Vector3):
	var body=StaticBody3D.new()
	body.name=path.get_file().get_basename().to_pascal_case()
	body.position=position
	body.rotation.y=rotation
	add_child(body)
	var instance=_instantiate_model(path)
	if instance==null:return
	body.add_child(instance)
	var collision=CollisionShape3D.new()
	var box_shape=BoxShape3D.new()
	box_shape.size=Vector3(dimensions.x*.88,dimensions.y*.84,dimensions.z*.82)
	collision.shape=box_shape
	collision.position.y=box_shape.size.y*.5
	body.add_child(collision)
	body.collision_layer=1
	body.collision_mask=0

func add_barrier(path: String,position: Vector3,rotation: float,dimensions: Vector3,with_collision: bool):
	var root: Node3D
	if with_collision:
		root=StaticBody3D.new()
	else:
		root=Node3D.new()
	root.position=position
	root.rotation.y=rotation
	add_child(root)
	var model=_instantiate_model(path)
	if model==null:return
	root.add_child(model)
	if with_collision:
		var collision=CollisionShape3D.new()
		var shape=BoxShape3D.new();shape.size=dimensions
		collision.shape=shape;collision.position.y=dimensions.y*.5
		root.add_child(collision)
		root.collision_layer=1;root.collision_mask=0

func _instantiate_model(path: String) -> Node3D:
	var packed=load(path) as PackedScene
	if packed==null:
		push_error("DemoArena missing imported model: "+path)
		return null
	var instance=packed.instantiate() as Node3D
	if instance==null:push_error("DemoArena model root must be Node3D: "+path)
	return instance

func add_instanced(path: String,placements: Array,cast_shadows: bool):
	if placements.is_empty():return
	var template=_instantiate_model(path)
	if template==null:return
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
	template.queue_free()

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
	add_instanced(TREE_ASSETS.maple,_tree_points(maple_count,0),true)
	add_instanced(TREE_ASSETS.conifer,_tree_points(pine_count,1),true)
	add_instanced(TREE_ASSETS.oak,_tree_points(oak_count,2),true)
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

func _rock_points() -> Array:
	var result=[]
	for i in range(26):
		var x=rng.randf_range(-170,170);var z=rng.randf_range(-160,160)
		if absf(x)<48 and absf(z)<86:continue
		result.append({"position":Vector3(x,ground(x,z),z),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.55,1.15)})
	return result

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
