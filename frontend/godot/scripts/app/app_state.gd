extends Node
const Config=preload("res://scripts/app/session_config.gd")
var session=Config.new()
var settings={"preset":1,"fullscreen":false,"resolution":0,"shadows":true,"vegetation":1.0,"lod":1.0,"effects":1.0,"debug":false,"host":"127.0.0.1","port":8765,"audio":"no_audio"}
var root_path=""
var python=""
var view: Node
var battle
var backend_pid=-1
var job_pid=-1
var backend_state="NOT REQUIRED"
var status_path=""
var job_path=""
var last_output=""
var last_report={}
var generation=0
var current_page="MainMenu"
var loading_message="Preparing simulation…"
var backend_dialog_open=false
func _ready():
	root_path=OS.get_environment("FLYSWARM_ROOT")
	if root_path=="":root_path=ProjectSettings.globalize_path("res://../..").simplify_path()
	python=OS.get_environment("FLYSWARM_PYTHON")
	if python=="":python=root_path.path_join(".venv/bin/python")
	OS.set_environment("PYTHONPATH",root_path.path_join("src"))
	var file=ConfigFile.new()
	if file.load("user://settings.cfg")==OK:
		for key in settings:settings[key]=file.get_value("settings",key,settings[key])
	get_tree().auto_accept_quit=false
	apply_settings()
func apply_settings():
	if DisplayServer.get_name()=="headless":return
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if settings.fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)
	if not settings.fullscreen:DisplayServer.window_set_size([Vector2i(1280,800),Vector2i(1440,900),Vector2i(1920,1080)][int(settings.resolution)])
func save_settings():
	var file=ConfigFile.new()
	for key in settings:file.set_value("settings",key,settings[key])
	file.save("user://settings.cfg")
	apply_settings()
func results_root() -> String:
	if not OS.has_feature("editor"):return ProjectSettings.globalize_path("user://sessions")
	return root_path.path_join("results/raw/app")
func new_output(prefix: String) -> String:
	var path=results_root().path_join(prefix+"-"+Time.get_datetime_string_from_system().replace(":","-")+"-"+str(Time.get_ticks_msec()))
	DirAccess.make_dir_recursive_absolute(path)
	return path
func read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):return {}
	var parsed=JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}
func clear_view():
	if is_instance_valid(view):
		view.get_parent().remove_child(view)
		view.queue_free()
	view=null
func show_page(page: String):
	current_page=page
	clear_view()
	view=load("res://scenes/app/"+page+".tscn").instantiate()
	get_tree().root.add_child(view)
func configure(mode: String):
	session=Config.new()
	session.mode=mode
	session.audio_mode=settings.audio
	session.host=settings.host
	session.port=int(settings.port)
	if mode=="range":session.map="test_range";session.seconds=3600
	if mode=="training":session.battle_seed=100;session.seconds=2;session.blue_controller="brain";session.red_controller="brain"
	if mode=="research":session.seconds=5;session.blue_controller="brain";session.red_controller="brain"
	show_page({"battle":"HistoricalBattleSetup","range":"TestRangeSetup","training":"TrainingMenu","research":"ResearchLab"}[mode])
func stop_backend():
	if backend_pid>0 and OS.is_process_running(backend_pid):OS.kill(backend_pid)
	backend_pid=-1
	backend_state="NOT REQUIRED"
func stop_job():
	if job_path!="" and job_pid>0 and OS.is_process_running(job_pid):
		FileAccess.open(job_path.path_join("cancel"),FileAccess.WRITE).store_string("cancel")
func stop_session():
	generation+=1
	stop_job()
	stop_backend()
	if is_instance_valid(battle):
		if not battle.finished_report and not battle.replay_mode:battle.finish(false)
		battle.bridge.tcp.disconnect_from_host()
		if battle.recorder:battle.recorder.flush();battle.recorder.close();battle.recorder=null
		battle.get_parent().remove_child(battle)
		battle.queue_free()
	battle=null
	backend_dialog_open=false
func menu():
	stop_session()
	show_page("MainMenu")
func launch():
	var problem=session.validate()
	if problem!="":view.notice(problem);return
	generation+=1
	var token=generation
	show_page("LoadingScreen")
	loading_message="Preparing simulation…"
	await get_tree().process_frame
	if session.mode=="replay":
		var manifest=read_json(session.replay_path.get_base_dir().path_join("manifest.json"))
		if manifest.has("session"):
			var original=manifest.session
			session.map=original.get("map","krasny_valley")
			session.map_seed=int(original.get("map_seed",1944))
			session.vehicle_composition=original.get("vehicle_composition","mixed_1944")
			session.target_vehicle=original.get("target_vehicle","t34_85")
			session.training_vehicle=original.get("training_vehicle","tiger_i")
			session.range_distance=int(original.get("range_distance",500))
			session.target_angle=int(original.get("target_angle",0))
		else:session.map_seed=int(manifest.get("map_seed",1944))
	if session.needs_brain():
		var ok=await start_backend(token)
		if token!=generation:return
		if not ok:
			backend_state="ERROR"
			view.backend_unavailable(loading_message)
			return
	if token!=generation:return
	loading_message="Loading battlefield · spawning vehicles"
	await get_tree().process_frame
	session.output=new_output(session.mode) if session.mode!="replay" else ""
	last_output=session.output
	battle=load("res://scenes/TestRangeScene.tscn" if session.mode=="range" else "res://scenes/Battle.tscn").instantiate()
	battle.session_config=session
	battle.completed.connect(on_completed)
	battle.pause_requested.connect(pause_menu)
	battle.backend_failed.connect(on_backend_failed)
	get_tree().root.add_child(battle)
	clear_view()
	backend_state="READY" if session.needs_brain() else "NOT REQUIRED"
