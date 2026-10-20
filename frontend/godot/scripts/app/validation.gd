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
	for page in ["MainMenu","HistoricalBattleSetup","ResearchLab","TrainingMenu","TestRangeSetup","ReplayBrowser","Settings","LoadingScreen","ResultsScreen","PauseMenu","JobProgress","OpenDayMain","HowItWorks","DemoResult"]:
		check(ResourceLoader.exists("res://scenes/app/"+page+".tscn"),"Missing "+page)
		app.show_page(page)
		await process_frame
		check(is_instance_valid(app.view),"Scene instantiation "+page)
		if page in ["LoadingScreen","JobProgress"]:
			check(not app.view.find_children("*","ProgressBar",true,false).is_empty(),page+" shows operation progress")

	var original_language=str(app.settings.get("language","en"))
	app.settings.language="ru"
	app.show_page("MainMenu")
	await process_frame
	var battle_button=app.view.find_child("AutonomousBattle",true,false)
	check(battle_button!=null and battle_button.text=="АВТОНОМНЫЙ БОЙ","Russian localization")
	var expression=RegEx.new();expression.compile("%[-+0-9.]*[sdf]")
	for key in app.I18n.EN:
		var en=[];var ru=[]
		for token in expression.search_all(app.I18n.t(key,"en")):en.append(token.get_string())
		for token in expression.search_all(app.I18n.t(key,"ru")):ru.append(token.get_string())
		check(en==ru,"Localized format arguments "+key)
		var args=[]
		for token in en:args.append("test" if token.ends_with("s") else 1)
		for language in ["en","ru"]:check(not app.I18n.format(key,language,args).is_empty(),"Format "+key)
	var saved_settings=FileAccess.get_file_as_string("user://settings.cfg")
	app.set_language("en")
	await process_frame
	var persisted=ConfigFile.new();persisted.load("user://settings.cfg")
	check(persisted.get_value("settings","language")=="en","Language persisted")
	FileAccess.open("user://settings.cfg",FileAccess.WRITE).store_string(saved_settings)
	app.settings.language=original_language
	app.show_page("MainMenu")
	await process_frame
	app.show_page("Settings")
	await process_frame
	check(app.view.find_child("DatasetCheckProgress",true,false) is ProgressBar,"MaleCNS data check exposes an indeterminate status bar")
	var unavailable_dataset := ProjectSettings.globalize_path("res://dataset-check-unavailable")
	check(app.request_malecns_dataset_validation(unavailable_dataset),"MaleCNS data check starts asynchronously")
	for _attempt in 300:
		if app.dataset_validation_state != "checking":break
		await create_timer(.1).timeout
	check(app.dataset_validation_state=="error" and not app.dataset_validation_result.get("ready",false),"MaleCNS data check reports invalid data after the worker completes (state=%s result=%s)" % [app.dataset_validation_state,str(app.dataset_validation_result)])
	app.show_page("MainMenu")
	await process_frame
	app.configure("range")
	app.session.training_vehicle="tiger_i"
	app.session.range_distance=1500
	app.launch()
	check(await wait_battle(),"Range starts")
	await physics_frame
	check(app.battle.camera_mode==1,"Range defaults to follow")
	check(app.battle.is_range and app.battle.vehicles[0].cfg.id=="tiger_i","Tiger selection")
	check(app.battle.vehicles[8].position.z-app.battle.vehicles[0].position.z>1499,"1500 m spacing")
	# Mouse presses must survive even if the click is released before a physics tick.
	var range_tiger=app.battle.vehicles[0]
	range_tiger.modules.gunner=true;range_tiger.modules.breech=true;range_tiger.ammo_left=20;range_tiger.reload_left=0.0
	var range_shots_before=int(range_tiger.metrics.shots)
	var range_lmb=InputEventMouseButton.new();range_lmb.button_index=MOUSE_BUTTON_LEFT;range_lmb.pressed=true;range_lmb.position=Vector2(640,360)
	Input.parse_input_event(range_lmb)
	var range_lmb_release=range_lmb.duplicate();range_lmb_release.pressed=false;Input.parse_input_event(range_lmb_release)
	for _tick in 4:await physics_frame
	check(int(range_tiger.metrics.shots)==range_shots_before+1 and not app.battle.mouse_fire_pending,"A brief routed LMB click fires exactly one range round")
	range_tiger.reload_left=0.0;range_tiger.modules.breech=false
	var ammo_before_blocked=range_tiger.ammo_left
	Input.parse_input_event(range_lmb.duplicate())
	Input.parse_input_event(range_lmb_release.duplicate())
	for _tick in 4:await physics_frame
	check(int(range_tiger.metrics.shots)==range_shots_before+1 and range_tiger.ammo_left==ammo_before_blocked,"A disabled breech prevents firing without spending ammunition")
	check(range_tiger.weapon_block_reason()=="breech" and app.battle.gunner_reticle.block_message() in ["BREECH DISABLED","КАЗЁННИК СЛОМАН"],"The sight explains why a damaged gun cannot fire")
	range_tiger.modules.breech=true
	var key=InputEventKey.new();key.physical_keycode=KEY_W;key.pressed=true;Input.parse_input_event(key)
	var before=app.battle.vehicles[0].position
	for frame in range(50):await physics_frame
	key.pressed=false;Input.parse_input_event(key)
	check(app.battle.vehicles[0].position.distance_to(before)>.1,"Manual Tiger drives")
	app.pause_menu();await process_frame
	check(app.battle.paused and app.current_page=="PauseMenu","Pause route")
	app.battle.save_replay()
	check(FileAccess.file_exists(app.battle.record_path.path_join("replay.jsonl")),"Save replay")
	app.menu();await process_frame
	check(app.battle==null and app.current_page=="MainMenu","Return without restarting")
	app.configure("battle");app.session.seconds=.3;app.launch()
	check(await wait_battle(),"Rule battle starts")
	check(app.battle.camera_mode==0,"Autonomous battle defaults to Battlefield camera")
	check(not app.battle.vehicle_status_panel.visible and not app.battle.should_show_impact(app.battle.vehicles[0],app.battle.vehicles[8]),"Observer mode has no per-vehicle damage overlays")
	app.battle.camera_mode=1;app.battle.update_vehicle_status()
	check(app.battle.vehicle_status_panel.visible and app.battle.vehicle_status_map.vehicle==app.battle.vehicles[0] and app.battle.should_show_impact(app.battle.vehicles[0],app.battle.vehicles[8]) and not app.battle.should_show_impact(app.battle.vehicles[1],app.battle.vehicles[8]),"Only the selected shooter receives the correct enemy hit report and 2D own-tank map")
	check(app.battle.impact_killcam.offset_bottom<app.battle.previous_vehicle_button.offset_top,"Battle impact camera clears tank-switch controls")
	app.battle.impact_killcam.show_impact({"source_id":0,"source_name":"B1","target_name":"R1 Panther G","vehicle_id":"panther_g","impact":{}})
	app.battle.select_vehicle(1);app.battle.update_vehicle_status()
	check(not app.battle.impact_killcam.visible and app.battle.vehicle_status_text.text.contains(app.battle.vehicles[1].cfg.display_name) and app.battle.vehicle_status_map.vehicle==app.battle.vehicles[1],"Switching tanks clears old impact and shows new tank schematic")
	app.battle.camera_mode=0;await process_frame
	check(is_instance_valid(app.battle.camera_button),"Camera UI button")
	check(is_instance_valid(app.battle.comm_toggle),"Communication UI button")
	await process_frame
	check(app.battle.camera.projection==Camera3D.PROJECTION_ORTHOGONAL,"Overview orthographic")
	check(not app.battle.observer_environment.fog_enabled,"Overview has no fog")
	check(app.battle.camera.global_basis.z.dot(Vector3.UP)>.99,"Camera looks down")
	for mode in [1,2,3,0]:
		app.battle.cycle_camera();await process_frame
		check(app.battle.camera_mode==mode,"Camera cycle")
		check(app.battle.camera.projection==(Camera3D.PROJECTION_ORTHOGONAL if mode==0 else Camera3D.PROJECTION_PERSPECTIVE),"Projection transition")
		app.battle.update_vehicle_status()
		check(app.battle.vehicle_status_panel.visible==(mode in [1,2]),"Damage schematic obeys every camera mode")
	for mode in [1,2,3,0]:
		app.battle.cycle_comms();check(app.battle.comm_view==mode,"Comms cycle")
	app.battle.ingest_communication(null)
	app.battle.ingest_communication({"sample":1,"events":[null,{"sender":[],"receiver":1}]})
	app.battle.ingest_communication({"sample":2,"events":[{"sender":0,"receiver":1,"raw":2.0,"received":.1,"distance_m":20.0}]})
	var count=app.battle.comm_history.size()
	app.battle.ingest_communication({"sample":2,"events":[{"sender":0,"receiver":1,"raw":2.0,"received":.1,"distance_m":20.0}]})
	check(app.battle.comm_history.size()==count,"Replay sample deduplication")
	check(app.battle.comm_event_visible({"sender":0})==false,"Off filter")
	app.battle.comm_view=1;check(app.battle.comm_event_visible({"sender":8}) and not app.battle.comm_event_visible({"sender":0}),"Red sender filter")
	app.battle.comm_view=2;check(app.battle.comm_event_visible({"sender":0}) and not app.battle.comm_event_visible({"sender":8}),"Blue sender filter")
	app.battle.comm_view=0
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
		app.configure("battle");app.session.blue_controller="brain";app.session.red_controller="brain";app.session.seconds=1.0;app.session.audio_mode="team_audio";app.launch()
		check(await wait_battle(),"Real brains loaded")
		for attempt in range(300):
			if app.current_page=="ResultsScreen":break
			await create_timer(.1).timeout
		check(app.current_page=="ResultsScreen","Neural battle completed")
		check(app.last_report.get("backend_metadata",{}).get("neuron_count",0)==2667200,"Two real batch8 populations")
		check(app.backend_pid<0,"Backend stopped on completion")
		var comm=app.last_report.get("communication",{})
		check(comm.get("sample",-1)>=4,"Multiple real communication samples")
		check(comm.get("song_out",[]).size()==16 and comm.get("heard_total",[]).size()==16,"Real telemetry vectors")
		for event in comm.get("events",[]):
			check(event.sender>=0 and event.sender<16 and event.receiver>=0 and event.receiver<16 and event.received>=0 and event.distance_m>=0,"Real communication event")
		print("REAL COMMUNICATION sample=",comm.get("sample")," events=",comm.get("events",[]).size()," bytes=",JSON.stringify(comm).to_utf8_buffer().size())
		var real_replay=app.last_output.path_join("replay.jsonl")
		app.menu();app.session=app.Config.new();app.session.mode="replay";app.session.replay_path=real_replay;app.launch()
		check(await wait_battle(),"Neural replay offline")
		app.battle.cycle_comms()
		for frame in range(80):await physics_frame
		check(app.backend_pid<0 and app.current_page=="ResultsScreen","Neural replay completes without backend")
		app.menu()
		for controllers in [["rule","brain"],["brain","rule"]]:
			app.configure("battle")
			app.session.blue_controller=controllers[0]
			app.session.red_controller=controllers[1]
			app.session.seconds=.4
			app.launch()
			check(await wait_battle(),"Mixed controller battle starts: "+str(controllers))
			for attempt in range(300):
				if app.current_page=="ResultsScreen":break
				await create_timer(.1).timeout
			check(app.current_page=="ResultsScreen","Mixed controller battle completes: "+str(controllers))
			check(app.last_report.vehicles.size()==16,"Mixed controller battle retains 8v8")
			app.menu()
	print("APPLICATION VALIDATION failures=",failed)
	app.stop_session();app.clear_view()
	await process_frame
	quit(0 if failed==0 else 1)
