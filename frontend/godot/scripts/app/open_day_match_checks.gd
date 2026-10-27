extends Node
var app
var battle
var rows=[]
var failures=0
var count=5
var seconds=120.0
var rule=false
var frame_ms:Array[float]=[]
var previous_usec=0
var sampling=false
var output=""
var screenshots=""
var fire_elapsed=0.0

func check(ok: bool,message: String):
	if not ok:failures+=1;push_error(message)
func _ready():call_deferred("run")
func _process(_dt):
	if sampling:
		var now=Time.get_ticks_usec()
		if previous_usec>0:frame_ms.append((now-previous_usec)/1000.0)
		previous_usec=now
func _physics_process(dt):
	if not sampling or not is_instance_valid(battle) or battle.finished_report:return
	# Repeatable mouse test input, not a human-play result: track the target and
	# click when the actual player gun is aligned. Locomotion uses the real UI's
	# mouse autopilot; the opponent always receives unmodified real CNS replies.
	var p=battle.vehicles[0];var t=battle.vehicles[8]
	if not p.alive or not t.alive:return
	var distance=p.position.distance_to(t.position)
	var flight=distance/float(p.cfg.ammo_data.muzzle_velocity_m_s)
	var lead=t.position+Vector3.UP*1.45+(t.velocity-p.velocity)*flight+Vector3.UP*4.905*flight*flight
	battle.demo_aim_world_valid=true;battle.demo_aim_world_point=lead
	battle.demo_aim_vehicle_offset=lead-p.get_global_transform_interpolated().origin
	battle.demo_update_aim_from_world_point(p,lead)
	fire_elapsed+=dt
	if fire_elapsed>.3 and battle.has_los(p,t) and absf(wrapf(p.manual_turret_target-p.turret_angle,-PI,PI))<.02 and absf(p.manual_gun_target-p.gun_angle)<.02:
		battle.mouse_fire_pending=true;fire_elapsed=0

