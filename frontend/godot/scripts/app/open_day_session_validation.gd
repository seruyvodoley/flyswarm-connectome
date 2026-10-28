extends SceneTree

const Layout=preload("res://scripts/demo/arena_layout.gd")
var app
var failures=0
var previous_id=0
var previous_seed=-1

func check(value: bool,message: String):
	if not value:
		failures+=1
		push_error(message)

func _initialize():call_deferred("run")

func press(name: String):
	var button=app.view.find_child(name,true,false)
	check(button is Button,"Route button exists: "+name)
	if button is Button:button.pressed.emit()

func new_round() -> void:
	# Keep the real menu/launch path, substituting rule controls before the
	# first async loading frame. This test never starts or stops another worker.
	app.session.red_controller="rule"
	app.session.record=false
	for _i in 100:
		await process_frame
		if app.current_page=="Battle":break
	check(app.current_page=="Battle","A new battle reaches its active page")
	if not is_instance_valid(app.battle):return
	var b=app.battle
	check(b.get_instance_id()!=previous_id,"Every round owns a new scene instance")
	check(not b.finished_report and not b.ended and not b.paused,"New round has no terminal/pause flags")
	check(b.sim_time<1.0,"New round starts its own clock")
	check(app.last_report.is_empty(),"Previous round report is cleared on launch")
	check(b.vehicles[0].alive and b.vehicles[8].alive,"Both tanks start alive")
	check(b.vehicles[0].metrics.shots==0 and b.vehicles[8].metrics.shots==0,"Both shot counters restart at zero")
	check(b.vehicles[0].impact_history.is_empty() and b.vehicles[8].impact_history.is_empty(),"Damage history does not leak across rounds")
	check(previous_seed<0 or posmod(app.session.battle_seed,Layout.SPAWN_VARIANTS)!=posmod(previous_seed,Layout.SPAWN_VARIANTS),"Consecutive rounds use different spawn pairs")
	var scenes=0
	for node in root.get_children():
		if node.get_script()!=null and node.get_script().resource_path=="res://scripts/battle.gd":scenes+=1
	check(scenes==1,"Exactly one battle remains in the scene tree")
	previous_id=b.get_instance_id();previous_seed=app.session.battle_seed
	b.demo_intro_left=0
	for _i in 8:await physics_frame
	check(b.sim_time>0,"Fresh simulation advances after its intro")
	b.paused=true
	await physics_frame
	await b.prepare_demo_navigation()
	for seed_value in Layout.SPAWN_VARIANTS:
		for team in 2:
			check(b.demo_navigation.passable(Layout.spawn(team,seed_value)),"Spawn is navigable: %d / %d" % [seed_value,team])
		var a=b.demo_navigation.point(Layout.spawn(0,seed_value))+Vector3.UP*1.65
		var c=b.demo_navigation.point(Layout.spawn(1,seed_value))+Vector3.UP*1.65
		check(not b.demo_navigation.line_clear(a,c),"Village/terrain blocks the opening shot for pair %d" % seed_value)

func complete_round():
	app.battle.finish()
	check(app.current_page=="DemoResult","Completion opens results")
	check(app.battle.process_mode==Node.PROCESS_MODE_DISABLED and app.battle.paused,"Completed battle cannot process input, physics or camera updates behind menus")

func run():
	app=root.get_node("AppState")
	for _i in 2:await process_frame
	app.open_day_policy_mode="baseline"
	var points={}
	for seed_value in 120:
		var a=Layout.spawn(0,seed_value);var b=Layout.spawn(1,seed_value)
		check(absf(a.distance_to(b)-Layout.SPAWN_SEPARATION_M)<.001,"All seeded pairs have the same separation")
		points[str(a)]=true
	check(points.size()==Layout.SPAWN_VARIANTS,"All spawn placements are distinct")
	app.start_demo("t34_85")
	await new_round()
	complete_round()
	press("HowItWorks");await process_frame
	press("StartDemo");await new_round()
	complete_round()
	press("HowItWorks");await process_frame
	press("Back");await process_frame
	app.view.select_vehicle("panther_g")
	press("StartDemo");await new_round()
	check(app.battle.vehicles[0].cfg.id=="panther_g","Menu vehicle selection survives a post-result help detour")
	complete_round()
	press("PlayAgain");await new_round()
	check(app.battle.vehicles[0].cfg.id=="panther_g","Play Again keeps the selected vehicle")
	complete_round()
	app.resume()
	check(app.current_page=="OpenDayMain" and app.battle==null,"A finished battle can never be resumed")
	app.start_demo("tiger_i")
	app.session.red_controller="rule";app.session.record=false
	app.open_day_menu()
	for _i in 5:await process_frame
	check(app.current_page=="OpenDayMain" and app.battle==null,"Leaving during loading cancels the pending launch")
	app.clear_view()
	print("OPEN_DAY_SESSION failures=",failures," spawn_variants=",points.size()," separation_m=",Layout.SPAWN_SEPARATION_M)
	quit(1 if failures else 0)
