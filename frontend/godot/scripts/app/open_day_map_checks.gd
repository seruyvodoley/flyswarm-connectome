extends Node
const Layout=preload("res://scripts/demo/arena_layout.gd")
const Tactics=preload("res://scripts/app/open_day_tactics.gd")
var failures=0
var results={}
func check(ok: bool,message: String):
	if not ok:failures+=1;push_error(message)
func _ready():call_deferred("run")
func run():
	var app=get_tree().root.get_node("AppState");app.clear_view();app.configure_demo("t34_85")
	app.session.red_controller="rule";app.session.blue_controller="rule";app.session.record=false
	var b=load("res://scenes/Battle.tscn").instantiate();b.session_config=app.session;get_tree().root.add_child(b)
	b.set_process(false);b.set_physics_process(false);b.sim_time=12;b.demo_intro_left=0;b.update_demo_smoke_screen()
	await get_tree().physics_frame;await get_tree().physics_frame
	b.demo_navigation.configure(b);var nav=b.demo_navigation
	check(is_equal_approx(b.terrain.extent,350.0),"Open Day territory must be 700 × 700 metres")
	check(Layout.BUILDINGS.size()==10,"Ten authored building placements")
	var low=INF;var high=-INF;var grade=0.0
	for x in range(-330,331,10):
		for z in range(-330,331,10):
			var h=b.terrain.height_at(x,z);low=minf(low,h);high=maxf(high,h)
			grade=maxf(grade,Vector2(b.terrain.height_at(x+2,z)-h,b.terrain.height_at(x,z+2)-h).length()/2)
	check(high-low>10 and grade<.32,"Relief must influence visibility while retaining driveable slopes")
	var corridor_rows=[]
	for route in Layout.ROUTES:
		var length_m=0.0;var valid=true
		for i in range(route.size()-1):
			var path=nav.path(nav.point(route[i]),nav.point(route[i+1]))
			if path.size()<2:valid=false
			for j in range(1,path.size()):
				length_m+=path[j-1].distance_to(path[j])
				if not nav.drive_clear(path[j-1],path[j]):
					valid=false;print("BLOCKED_EDGE ",path[j-1]," -> ",path[j])
		check(valid,"Every segment of each of the three independent corridors has hull-width clearance")
		corridor_rows.append({"clear":valid,"length_m":length_m})
	for seed_value in range(8):
		for team in 2:
			var p=Layout.spawn(team,seed_value);check(nav.passable(p),"Seeded spawn has room for a full vehicle")
	check(not nav.line_clear(b.vehicles[0].position+Vector3.UP*1.65,b.vehicles[8].position+Vector3.UP*1.65),"Natural terrain/buildings, rather than smoke alone, block the opening shot")
	# Clear firing lane independent of village geometry, at three real distances.
	for distance in [100.0,180.0,240.0]:
		check(nav.line_clear(nav.point(Vector2(105,-distance*.5))+Vector3.UP*1.65,nav.point(Vector2(105,distance*.5))+Vector3.UP*1.65),"Field lane permits %d m gunnery" % distance)
	var detour=nav.path(nav.point(Vector2(-28,0)),nav.point(Vector2(35,0)))
	var detour_length=0.0
	for i in range(1,detour.size()):detour_length+=detour[i-1].distance_to(detour[i])
	check(detour_length>70.0,"A building crossing takes a geometric detour rather than a direct steering angle")
	var v=b.vehicles[8];var target=b.vehicles[0]
	v.position=nav.point(Vector2(105,90));target.position=nav.point(Vector2(105,-90));v.rotation.y=PI
	await get_tree().physics_frame
	var c=Tactics.new();c.configure(5)
	var held=c.update(12,v,target,nav,true,false,1,.02)
	var drive=c.drive(v,held.waypoint,held.holding,held.reverse,[1,0,1])
	check(held.mode=="hold" and drive[0]==0 and drive[1]==1,"180 m clear shot brakes rather than enforcing approach")
	c.next_decision=-1;target.velocity=Vector3(0,0,7);target.position=nav.point(Vector2(105,20));v.reload_left=2
	var retreat_start=v.position.distance_to(target.position)
	var retreat=c.update(14,v,target,nav,true,true,.4,.02)
	check(retreat.mode=="disengage" and retreat.goal.distance_to(target.position)>v.position.distance_to(target.position)+10 and retreat.route_remaining>0,"Threatened close-range reload selects a reachable withdrawal, away from the target")
	for tick in 1000:
		await get_tree().physics_frame
		var plan=c.update(14+tick*.02,v,target,nav,true,true,.4,.02)
		var movement=c.drive(v,plan.waypoint,plan.holding,plan.reverse,[0,0,0])
		v.cmd=[movement[0],movement[1],movement[2],0,0,0];v.step(.02)
	check(v.position.distance_to(target.position)>retreat_start+10.0,"Withdrawal must physically increase separation by ten metres")
	v.speed=0;v.yaw_rate=0;v.velocity=Vector3.ZERO;v.drive_throttle=0;v.rotation.y=PI
	v.position=nav.point(Vector2(-28,90));target.position=nav.point(Vector2(24,-180));target.velocity=Vector3.ZERO
	c=Tactics.new();c.configure(5)
	var flank=c.update(15,v,target,nav,false,false,1,.02)
	check(flank.mode=="flank" and flank.route_remaining>2,"Occluded target produces an actual multi-node alternative route")
	# Execute steering against the real vehicle/terrain collision implementation.
	var start=v.position;var max_motion=0.0
	for tick in 600:
		await get_tree().physics_frame
		var p=c.update(15+tick*.02,v,target,nav,false,false,1,.02)
		var motion=c.drive(v,p.waypoint,p.holding,p.reverse,[0,0,0])
		v.cmd=[motion[0],motion[1],motion[2],0,0,0];v.step(.02)
		max_motion=maxf(max_motion,start.distance_to(v.position))
	check(max_motion>15,"A planned flank must produce physical movement, not just a state name")
	v.position=nav.point(Vector2(-28,90));v.speed=0;v.yaw_rate=0;v.velocity=Vector3.ZERO;v.rotation.y=PI
	var seeds={}
	for seed_value in range(8):
		var controller=Tactics.new();controller.configure(seed_value)
		var plan=controller.update(12,v,target,nav,false,false,1,.02)
		seeds[str(plan.goal)]=true
	check(seeds.size()>1,"Different seeds select geometrically different feasible positions")
	c=Tactics.new();c.configure(5);c.last_seen=10
	var ambush=c.update(11,v,target,nav,false,false,1,.02)
	var search=c.update(20,v,target,nav,false,false,1,.02)
	check(ambush.holding and not search.holding and search.route_remaining>0,"A lost target permits only a bounded ambush before routed search")
	# Long immobility blacklists the current destination and commands reversal.
	c=Tactics.new();c.configure(1)
	for time in [20.0,21.3,22.6,23.9,25.2]:c.update(time,v,target,nav,false,false,1,.02)
	check(c.recoveries>0 and not c.blocked_goals.is_empty(),"Stalled motion changes destination and records a bounded reverse recovery")
	# Drive the entire western corridor using each actual vehicle's physics,
	# rather than inferring traversability from slopes alone.
	var route_vehicles=[]
	target.position=nav.point(Vector2(308,308))
	var full_path=PackedVector3Array()
	for segment in range(Layout.ROUTES[0].size()-1):
		var part=nav.path(nav.point(Layout.ROUTES[0][segment]),nav.point(Layout.ROUTES[0][segment+1]))
		for point in part:
			if full_path.is_empty() or full_path[-1].distance_to(point)>.1:full_path.append(point)
	for vehicle_id in ["t34_85","is2_1944","panther_g","tiger_i","jagdpanther","su100"]:
		v.queue_free();await get_tree().physics_frame
		v=load("res://scripts/vehicle.gd").new();b.add_child(v)
		v.setup(load("res://scripts/catalog.gd").vehicle(vehicle_id,false),8,b);b.vehicles[8]=v
		v.position=full_path[0];v.rotation.y=0;v.reset_physics_interpolation()
		var index=1;var ticks=0
		while index<full_path.size() and ticks<16000:
			await get_tree().physics_frame
			while index<full_path.size() and v.position.distance_to(full_path[index])<6.0:index+=1
			if index>=full_path.size():break
			var movement=c.drive(v,full_path[index],false,false,[0,0,0])
			v.cmd=[movement[0],movement[1],movement[2],0,0,0];v.step(.02);ticks+=1
		check(index==full_path.size(),vehicle_id+" must physically complete the full western route")
		route_vehicles.append({"vehicle":vehicle_id,"completed":index==full_path.size(),"sim_seconds":ticks*.02,"route_index":index,"position":v.position,"distance_m":v.metrics.distance_travelled,"stuck_recoveries":v.metrics.stuck_recoveries})
	results={"route_vehicles":route_vehicles,"extent_m":700,"buildings":10,"height_min_m":low,"height_max_m":high,"max_grade":grade,"corridors":corridor_rows,"flank_physical_motion_m":max_motion,"map_build_ms":b.demo_map_generation_ms,"nav_build_ms":nav.build_ms,"route_calls":nav.routes,"route_total_ms":nav.route_ms,"failures":failures}
	var output=ProjectSettings.globalize_path("res://../../build/validation/map-checks.json" if OS.has_feature("editor") else "user://validation/open-day-map.json")
	DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	var file=FileAccess.open(output,FileAccess.WRITE)
	if file!=null:file.store_string(JSON.stringify(results,"  "))

	print("OPEN_DAY_MAP ",JSON.stringify(results));get_tree().quit(1 if failures else 0)
