extends Node3D
class_name HistoricalEnvironment

## Authored Eastern Front farm-country set dressing for Krasny Valley. Repeated
## trees and walls are batched; only near-field trunks and cover get colliders.
const ASSET="res://assets/environment/"
const TREES={"maple":ASSET+"vegetation/maple-light.glb","conifer":ASSET+"vegetation/conifer-light.glb","oak":ASSET+"vegetation/oak-detailed.glb"}
const FARM=ASSET+"ruins/farmhouse-barn.glb"
const COTTAGE=ASSET+"ruins/thatched-cottage.glb"
const WALL=ASSET+"ruins/stone-cottage-wall.glb"
const BROKEN_WALL=ASSET+"ruins/broken-masonry-wall.glb"
const FENCE=ASSET+"props/cow-pen-fence.glb"
const ROCK=ASSET+"rocks/rock-cluster.glb"
const RUBBLE=ASSET+"props/stone-rubble-pile.glb"
const DestructibleTree=preload("res://scripts/demo/destructible_tree.gd")

var terrain: Node3D
var density:=1.0
var rng:=RandomNumberGenerator.new()
var wall_visuals:Array[Dictionary]=[]
var fence_visuals:Array[Dictionary]=[]
var tree_points:Array[Dictionary]=[]
var interactive_tree_indices:Array[int]=[]
var house_count:=0
var forest_zones:Array[Dictionary]=[]
var collision_root:StaticBody3D
var combined_models:Dictionary={}

func build(terrain_node:Node3D,vegetation_density:float,seed_value:int)->void:
	terrain=terrain_node
	density=clampf(vegetation_density,.25,1.0)
	rng.seed=seed_value
	name="KrasnyValleyEnvironment"
	forest_zones=[{"center":Vector2(-500.0,-28.0),"radius":128.0},{"center":Vector2(492.0,30.0),"radius":142.0},{"center":Vector2(-164.0,0.0),"radius":72.0},{"center":Vector2(164.0,0.0),"radius":72.0}]
	collision_root=StaticBody3D.new();collision_root.name="CoverAndFenceColliders";collision_root.collision_layer=1;collision_root.collision_mask=0;add_child(collision_root)
	_build_hamlet()
	_build_farmsteads()
	_build_centre_hamlet()
	_build_cover_lines()
	_build_woodlots()
	_build_rubble()
	_build_rocks()
	_batch_models(wall_visuals)
	_batch_models(fence_visuals)
	_batch_trees()
	terrain.set("forest_zones",forest_zones)

func _build_hamlet()->void:
	# The western objective is approached through a staggered lane and farmyards;
	# the capture circle itself remains open for tanks to manoeuvre.
	_add_house(FARM,Vector2(-424,-82),deg_to_rad(18),Vector3(13.4,7.0,6.8))
	_add_house(COTTAGE,Vector2(-460,72),deg_to_rad(206),Vector3(6.3,5.4,5.1))
	_add_house(FARM,Vector2(-225,94),deg_to_rad(157),Vector3(12.0,6.6,6.2))
	_add_house(COTTAGE,Vector2(-208,-98),deg_to_rad(346),Vector3(6.3,5.4,5.1))
	_add_wall_run(Vector2(-407,-29),Vector2(-365,-48),"stone",[.0,.23,.46,.69,.92])
	_add_fence_run(Vector2(-465,30),Vector2(-435,14))
	_add_fence_run(Vector2(-256,48),Vector2(-215,27))

func _build_farmsteads()->void:
	_add_house(COTTAGE,Vector2(118,-193),deg_to_rad(277),Vector3(6.3,5.4,5.1))
	_add_house(FARM,Vector2(536,132),deg_to_rad(112),Vector3(12.0,6.6,6.2))
	_add_house(COTTAGE,Vector2(248,184),deg_to_rad(24),Vector3(6.3,5.4,5.1))
	_add_wall_run(Vector2(92,-166),Vector2(127,-149),"broken",[0.0,.5,1.0])
	_add_wall_run(Vector2(502,96),Vector2(548,81),"stone",[0.0,.25,.5,.75,1.0])
	_add_fence_run(Vector2(521,170),Vector2(486,194))
	_add_fence_run(Vector2(281,169),Vector2(321,148))

func _build_centre_hamlet()->void:
	# A pair of yards frames the central capture point without closing its open
	# firing lane. The flanking groves mask sight lines without blocking shells.
	_add_house(COTTAGE,Vector2(-82,-92),deg_to_rad(34),Vector3(6.3,5.4,5.1))
	_add_house(COTTAGE,Vector2(86,91),deg_to_rad(214),Vector3(6.3,5.4,5.1))
	_add_wall_run(Vector2(-108,-70),Vector2(-84,-57),"stone",[0.0,.5,1.0])
	_add_wall_run(Vector2(111,72),Vector2(86,58),"broken",[0.0,.5,1.0])
	_add_fence_run(Vector2(-62,-119),Vector2(-39,-132))
	_add_fence_run(Vector2(67,120),Vector2(43,134))

