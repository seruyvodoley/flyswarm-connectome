extends SceneTree
const Layout=preload("res://scripts/demo/arena_layout.gd")
var failures=0
func check(ok: bool,message: String):
	if not ok:failures+=1;push_error(message)
func _initialize():call_deferred("run")
func run():
	var app=root.get_node("AppState");app.clear_view();app.configure_demo("t34_85")
	app.session.red_controller="rule";app.session.blue_controller="rule";app.session.record=false
	var b=load("res://scenes/Battle.tscn").instantiate();b.session_config=app.session;root.add_child(b)
	b.set_physics_process(false);b.set_process(false)
	await physics_frame;await physics_frame
	var rows=[]
	for i in Layout.BUILDINGS.size():
		var placement=Layout.BUILDINGS[i];var body=b.demo_arena_root.get_child(i)
		var expected=Vector2(float(placement[0]),float(placement[1]))
		check(Vector2(body.position.x,body.position.z).is_equal_approx(expected),"Building %d has its authored coordinates" % i)
		check(absf(wrapf(body.rotation.y-float(placement[2]),-PI,PI))<.001,"Building %d has its authored orientation" % i)
		check(absf(body.position.x)+18<b.terrain.extent and absf(body.position.z)+18<b.terrain.extent,"Building %d and its full footprint lie within the playable territory" % i)
		var hit=b.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(body.position+Vector3.UP*14,body.position-Vector3.UP,1))
		var physical_cover=not hit.is_empty() and body.is_ancestor_of(hit.collider)
		check(physical_cover,"Building %d has actual solid geometry above its foundation" % i)
		rows.append({"index":i,"position_m":[body.position.x,body.position.y,body.position.z],"yaw_deg":rad_to_deg(body.rotation.y),"actual_solid_cover":physical_cover})
	var result={"failures":failures,"buildings":rows}
	var output=ProjectSettings.globalize_path("res://../../build/validation/buildings.json")
	DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify(result,"  "))
	print("OPEN_DAY_BUILDINGS ",JSON.stringify(result));quit(1 if failures else 0)
