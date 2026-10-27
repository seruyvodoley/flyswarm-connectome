extends Node

const Tactics=preload("res://scripts/app/open_day_tactics.gd")
var failures=0
var baseline_script=""
var rows=[]
var aim_offset_key="demo_aim_vehicle_offset"

func check(ok: bool, message: String):
	if not ok:
		failures+=1
		push_error(message)

func _ready():call_deferred("run")

func make_battle(vehicle_id: String):
	var app=get_tree().root.get_node("AppState")
	app.configure_demo(vehicle_id)
	app.session.blue_controller="rule"
	app.session.red_controller="rule"
	app.session.demo_opponent=vehicle_id
	app.session.record=false
	app.session.battle_seed=7
	var battle=load(baseline_script).new() if baseline_script!="" else load("res://scenes/Battle.tscn").instantiate()
	battle.session_config=app.session
	get_tree().root.add_child(battle)
	battle.set_process(false)
	battle.set_physics_process(false)
	battle.paused=true
	battle.demo_gamepad_active=false
	battle.demo_intro_left=0.0
	battle.demo_intro.visible=false
	battle.sim_time=12.0
	battle.update_demo_smoke_screen()
	return battle

func camera_probe(battle, controller: bool=false) -> void:
	var vehicle=battle.vehicles[0]
	battle.demo_gamepad_active=controller
	battle.demo_camera_yaw=.35
	vehicle.position=Vector3(105,battle.terrain.height_at(105,0)+.1,0)
	vehicle.rotation.y=0
	vehicle.reset_physics_interpolation()
	await get_tree().physics_frame
	await get_tree().process_frame
	battle.demo_aim_world_valid=true
	battle.set(aim_offset_key,Vector3(40,3,100))
	battle.demo_aim_world_point=vehicle.position+battle.get(aim_offset_key)
	battle.last_camera_mode=-1
	var max_relative_step=0.0
	var max_aim_drift=0.0
	for scoped in [false,true]:
		battle.demo_set_sniper_mode(scoped)
		battle._process(1.0/120.0)
		var previous_camera=battle.camera.position
		var previous_vehicle=vehicle.get_global_transform_interpolated().origin
		for _frame in 120:
			await get_tree().physics_frame
			vehicle.position+=Vector3(.04,0,.08)
			vehicle.rotation.y+=.006
			vehicle.turret_angle+=.01
			vehicle.turret.rotation.y=vehicle.turret_angle
			vehicle.reset_physics_interpolation()
			await get_tree().process_frame
			battle._process(1.0/120.0)
			var rendered=vehicle.get_global_transform_interpolated().origin
			max_relative_step=maxf(max_relative_step,((battle.camera.position-previous_camera)-(rendered-previous_vehicle)).length())
			if not controller:max_aim_drift=maxf(max_aim_drift,(battle.demo_aim_world_point-rendered-battle.get(aim_offset_key)).length())
			previous_camera=battle.camera.position
			previous_vehicle=rendered
	check(battle.camera.physics_interpolation_mode==Node.PHYSICS_INTERPOLATION_MODE_OFF,"Render-driven camera must not be interpolated again at physics frequency")
	check(max_relative_step<.001,"Driving, hull/turret traverse and zoom must not drag the camera away from the displayed vehicle")
	check(max_aim_drift<.001,"Hull rotation must not rotate the selected world sight direction")
	rows.append({"scenario":"camera_translation_turn_and_scope","input":"controller" if controller else "mouse","max_relative_step_m":max_relative_step,"max_aim_drift_m":max_aim_drift})

func tactical_checks():
	var first=Tactics.new();first.configure(7)
	var second=Tactics.new();second.configure(7)
	check(first.flank_sign==second.flank_sign,"A match seed must reproduce the opening flank")
	var variations={}
	for seed_value in range(8):
		var tactic=Tactics.new();tactic.configure(seed_value);variations[tactic.flank_sign]=true
	check(variations.size()==2,"Opening seeds must use both route sides")
	check(Tactics.lead_position(Vector3.ZERO,Vector3(4,0,0),Vector3(2,0,0),.5).is_equal_approx(Vector3(2.25,0,0)),"Target acceleration must contribute one half a*t^2, not three halves")
	check(is_zero_approx(Tactics.aim_command(0.0,0.0,1.0,1.0)),"Neural motor bias must vanish at an acquired firing solution")
	check(is_equal_approx(Tactics.aim_command(0.0,.2,.4,0.0),-.5),"Turret aiming must compensate the rotating hull")