func _add_house(path:String,plan:Vector2,yaw:float,dimensions:Vector3)->void:
	var scene:=load(path) as PackedScene
	if scene==null:push_error("Missing licensed environment building: "+path);return
	house_count+=1
	var body:=StaticBody3D.new();body.name="Farmstead_%02d" % house_count;body.collision_layer=1;body.collision_mask=0
	body.position=Vector3(plan.x,terrain.height_at(plan.x,plan.y),plan.y);body.rotation.y=yaw;add_child(body)
	var visual:=scene.instantiate() as Node3D
	if visual:body.add_child(visual)
	var shape:=CollisionShape3D.new();var box:=BoxShape3D.new();box.size=Vector3(dimensions.x,dimensions.y*.76,dimensions.z)
	shape.shape=box;shape.position.y=dimensions.y*.38;body.add_child(shape)

func _add_wall_run(a:Vector2,b:Vector2,kind:String,steps:Array)->void:
	var path=BROKEN_WALL if kind=="broken" else WALL
	var vector=b-a;var yaw=atan2(vector.x,vector.y)
	for t in steps:
		var p=a.lerp(b,float(t));var length=vector.length()/maxf(1.0,float(steps.size()-1))
		wall_visuals.append({"path":path,"position":Vector3(p.x,terrain.height_at(p.x,p.y),p.y),"yaw":yaw,"scale":Vector3.ONE*.64})
		var shape:=CollisionShape3D.new();var box:=BoxShape3D.new();box.size=Vector3(maxf(2.1,length+.4),1.35,.58)
		shape.shape=box;shape.transform=Transform3D(Basis(Vector3.UP,yaw),Vector3(p.x,terrain.height_at(p.x,p.y)+.675,p.y));collision_root.add_child(shape)

func _add_fence_run(a:Vector2,b:Vector2)->void:
	var vector=b-a;var count=maxi(2,ceili(vector.length()/3.0));var yaw=atan2(vector.x,vector.y)
	for i in range(count):
		var p=a.lerp(b,float(i)/float(count-1))
		fence_visuals.append({"path":FENCE,"position":Vector3(p.x,terrain.height_at(p.x,p.y),p.y),"yaw":yaw,"scale":Vector3.ONE*.82})
		var shape:=CollisionShape3D.new();var box:=BoxShape3D.new();box.size=Vector3(2.7,1.05,.16);shape.shape=box
		shape.transform=Transform3D(Basis(Vector3.UP,yaw),Vector3(p.x,terrain.height_at(p.x,p.y)+.525,p.y));collision_root.add_child(shape)

func _build_cover_lines()->void:
	# Uneven fragments leave deliberate lanes through the central open bowl.
	_add_wall_run(Vector2(-118,-74),Vector2(-72,-94),"broken",[0.0,.31,.66,1.0])
	_add_wall_run(Vector2(73,88),Vector2(126,69),"stone",[0.0,.24,.49,.73,.97])
	_add_fence_run(Vector2(-163,121),Vector2(-124,142))
	_add_fence_run(Vector2(176,-132),Vector2(218,-112))

