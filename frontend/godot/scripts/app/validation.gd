extends SceneTree
var failed=0
var app
func check(condition: bool,message: String):
	if not condition:failed+=1;push_error(message)
func _initialize():call_deferred("run")
func wait_battle():
	for attempt in range(1500):
		if is_instance_valid(app.battle):return true
		if app.backend_state=="ERROR":return false
		await create_timer(.1).timeout
	return false
func run():
	app=root.get_node("AppState")
	for page in ["MainMenu","HistoricalBattleSetup","ResearchLab","TrainingMenu","TestRangeSetup","ReplayBrowser","Settings","LoadingScreen","ResultsScreen","PauseMenu","JobProgress"]:
		check(ResourceLoader.exists("res://scenes/app/"+page+".tscn"),"Missing "+page)
		app.show_page(page)
		await process_frame
		check(is_instance_valid(app.view),"Scene instantiation "+page)
	app.configure("range")
	app.session.training_vehicle="tiger_i"
	app.session.range_distance=1500
	app.launch()
	check(await wait_battle(),"Range starts")
	await physics_frame
	check(app.battle.is_range and app.battle.vehicles[0].cfg.id=="tiger_i","Tiger selection")
	check(app.battle.vehicles[8].position.z-app.battle.vehicles[0].position.z>1499,"1500 m spacing")
	var key=InputEventKey.new();key.physical_keycode=KEY_W;key.pressed=true;Input.parse_input_event(key)
	var before=app.battle.vehicles[0].position
	for frame in range(50):await physics_frame
	key.pressed=false;Input.parse_input_event(key)
	check(app.battle.vehicles[0].position.distance_to(before)>.2,"Manual Tiger drives")
	app.pause_menu();await process_frame
	check(app.battle.paused and app.current_page=="PauseMenu","Pause route")
	app.battle.save_replay()
	check(FileAccess.file_exists(app.battle.record_path.path_join("replay.jsonl")),"Save replay")
	app.menu();await process_frame
	check(app.battle==null and app.current_page=="MainMenu","Return without restarting")
	app.configure("battle");app.session.seconds=.3;app.launch()
	check(await wait_battle(),"Rule battle starts")
	for frame in range(50):await physics_frame
	check(app.current_page=="ResultsScreen","Battle reaches Results")
	check(app.last_report.vehicles.size()==16,"Actual 8v8 results")
	var replay_path=app.last_output.path_join("replay.jsonl")
	app.menu();app.session=app.Config.new();app.session.mode="replay";app.session.replay_path=replay_path;app.launch()
	check(await wait_battle(),"Replay starts")
	for frame in range(40):await physics_frame
	check(app.backend_pid<0 and app.current_page=="ResultsScreen","Replay completes without brain")
	app.menu()
	# Missing dependency must produce recovery controls, not terminate the app.
	var python=app.python;app.python="/missing/flyswarm-python"
	app.configure("battle");app.session.blue_controller="brain";app.launch()
	for frame in range(8):await process_frame
	check(app.view.find_child("UseRuleAi",true,false)!=null,"Missing backend offers Rule AI")
	app.python=python;app.menu()
	if "--real-brains" in OS.get_cmdline_user_args():
		app.configure("battle");app.session.blue_controller="brain";app.session.red_controller="brain";app.session.seconds=.2;app.launch()
		check(await wait_battle(),"Real brains loaded")
		for attempt in range(300):
			if app.current_page=="ResultsScreen":break
			await create_timer(.1).timeout
		check(app.current_page=="ResultsScreen","Neural battle completed")
		check(app.last_report.get("backend_metadata",{}).get("neuron_count",0)==2667200,"Two real batch8 populations")
		check(app.backend_pid<0,"Backend stopped on completion")
		app.menu()
	print("APPLICATION VALIDATION failures=",failed)
	app.stop_session();app.clear_view()
	await process_frame
	quit(0 if failed==0 else 1)