func run():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--baseline-script="):baseline_script=arg.trim_prefix("--baseline-script=")
	if baseline_script!="":aim_offset_key="demo_aim_vehicle_local_point"
	else:tactical_checks()
	get_tree().root.get_node("AppState").clear_view()
	var camera_battle=make_battle("t34_85")
	await get_tree().process_frame
	await camera_probe(camera_battle)
	await camera_probe(camera_battle,true)
	camera_battle.queue_free()
	await get_tree().process_frame
	for vehicle_id in ["t34_85","is2_1944","panther_g","tiger_i","jagdpanther","su100"]:
		var battle=make_battle(vehicle_id)
		await get_tree().physics_frame
		var player=battle.vehicles[0]
		var fly=battle.vehicles[8]
		if baseline_script=="":
			var saved_tilt=fly.model.rotation
			fly.model.rotation=Vector3(.12,0,-.08)
			var direction=Vector3(.3,.05,-1).normalized()
			var angles=fly.aim_angles_for_direction(direction)
			var reconstructed=fly.model.global_basis*Vector3(sin(angles.x)*cos(angles.y),sin(angles.y),cos(angles.x)*cos(angles.y))
			check(reconstructed.angle_to(direction)<.001,"%s aim must include terrain pitch and roll" % vehicle_id)
			fly.model.rotation=saved_tilt
			battle.is_demo=false
			check(is_equal_approx(fly.reload_duration(),float(fly.cfg.reload_s)),"%s research reload must retain the catalogue value" % vehicle_id)
			battle.is_demo=true
		player.position=Vector3(105,battle.terrain.height_at(105,-65)+.1,-65)
		fly.position=Vector3(105,battle.terrain.height_at(105,65)+.1,65)
		player.rotation.y=0.0
		fly.rotation.y=PI
		player.demo_health=1000
		player.demo_health_max=1000
		var modes={}
		for tick in 2000:
			await get_tree().physics_frame
			var dt=1.0/float(Engine.physics_ticks_per_second)
			# A moving, gently turning target plus conflicting neural motor bias.
			player.cmd=[.36,0.0,sin(float(tick)*dt*.4)*.24,0.0,0.0,0.0]
			player.step(dt)
			fly.cmd=battle.apply_demo_tactical_aux(fly,[.15,0.0,.1,.8,-.6,1.0],dt)
			fly.step(dt)
			battle.step_shells(dt)
			battle.sim_time+=dt
			if baseline_script=="":modes[str(battle.demo_tactical_plan.get("mode",""))]=true
		var penetrations=1000-player.demo_health
		var hits=player.impact_history.size()
		var result={"vehicle":vehicle_id,"shots":fly.metrics.shots,"hits":hits,"penetrations":penetrations,"distance_m":fly.metrics.distance_travelled,"tactical_modes":modes.keys()}
		rows.append(result)
		check(int(fly.metrics.shots)>=2,"%s must acquire and fire repeatedly at a moving target" % vehicle_id)
		check(hits>=1,"%s must hit the moving target" % vehicle_id)
		if baseline_script=="":
			check(is_equal_approx(player.reload_duration()-fly.reload_duration(),.5),"%s fly reload advantage must be exactly half a second" % vehicle_id)
			check(modes.has("hold"),"%s must stop on a useful firing solution" % vehicle_id)
			check(float(fly.metrics.distance_travelled)>=0.0,"%s motion metrics remain finite" % vehicle_id)
		battle.queue_free()
		await get_tree().process_frame
	print("OPEN_DAY_MOTION_COMBAT ",JSON.stringify({"baseline":baseline_script!="","failures":failures,"results":rows}))
	get_tree().quit(1 if failures else 0)