func _build_woodlots()->void:
	var centers=[]
	for zone in forest_zones:centers.append(zone.center)
	var kinds=["maple","conifer","oak"]
	var near:Dictionary={}
	var interactive_count=0
	for center_index in centers.size():
		var center:Vector2=centers[center_index]
		for i in range(roundi(76.0*density)):
			var angle=rng.randf_range(0.0,TAU);var radius=sqrt(rng.randf())*float(forest_zones[center_index].radius)
			var p=center+Vector2(cos(angle),sin(angle))*radius
			if absf(p.y)>294.0:continue
			var kind=kinds[rng.randi_range(0,kinds.size()-1)]
			var placement={"kind":kind,"position":Vector3(p.x,terrain.height_at(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.74,1.03)}
			var key=str(center_index)+":"+str(kind)
			if not near.has(key):near[key]=[]
			near[key].append(placement)
	# The four nearest trees per woodlot are individual, destructible trunks;
	# distant canopy remains MultiMesh-instanced and does not add active bodies.
	for key in near:
		var items:Array=near[key]
		items.sort_custom(func(left,right):return Vector2(left.position.x,left.position.z).length_squared()<Vector2(right.position.x,right.position.z).length_squared())
		for i in items.size():
			if i<2 and interactive_count<12:
				_add_interactive_tree(items[i]);interactive_count+=1
			else:tree_points.append(items[i])

func _add_interactive_tree(placement:Dictionary)->void:
	var trunk:DestructibleTree=DestructibleTree.new();trunk.name="WoodlotTrunk";trunk.collision_layer=1;trunk.collision_mask=0;trunk.position=placement.position;trunk.rotation.y=placement.yaw
	var kind=str(placement.kind);var threshold=310_000.0 if kind=="maple" else (520_000.0 if kind=="conifer" else 780_000.0)
	trunk.configure("WOOD",threshold,Color("62513b"));add_child(trunk)
	var shape:=CollisionShape3D.new();var capsule:=CapsuleShape3D.new();capsule.radius=.3*float(placement.scale);capsule.height=3.7*float(placement.scale);shape.shape=capsule;shape.position.y=capsule.height*.5;trunk.add_child(shape)
	var packed:=load(TREES[str(placement.kind)]) as PackedScene
	if packed:
		var visual=packed.instantiate() as Node3D
		visual.scale=Vector3.ONE*float(placement.scale)
		trunk.add_child(visual)

func _batch_trees()->void:
	for kind in TREES:
		var placements=[]
		for p in tree_points:
			if p.kind==kind:placements.append({"position":p.position,"yaw":p.yaw,"scale":p.scale})
		_batch_models_for_path(TREES[kind],placements,true)

func _build_rubble()->void:
	var points=[]
	for center in [Vector2(-424,-82),Vector2(118,-193),Vector2(536,132)]:
		for i in 3:
			var p=center+Vector2(rng.randf_range(-8,8),rng.randf_range(-7,7))
			points.append({"position":Vector3(p.x,terrain.height_at(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":rng.randf_range(.48,.76)})
	_batch_models_for_path(RUBBLE,points,false)

func _build_rocks()->void:
	var points=[]
	for center in [Vector2(-268,-157),Vector2(-147,176),Vector2(183,-182),Vector2(365,204)]:
		for i in 5:
			var p=center+Vector2(rng.randf_range(-16,16),rng.randf_range(-12,12));var size=rng.randf_range(.55,1.0)
			points.append({"position":Vector3(p.x,terrain.height_at(p.x,p.y),p.y),"yaw":rng.randf_range(-PI,PI),"scale":size})
			if i%2==0:
				var shape:=CollisionShape3D.new();var sphere:=SphereShape3D.new();sphere.radius=1.45*size;shape.shape=sphere;shape.position=Vector3(p.x,terrain.height_at(p.x,p.y)+1.05*size,p.y);collision_root.add_child(shape)
	_batch_models_for_path(ROCK,points,false)

func _batch_models(placements:Array[Dictionary])->void:
	var by_path:Dictionary={}
	for item in placements:
		var path:String=item.path
		if not by_path.has(path):by_path[path]=[]
		by_path[path].append(item)
	for path in by_path:_batch_models_for_path(path,by_path[path],true)

func _batch_models_for_path(path:String,placements:Array,cast_shadows:bool)->void:
	if placements.is_empty():return
	var packed:=load(path) as PackedScene
	if packed==null:push_error("Missing licensed scenery asset: "+path);return
	var template:=packed.instantiate() as Node3D
	if template==null:return
	add_child(template)
	var source_batches:Array=combined_models.get(path,[])
	if source_batches.is_empty():
		source_batches=_combine_source_meshes(template)
		combined_models[path]=source_batches
	for source_batch in source_batches:
		var multi:=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=source_batch.mesh;multi.instance_count=placements.size()
		for i in placements.size():
			var item=placements[i];var raw_scale=item.scale
			var scale=raw_scale if raw_scale is Vector3 else Vector3.ONE*float(raw_scale)
			var transform=Transform3D(Basis(Vector3.UP,float(item.yaw)).scaled(scale),item.position)
			multi.set_instance_transform(i,transform)
		var batch:=MultiMeshInstance3D.new();batch.multimesh=multi;batch.material_override=source_batch.material
		batch.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		batch.visibility_range_end=850.0;add_child(batch)
	template.queue_free()

func _combine_source_meshes(template:Node3D)->Array:
	var inverse:=template.global_transform.affine_inverse()
	var surfaces:Dictionary={}
	for node in template.find_children("*","MeshInstance3D",true,false):
		var source:=node as MeshInstance3D
		if source.mesh==null:continue
		var relative:=inverse*source.global_transform
		for surface_index in source.mesh.get_surface_count():
			var material:Material=source.material_override if source.material_override!=null else source.mesh.surface_get_material(surface_index)
			var key=str(material.get_instance_id()) if material!=null else "default"
			if not surfaces.has(key):
				var builder:=SurfaceTool.new();builder.begin(Mesh.PRIMITIVE_TRIANGLES);builder.set_material(material);surfaces[key]={"builder":builder,"material":material}
			(surfaces[key].builder as SurfaceTool).append_from(source.mesh,surface_index,relative)
	var result=[]
	for key in surfaces:
		var item:Dictionary=surfaces[key];var merged=(item.builder as SurfaceTool).commit()
		if merged!=null and merged.get_surface_count()>0:result.append({"mesh":merged,"material":item.material})
	return result