func start_backend(token: int) -> bool:
	stop_backend()
	if session.host not in ["localhost","127.0.0.1"]:
		loading_message="Only the local managed backend is supported. Choose localhost in Settings."
		return false
	if not FileAccess.file_exists(python):
		loading_message="Python environment is missing: "+python+". Rule AI and Test Range remain available."
		return false
	status_path=new_output("backend").path_join("status.json")
	var args=PackedStringArray(["-m","flyswarm.bridge.server","--port",str(session.port),"--seed",str(session.battle_seed),"--once","--status-file",status_path,"--parent-pid",str(OS.get_process_id()),"--blue-controller",session.blue_controller,"--red-controller",session.red_controller])
	for team in ["blue","red"]:
		if session.get(team+"_controller")=="adapter":args.append_array(["--"+team+"-policy",session.get(team+"_policy")])
	backend_state="STARTING"
	backend_pid=OS.create_process(python,args)
	var started=Time.get_ticks_msec()
	while token==generation and Time.get_ticks_msec()-started<120000:
		var state=read_json(status_path)
		loading_message=state.get("stage","Starting Python backend…")
		if state.get("stage","")=="READY":backend_state="CONNECTING";loading_message="Connecting backend";return true
		if state.get("error")!=null:loading_message=str(state.error);break
		if backend_pid<0 or not OS.is_process_running(backend_pid):loading_message="Backend exited. Check the Python environment and MaleCNS dataset.";break
		await get_tree().create_timer(.2).timeout
	if token!=generation:return false
	stop_backend()
	backend_state="ERROR"
	return false
func on_backend_failed(message: String):
	if backend_dialog_open:return
	backend_dialog_open=true
	backend_state="DISCONNECTED"
	battle.paused=true
	show_page("LoadingScreen")
	view.disconnect_dialog(message)
func reconnect():
	generation+=1
	show_page("LoadingScreen")
	var ok=await start_backend(generation)
	if not is_instance_valid(battle):return
	if ok:
		battle.bridge=load("res://scripts/bridge.gd").new()
		battle.bridge.connect_backend(session.port)
		battle.start_wall=Time.get_ticks_usec()
		battle.paused=false
		backend_dialog_open=false
		clear_view()
	else:view.disconnect_dialog(loading_message)
func pause_menu():
	if not is_instance_valid(battle):return
	battle.paused=true
	show_page("PauseMenu")
func resume():
	if is_instance_valid(battle):battle.paused=false
	clear_view()
func on_completed(report: Dictionary):
	last_report=report
	stop_backend()
	show_page("ResultsScreen")
func rerun():
	stop_session()
	launch()
func start_job(evaluate=false):
	if job_pid>0 and OS.is_process_running(job_pid):view.notice("The previous job is still stopping. Please retry shortly.");return
	var error=session.validate()
	if error!="":view.notice(error);return
	if not FileAccess.file_exists(python):view.notice("Python .venv is missing. Configure dependencies before starting this job.");return
	job_path=new_output("training" if session.mode=="training" else "research")
	var config=session.as_dict()
	config.output=job_path
	config.evaluate=evaluate
	config.godot=OS.get_executable_path()
	config.parent_pid=OS.get_process_id()
	FileAccess.open(job_path.path_join("job.json"),FileAccess.WRITE).store_string(JSON.stringify(config,"  "))
	job_pid=OS.create_process(python,[root_path.path_join("tools/app_job.py"),job_path.path_join("job.json")])
	backend_state="BUSY"
	show_page("JobProgress")
func _process(_dt):
	if current_page=="JobProgress" and job_path!="":
		var state=read_json(job_path.path_join("progress.json"))
		if state.get("state","") in ["complete","cancelled","error"]:
			backend_state="NOT REQUIRED"
		elif job_pid>0 and not OS.is_process_running(job_pid):
			backend_state="ERROR"
			state={"state":"error","message":"Worker exited unexpectedly; inspect the results folder."}
		if is_instance_valid(view):view.update_job(state)
func quit_app():
	stop_session()
	# Give the supervised job time to terminate its owned child processes.
	if job_pid>0:
		for attempt in range(30):
			if not OS.is_process_running(job_pid):break
			await get_tree().create_timer(.1).timeout
	get_tree().quit()
func _notification(what):
	if what==NOTIFICATION_WM_CLOSE_REQUEST:quit_app()
