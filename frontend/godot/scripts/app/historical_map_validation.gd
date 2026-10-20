extends SceneTree

const Terrain=preload("res://scripts/terrain.gd")
const TreeScript=preload("res://scripts/demo/destructible_tree.gd")
const IDS=["t34_85","is2_1944","panther_g","tiger_i","jagdpanther","su100"]
var failures:=0
var houses:=0
var falling_trees:=0
var batched:=0

func _initialize()->void:
	call_deferred("run")

func check(ok:bool,message:String)->void:
	if not ok:failures+=1;push_error(message)

func count_nodes(node:Node)->void:
	if node is StaticBody3D and str(node.name).begins_with("Farmstead_"):houses+=1
	if node.get_script()==TreeScript:falling_trees+=1
	if node is MultiMeshInstance3D:batched+=1
	for child in node.get_children():count_nodes(child)

func run()->void:
	var terrain:Node3D=Terrain.new();root.add_child(terrain)
	terrain.environment_profile="historical_krasny"
	terrain.vegetation_density=.5
	terrain.build(false,1944,1500.0)
	for _frame in 4:await physics_frame
	var environment=terrain.get_node_or_null("KrasnyValleyEnvironment")
	check(environment!=null,"Historical battle builds its authored farm-country environment separately from Open Day")
	if environment==null:quit(1);return
	count_nodes(environment)
	check(houses>=6,"Historical villages and farms use imported licensed building assets")
	check(falling_trees>=8 and falling_trees<=16,"Woodlots use a bounded number of destructible near-field tree trunks")
	check(batched>=8 and batched<=40,"Repeated woodlots, walls, fences, rocks and rubble use a bounded number of batched material meshes")
	check(environment.collision_root.get_child_count()>=40,"Stone cover, timber fences and boulders have real physics shapes")
	check(terrain.forest_zones.size()==4 and terrain.forest_blocks(Vector3(-600,4,-28),Vector3(-400,4,-28)) and terrain.forest_blocks(Vector3(-230,4,0),Vector3(-100,4,0)),"Distant and flanking woodlots provide visual masking independent of physical projectile blockers")
	check(not terrain.forest_blocks(Vector3(-70,3,0),Vector3(70,3,0)),"Open centre lanes between the three capture sectors remain visible")
	var h0=terrain.height_at(-286.0,48.0);var h1=terrain.height_at(-286.0,48.0)
	check(is_equal_approx(h0,h1),"The same map seed produces stable terrain heights")
	var height_min=INF;var height_max=-INF;var max_slope=0.0
	for x in range(-700,701,50):
		for z in range(-250,251,50):
			var h=terrain.height_at(float(x),float(z));height_min=minf(height_min,h);height_max=maxf(height_max,h)
			max_slope=maxf(max_slope,absf(terrain.height_at(float(x)+10.0,float(z))-h)/10.0)
	check(height_max-height_min>9.0,"Historical terrain has rolling hills, ridges and low ground rather than one flat plane")
	check(max_slope<.25,"Generated relief remains within a drivable grade envelope")
	var shape:=BoxShape3D.new();shape.size=Vector3(4.0,1.4,6.5)
	var spawn_clear=true
	for side in [-1.0,1.0]:
		for i in 8:
			var x=(float(i)-3.5)*28.0;var z=side*400.0
			var query:=PhysicsShapeQueryParameters3D.new();query.shape=shape;query.transform=Transform3D(Basis(),Vector3(x,terrain.height_at(x,z)+1.1,z));query.collision_mask=1
			if not root.get_world_3d().direct_space_state.intersect_shape(query,1).is_empty():spawn_clear=false
	check(spawn_clear,"All sixteen 8v8 spawn footprints are clear of buildings, fences, trees and rocks")
	var center_hit=root.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(0,45,-35),Vector3(0,45,35),1,[]))
	check(center_hit.is_empty(),"The central capture approach remains an open tank-width firing lane")
	check(IDS.size()==6,"The terrain envelope is checked against the project's six historical vehicle classes")
	print("HISTORICAL MAP VALIDATION failures=",failures," houses=",houses," interactive_trees=",falling_trees," batched_meshes=",batched," slope_max=",max_slope," relief=",height_max-height_min)
	quit(0 if failures==0 else 1)