func run():
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--matches="):count=clampi(int(arg.trim_prefix("--matches=")),1,5)
		if arg.begins_with("--seconds="):seconds=clampf(float(arg.trim_prefix("--seconds=")),20,180)
		if arg.begins_with("--output="):output=arg.trim_prefix("--output=")
		if arg.begins_with("--screenshots="):screenshots=arg.trim_prefix("--screenshots=")
		if arg=="--rule":rule=true
	if output=="":output=ProjectSettings.globalize_path("res://../../build/validation/five-matches.json" if OS.has_feature("editor") else "user://validation/five-matches.json")
	app=get_tree().root.get_node("AppState")
	app.clear_view();app.settings.fullscreen=false;app.settings.resolution=0
	app.settings.shadows=true;app.settings.vegetation=.6
	if OS.has_environment("FLY_DATA"):app.settings.dataset_path=OS.get_environment("FLY_DATA")
	var viewport=get_tree().root
	if DisplayServer.get_name()!="headless":
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_size(Vector2i(1280,800))
		viewport.content_scale_mode=Window.CONTENT_SCALE_MODE_VIEWPORT
		viewport.content_scale_size=Vector2i(1280,800)
	var ids=["t34_85","panther_g","su100","tiger_i","jagdpanther"]
	for index in count:
		app.configure_demo(ids[index]);app.session.record=false;app.session.seconds=seconds
		app.session.battle_seed=204+index;app.session.map_seed=1944+index
		if rule:app.session.red_controller="rule"
		await app.launch()
		var started=Time.get_ticks_msec()
		while not is_instance_valid(app.battle) and Time.get_ticks_msec()-started<120000:await get_tree().create_timer(.1).timeout
		check(is_instance_valid(app.battle),"Real battle must start")
		if not is_instance_valid(app.battle):break
		battle=app.battle;battle.demo_gamepad_active=false;battle.demo_intro_left=0;battle.demo_intro.hide()
		frame_ms.clear();previous_usec=0;sampling=true;fire_elapsed=0
		var expires=Time.get_ticks_msec()+int((seconds*5+120)*1000)
		var next_trace=0.0;var trace=[];var exposed=0.0;var last_time=0.0
		var capture_done=false
		while not battle.finished_report and Time.get_ticks_msec()<expires:
			await get_tree().create_timer(.2).timeout
			if battle.has_los(battle.vehicles[8],battle.vehicles[0]):exposed+=battle.sim_time-last_time
			last_time=battle.sim_time
			if battle.sim_time>=next_trace:
				trace.append({"time":battle.sim_time,"fly":[battle.vehicles[8].position.x,battle.vehicles[8].position.z],"player":[battle.vehicles[0].position.x,battle.vehicles[0].position.z],"mode":battle.demo_tactical_plan.get("mode",""),"fly_shots":battle.vehicles[8].metrics.shots,"player_motion":battle.vehicles[0].cmd.slice(0,3),"player_plan":app.battle.demo_player_tactics.plan_cache,"player_yaw":battle.vehicles[0].rotation.y,"player_speed":battle.vehicles[0].speed,"distance":battle.vehicles[0].position.distance_to(battle.vehicles[8].position)})
				next_trace=battle.sim_time+5
			if not capture_done and screenshots!="" and battle.vehicles[8].metrics.shots>0 and DisplayServer.get_name()!="headless":
				DirAccess.make_dir_recursive_absolute(screenshots)
				await RenderingServer.frame_post_draw
				viewport.get_texture().get_image().save_png(screenshots.path_join("live-match-%d.png" % (index+1)))
				capture_done=true
		sampling=false
		check(battle.finished_report,"Match must finish by destruction or time limit")
		var report=battle.report_cache
		var p=battle.vehicles[0];var f=battle.vehicles[8]
		var perf=battle.sample_statistics(frame_ms)
		var result={"seed":204+index,"vehicle":ids[index],"seconds":battle.sim_time,"completion":report.get("completion","missing"),"winner":"draw" if p.alive==f.alive else ("player" if p.alive else "fly"),"fly_shots":f.metrics.shots,"fly_hits":p.impact_history.size(),"player_shots":p.metrics.shots,"player_hits":f.impact_history.size(),"fly_distance_m":f.metrics.distance_travelled,"direct_exposure_s":exposed,"shot_ranges_m":report.get("demo_shot_ranges",{}),"tactics":report.get("demo_tactics",{}),"navigation":report.get("demo_navigation",{}),"stuck_recoveries":f.metrics.stuck_recoveries,"neural_responses":battle.bridge.responses_received,"neuron_count":report.get("backend_metadata",{}).get("neuron_count",0),"backend_disconnects":battle.bridge.disconnect_count,"map_build_ms":battle.demo_map_generation_ms,"native_renderer":RenderingServer.get_video_adapter_name() if DisplayServer.get_name()!="headless" else "headless","frame_ms":perf if DisplayServer.get_name()!="headless" else null,"fps":1000.0/float(perf.mean) if DisplayServer.get_name()!="headless" and perf.mean!=null else null,"viewport_px":viewport.get_texture().get_size() if DisplayServer.get_name()!="headless" else null,"trace":trace}
		if not rule:
			check(result.neural_responses>10 and result.neuron_count==166700,"Full MaleCNS must produce repeated real responses")
			check(result.backend_disconnects==0,"No silent backend disconnect")
		check(result.fly_shots>0,"Opponent must find a firing solution in a full match")
		rows.append(result);print("OPEN_DAY_MATCH ",JSON.stringify(result))
		DirAccess.make_dir_recursive_absolute(output.get_base_dir())
		FileAccess.open(output,FileAccess.WRITE).store_string(JSON.stringify({"rule_only":rule,"synthetic_player_input":true,"failures":failures,"matches":rows},"  "))
		app.stop_session();app.clear_view();await get_tree().process_frame
	print("OPEN_DAY_MATCHES failures=",failures)
	get_tree().quit(1 if failures or rows.size()!=count else 0)
