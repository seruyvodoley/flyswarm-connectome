extends SceneTree
var app
var failures=0
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
	app=root.get_node("AppState");app.configure_demo("t34_85");app.session.seconds=1.0;app.launch()
	check(await wait_battle(),"Real Open Day battle starts")
	if not is_instance_valid(app.battle):quit(1);return
	var battle=app.battle;var fly_start=battle.vehicles[8].position;battle.demo_intro_left=0;battle.demo_intro.visible=false
	for attempt in range(400):
		if app.current_page=="DemoResult":break
		await create_timer(.1).timeout
	check(app.current_page=="DemoResult","Demo reaches its dedicated result page")
	check(app.last_report.get("backend_metadata",{}).get("neuron_count",0)==2667200,"Real two-brain MaleCNS metadata")
	check(app.last_report.get("brain","")=="BIOLOGICAL_BASELINE","Fly opponent uses biological baseline")
	check(app.last_report.vehicles[8].position!=[fly_start.x,fly_start.y,fly_start.z],"MaleCNS opponent moves")
	check(app.last_report.vehicles[0].metrics.distance_travelled>0,"Mouse-only player default forward drive works")
	check(app.view.find_child("PlayAgain",true,false)!=null,"Fast restart control exists")
	print("OPEN DAY REAL MALECNS failures=",failures," tick_ms=",app.last_report.get("brain_tick_ms")," xRT=",app.last_report.get("realtime_factor"))
	app.stop_session();app.clear_view();await process_frame;quit(0 if failures==0 else 1)
