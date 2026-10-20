extends SceneTree
var app
var failures=0
var screenshot_dir=""
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
	screenshot_dir=ProjectSettings.globalize_path("res://../../artifacts/performance/open_day_real_validation")
	DirAccess.make_dir_recursive_absolute(screenshot_dir)
	app=root.get_node("AppState");app.configure_demo("t34_85");app.session.seconds=1.0;app.launch()
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
		await process_frame;await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png(screenshot_dir.path_join("battle-live-malecns-1280x720.png"))
	for attempt in range(400):
		if app.current_page=="DemoResult":break
		await create_timer(.1).timeout
	check(app.current_page=="DemoResult","Demo reaches its dedicated result page")
	check(app.last_report.get("backend_metadata",{}).get("neuron_count",0)==166700,"Real single-brain MaleCNS demo metadata")
	check(app.last_report.get("backend_metadata",{}).get("brain_seeds",[]).size()==1,"Demo creates only the required real MaleCNS opponent")
	check(app.last_report.get("brain","")=="BIOLOGICAL_BASELINE","Fly opponent uses biological baseline")
	check(app.last_report.vehicles[8].position!=[fly_start.x,fly_start.y,fly_start.z],"MaleCNS opponent moves")
	check(app.last_report.vehicles[0].metrics.distance_travelled>0,"Mouse-only player default forward drive works")
	check(app.view.find_child("PlayAgain",true,false)!=null,"Fast restart control exists")
	await process_frame;await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(screenshot_dir.path_join("demo-result-1280x720.png"))
	print("OPEN DAY REAL MALECNS failures=",failures," tick_ms=",app.last_report.get("brain_tick_ms")," xRT=",app.last_report.get("realtime_factor"))
	app.stop_session();app.clear_view();await process_frame;quit(0 if failures==0 else 1)
