extends SceneTree
var app
var failures=0
var screenshot_dir=""
var combat_policy=""
func check(condition: bool,message: String):
	if not condition:failures+=1;push_error(message)
func _initialize():call_deferred("run")
func wait_battle() -> bool:
	for attempt in range(900):
		if is_instance_valid(app.battle):return true
		if app.backend_state=="ERROR":return false
		await create_timer(.1).timeout
	return false
func run():
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--combat-policy="):combat_policy=argument.trim_prefix("--combat-policy=")
	screenshot_dir=ProjectSettings.globalize_path("res://../../artifacts/performance/open_day_real_validation")
	DirAccess.make_dir_recursive_absolute(screenshot_dir)
	app=root.get_node("AppState");app.configure_demo("t34_85");app.session.seconds=1.0
	if combat_policy!="":
		app.session.red_controller="adapter";app.session.red_policy=combat_policy
	app.launch()
	check(await wait_battle(),"Real Open Day battle starts")
	if not is_instance_valid(app.battle):
		print("OPEN DAY REAL BACKEND START FAILURE state=",app.backend_state," message=",app.loading_message)
		quit(1)
		return
	var battle=app.battle;var fly_start=battle.vehicles[8].position;battle.demo_intro_left=0;battle.demo_intro.visible=false
	for attempt in range(150):
		if app.current_page=="DemoResult" or (battle.bridge.connected() and battle.bridge.last_reply.has("traces")):break
		await create_timer(.1).timeout
	if app.current_page!="DemoResult":
		if DisplayServer.get_name()!="headless":
			await process_frame;await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(screenshot_dir.path_join("battle-live-malecns-1280x720.png"))
	for attempt in range(400):
		if app.current_page=="DemoResult":break
		await create_timer(.1).timeout
	check(app.current_page=="DemoResult","Demo reaches its dedicated result page")
	check(app.last_report.get("backend_metadata",{}).get("neuron_count",0)==166700,"Real single-brain MaleCNS demo metadata")
	check(app.last_report.get("backend_metadata",{}).get("brain_seeds",[]).size()==1,"Demo creates only the required real MaleCNS opponent")
	if combat_policy=="":
		check(app.last_report.get("brain","")=="BIOLOGICAL_BASELINE","Fly opponent uses biological baseline")
	else:
		var policy_ids=app.last_report.get("backend_metadata",{}).get("team_policy_ids",{})
		check(policy_ids.get("red",{}).get("male_cns_required",false),"Open Day loaded the real MaleCNS-trained PPO deployment")
		check(policy_ids.get("red",{}).get("schema","")=="flyswarm_malecns_combat_v2","Open Day loaded the versioned combat checkpoint schema")
		var layers=battle.bridge.last_reply.get("control_layers",[])
		check(layers.size()>8 and layers[8].get("adapter_action",null) is Array,"PPO supplied the opponent's actual action in the live Open Day backend")
	check(app.last_report.vehicles[8].position!=[fly_start.x,fly_start.y,fly_start.z],"MaleCNS opponent moves")
	check(app.last_report.vehicles[0].metrics.distance_travelled>0,"Mouse-only player default forward drive works")
	check(app.view.find_child("PlayAgain",true,false)!=null,"Fast restart control exists")
	if DisplayServer.get_name()!="headless":
		await process_frame;await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(screenshot_dir.path_join("demo-result-1280x720.png"))
	print("OPEN DAY REAL MALECNS failures=",failures," tick_ms=",app.last_report.get("brain_tick_ms")," xRT=",app.last_report.get("realtime_factor"))
	app.stop_session();app.clear_view();await process_frame;quit(0 if failures==0 else 1)
