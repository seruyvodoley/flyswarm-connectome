extends Node
const Config=preload("res://scripts/app/session_config.gd")
const I18n=preload("res://scripts/app/i18n.gd")
const OpenDayController=preload("res://scripts/app/open_day_controller.gd")
var session=Config.new()
var settings={"preset":1,"fullscreen":false,"resolution":0,"shadows":true,"vegetation":.6,"lod":1.0,"effects":1.0,"debug":false,"host":"127.0.0.1","port":8765,"audio":"no_audio","language":"en","appearance":"dark","dataset_path":"","environment_profile":"enhanced_visual"}
var root_path=""
var python=""
var packaged_app=false
var bundle_resources=""
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
# A controller gesture is consumed once, on crossing the engage threshold.
# It is re-armed only after BOTH left-stick axes return close to centre.
const MENU_STICK_ENGAGE := 0.65
const MENU_STICK_RELEASE := 0.28
var menu_axes: Dictionary={}
var menu_stick_latches: Dictionary={}

var loading_message="Preparing simulation…"
var backend_dialog_open=false
var open_day_mode=false
var marl_pid=-1
var marl_output=""
var marl_replay_path=""
var marl_progress={}
var dataset_validation_thread: Thread
var dataset_validation_state := "idle"
var dataset_validation_result: Dictionary = {}
var dataset_validation_path := ""
var marl_poll_elapsed := 0.0
var job_poll_elapsed := 0.0
func _ready():
	OpenDayController.configure()
	packaged_app=not OS.has_feature("editor")
	if packaged_app:
		bundle_resources=packaged_resources_path()
		root_path=bundle_resources.path_join("support")
		python=packaged_backend_path()
		OS.unset_environment("PYTHONPATH")
	else:
		root_path=OS.get_environment("FLYSWARM_ROOT")
		if root_path=="":root_path=ProjectSettings.globalize_path("res://../..").simplify_path()
		python=OS.get_environment("FLYSWARM_PYTHON")
		if python=="":python=developer_python_path()
		OS.set_environment("PYTHONPATH",root_path.path_join("src"))
	var file=ConfigFile.new()
	if file.load("user://settings.cfg")==OK:
		for key in settings:settings[key]=file.get_value("settings",key,settings[key])
	if str(settings.dataset_path)=="":
		var bundled_dataset=bundle_resources.path_join("MaleCNS") if packaged_app else ""
		if not bundled_dataset.is_empty() and FileAccess.file_exists(bundled_dataset.path_join("brain.npz")) and FileAccess.file_exists(bundled_dataset.path_join("weights.npz")):
			settings.dataset_path=bundled_dataset
		else:
			settings.dataset_path=OS.get_environment("FLY_DATA")
			if str(settings.dataset_path)=="":settings.dataset_path=user_home_path().path_join("fly-data")
	if not settings.language in I18n.LANGUAGES:settings.language="en"
	if str(settings.appearance) not in ["dark", "light"]:settings.appearance="dark"
	get_tree().auto_accept_quit=false
	apply_settings()

func _input(event: InputEvent) -> void:
	# Only the application menus are handled here. The active tank battle
	# keeps its own analog controls; modal FileDialogs handle their own input.
	if not is_instance_valid(view):return
	if current_page not in ["MainMenu","OpenDayMain","HowItWorks","DemoResult","HistoricalBattleSetup","ResearchLab","TrainingMenu","TestRangeSetup","ReplayBrowser","Settings","LoadingScreen","ResultsScreen","PauseMenu","JobProgress","MarlLaboratory","MarlViewer"]:return
	for popup in view.find_children("*","Window",true,false):
		if popup is Window and popup.visible:return
	if event is InputEventJoypadMotion:
		if event.axis not in [JoyAxis.JOY_AXIS_LEFT_X,JoyAxis.JOY_AXIS_LEFT_Y]:return
		var axes: Vector2=menu_axes.get(event.device,Vector2.ZERO)
		if event.axis==JoyAxis.JOY_AXIS_LEFT_X:axes.x=event.axis_value
		else:axes.y=event.axis_value
		menu_axes[event.device]=axes
		get_viewport().set_input_as_handled()
		if maxf(absf(axes.x),absf(axes.y))<=MENU_STICK_RELEASE:
			menu_stick_latches[event.device]=false
			return
		if menu_stick_latches.get(event.device,false):return
		if maxf(absf(axes.x),absf(axes.y))<MENU_STICK_ENGAGE:return
		menu_stick_latches[event.device]=true
		if absf(axes.x)>absf(axes.y):_menu_move(Vector2.RIGHT if axes.x>0.0 else Vector2.LEFT)
		else:_menu_move(Vector2.DOWN if axes.y>0.0 else Vector2.UP)
		return
	if not event is InputEventJoypadButton or not event.pressed:return
	var direction=Vector2.ZERO
	match event.button_index:
		JoyButton.JOY_BUTTON_DPAD_UP:direction=Vector2.UP
		JoyButton.JOY_BUTTON_DPAD_DOWN:direction=Vector2.DOWN
		JoyButton.JOY_BUTTON_DPAD_LEFT:direction=Vector2.LEFT
		JoyButton.JOY_BUTTON_DPAD_RIGHT:direction=Vector2.RIGHT
		JoyButton.JOY_BUTTON_A:
			get_viewport().set_input_as_handled()
			_menu_activate()
			return
		JoyButton.JOY_BUTTON_B,JoyButton.JOY_BUTTON_START:
			get_viewport().set_input_as_handled()
			if current_page=="PauseMenu":resume()
			elif event.button_index==JoyButton.JOY_BUTTON_B:
				if current_page=="OpenDayMain":research_menu()
				elif current_page in ["HowItWorks","DemoResult"]:open_day_menu()
				elif current_page=="MarlViewer":show_page("MarlLaboratory")
				else:menu()
			return
		_:return
	get_viewport().set_input_as_handled()
	_menu_move(direction)

func _menu_targets() -> Array[Control]:
	var controls: Array[Control]=[]
	if not is_instance_valid(view):return controls
	for node in view.find_children("*","Control",true,false):
		if not node is Control:continue
		var control: Control=node
		if not control.is_visible_in_tree() or control.focus_mode==Control.FOCUS_NONE:continue
		if control is BaseButton:
			var button: BaseButton=control
			if button.disabled:continue
		if control is LineEdit and control.get_parent() is SpinBox:continue
		if control is BaseButton or control is SpinBox or control is LineEdit or control is ItemList or control is Slider:
			controls.append(control)
	return controls

func _focus_initial_menu_control() -> void:
	if not is_instance_valid(view):return
	var current=get_viewport().gui_get_focus_owner()
	if current!=null and view.is_ancestor_of(current):return
	var targets=_menu_targets()
	if not targets.is_empty():targets[0].grab_focus()

func _menu_move(direction: Vector2) -> void:
	var controls=_menu_targets()
	if controls.is_empty():return
	var focused: Control=get_viewport().gui_get_focus_owner()
	if not focused in controls:
		controls[0].grab_focus()
		return
	# A replay list has its own selectable cells. Advance one row per gesture.
	if focused is ItemList and direction.y!=0.0:
		var list: ItemList=focused
		if list.item_count>0:
			var selected=list.get_selected_items()
			var index=selected[0] if not selected.is_empty() else 0
			var next_index=index+int(direction.y)
			if next_index>=0 and next_index<list.item_count:
				list.select(next_index)
				list.ensure_current_is_visible()
				return
	var origin=focused.get_global_rect().get_center()
	var nearest: Control=null
	var best_score=INF
	for candidate in controls:
		if candidate==focused:continue
		var offset=candidate.get_global_rect().get_center()-origin
		var forward=offset.dot(direction)
		if forward<5.0:continue
		var lateral=absf(offset.cross(direction))
		var score=forward+lateral*2.5
		if score<best_score:
			best_score=score
			nearest=candidate
	if nearest!=null:nearest.grab_focus()

func _menu_activate() -> void:
	var focused: Control=get_viewport().gui_get_focus_owner()
	if not focused in _menu_targets():return
	if focused is OptionButton:
		var option: OptionButton=focused
		option.show_popup()
	elif focused is BaseButton:
		var button: BaseButton=focused
		if button.toggle_mode:button.button_pressed=not button.button_pressed
		button.pressed.emit()
	elif focused is ItemList:
		var list: ItemList=focused
		var selection=list.get_selected_items()
		if not selection.is_empty():list.item_activated.emit(selection[0])
	elif focused is SpinBox:
		var spin: SpinBox=focused
		spin.get_line_edit().grab_focus()
func windows_host() -> bool:
	return OS.get_name()=="Windows"
func user_home_path() -> String:
	var home=OS.get_environment("HOME")
	if home=="":home=OS.get_environment("USERPROFILE")
	return home
func developer_python_path() -> String:
	if windows_host():return root_path.path_join(".venv/Scripts/python.exe")
	return root_path.path_join(".venv/bin/python")
func packaged_resources_path() -> String:
	var executable_dir=OS.get_executable_path().get_base_dir()
	if OS.get_name()=="macOS":return executable_dir.path_join("../Resources").simplify_path()
	return executable_dir.path_join("Resources")
func packaged_backend_path() -> String:
	var executable="FlySwarmBackend.exe" if windows_host() else "FlySwarmBackend"
	return bundle_resources.path_join("backend/FlySwarmBackend").path_join(executable)
func apply_settings():
	if DisplayServer.get_name()=="headless":return
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if settings.fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)
	if not settings.fullscreen:DisplayServer.window_set_size([Vector2i(1280,800),Vector2i(1440,900),Vector2i(1920,1080)][int(settings.resolution)])
func persist_settings():
	var file=ConfigFile.new()
	for key in settings:file.set_value("settings",key,settings[key])
	file.save("user://settings.cfg")
func save_settings():
	persist_settings()
	apply_settings()
func tr_text(text: String) -> String:
	return I18n.t(text,str(settings.get("language","en")))

func tr_format(key: String,args: Array) -> String:
	return I18n.format(key,str(settings.get("language","en")),args)

func validate_malecns_dataset(path: String) -> Dictionary:
	var result := _run_malecns_dataset_check(path)
	_apply_malecns_dataset_result(path, result)
	return result

func _run_malecns_dataset_check(path: String) -> Dictionary:
	if path.strip_edges()=="":return {"ready":false,"error":"Select a folder first"}
	var args=PackedStringArray()
	if packaged_app:args.append_array(["--check-data","--data-dir",path])
	else:args.append_array(["-m","flyswarm.bridge.server","--check-data","--data-dir",path])
	var output: Array=[]
	var exit_code=OS.execute(python,args,output,true)
	for line in output:
		var parsed=JSON.parse_string(line)
		if parsed is Dictionary:return parsed if exit_code==0 else {"ready":false,"error":str(parsed.get("error","Dataset check failed (exit %d)" % exit_code))}
	return {"ready":false,"error":"Dataset check failed (exit %d): %s" % [exit_code,"\n".join(output)]}

func _apply_malecns_dataset_result(path: String, result: Dictionary) -> void:
	if result.get("ready",false):
		settings.dataset_path=path
		OS.set_environment("FLY_DATA",path)
		persist_settings()

func request_malecns_dataset_validation(path: String) -> bool:
	if dataset_validation_thread != null and dataset_validation_thread.is_started():return false
	dataset_validation_path=path
	dataset_validation_result={}
	dataset_validation_state="checking"
	dataset_validation_thread=Thread.new()
	var error := dataset_validation_thread.start(Callable(self,"_run_malecns_dataset_check").bind(path))
	if error != OK:
		dataset_validation_thread=null
		dataset_validation_state="error"
		dataset_validation_result={"ready":false,"error":"Could not start the dataset check worker (%s)." % error}
		return false
	return true

func set_dataset_path(path: String) -> void:
	settings.dataset_path=path
	OS.set_environment("FLY_DATA",path)
	persist_settings()

func language_switch_label() -> String:
	return I18n.next_language_label(str(settings.get("language","en")))

func set_language(language: String):
	if not language in I18n.LANGUAGES:return
	settings.language=language
	# Language changes are UI-only. Persist them without re-applying display
	# settings: apply_settings() forces WINDOWED + the configured resolution and
	# therefore collapses a maximized/full-screen-sized window on language swap.
	persist_settings()
	if is_instance_valid(view):
		call_deferred("show_page",current_page)

func toggle_language():
	set_language("en" if str(settings.get("language","en"))=="ru" else "ru")

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
func set_battle_overlay_visible(value: bool):
	if not is_instance_valid(battle):return
	# Battle HUD, observer controls, communication panel, gunner reticle and
	# Test Range hit/killcam UI live on CanvasLayer children. They belong only
	# to the active simulation view and must never bleed through menus/results.
	for layer in battle.find_children("*","CanvasLayer",true,false):
		layer.visible=value
func show_page(page: String):
	menu_axes.clear()
	menu_stick_latches.clear()
	current_page=page
	set_battle_overlay_visible(false)
	clear_view()
	view=load("res://scenes/app/"+page+".tscn").instantiate()
	get_tree().root.add_child(view)
	call_deferred("_focus_initial_menu_control")
func run_marl_job(command: String,args: Array=[]):
	if marl_pid>0 and OS.is_process_running(marl_pid):return
	var root=results_root().path_join("marl")
	DirAccess.make_dir_recursive_absolute(root)
	# Keep Matplotlib's font cache in persistent user data so first chart render
	# does not look like a stalled training process.
	var matplotlib_cache=OS.get_user_data_dir().path_join("cache/matplotlib")
	DirAccess.make_dir_recursive_absolute(matplotlib_cache)
	OS.set_environment("MPLCONFIGDIR",matplotlib_cache)
	var stamp=Time.get_datetime_string_from_system().replace(":","-")+"-"+str(Time.get_ticks_msec())
	marl_output=root.path_join(stamp+"-"+command)
	DirAccess.make_dir_recursive_absolute(marl_output.get_base_dir())
	var cli_args=PackedStringArray()
	if packaged_app:cli_args.append("--marl")
	else:cli_args.append_array(["-m","flyswarm.marl.cli"])
	cli_args.append_array(["--output-root",root,"--experiment-dir",marl_output,command])
	for item in args:cli_args.append(str(item))
	marl_progress={"state":"starting","phase":"process","command":command,"message":"Starting the Python experiment worker…"}
	marl_pid=OS.create_process(python,cli_args)
	if marl_pid<=0:marl_progress={"state":"error","phase":"process","command":command,"message":"Could not start the Python experiment process."}
	if current_page!="MarlLaboratory":show_page("MarlLaboratory")
func stop_marl_job():
	if marl_pid>0 and OS.is_process_running(marl_pid):
		FileAccess.open(marl_output.path_join("cancel"),FileAccess.WRITE).store_string("cancel")
		marl_progress["message"]="Останавливаю после безопасного шага и сохраняю checkpoint."
func toggle_marl_pause():
	if marl_pid<=0 or not OS.is_process_running(marl_pid):return
	var pause_path=marl_output.path_join("pause")
	if FileAccess.file_exists(pause_path):DirAccess.remove_absolute(pause_path)
	else:FileAccess.open(pause_path,FileAccess.WRITE).store_string("pause")
func marl_history()->Array:
	var entries=[]
	var root=results_root().path_join("marl")
	var dir=DirAccess.open(root)
	if dir==null:return entries
	dir.list_dir_begin();var name=dir.get_next()
	while name!="":
		if dir.current_is_dir() and name not in [".",".."]:
			var manifest=read_json(root.path_join(name).path_join("manifest.json"))
			if not manifest.is_empty():entries.append({"name":name,"path":root.path_join(name),"manifest":manifest})
		name=dir.get_next()
	entries.sort_custom(func(a,b):return str(a.name)>str(b.name))
	return entries
func open_marl_replay(path: String):
	marl_replay_path=path
	show_page("MarlViewer")
func configure(mode: String):
	open_day_mode=false
	session=Config.new()
	session.mode=mode
	if mode!="replay":session.environment_profile=str(settings.get("environment_profile","enhanced_visual"))
	session.audio_mode=settings.audio
	session.host=settings.host
	session.port=int(settings.port)
	# Interactive autonomous battles are outcome-driven. battle.gd still has a
	# generic safety time limit for jobs/replays, so give the visual battle a
	# deliberately remote 1-hour simulation cap: under normal play it ends on
	# tickets or elimination, not on the old 60-second default.
	if mode=="battle":session.seconds=3600
	if mode=="range":session.map="test_range";session.seconds=3600
	if mode=="training":session.battle_seed=100;session.seconds=2;session.blue_controller="brain";session.red_controller="brain"
	if mode=="research":session.seconds=5;session.blue_controller="brain";session.red_controller="brain"
	show_page({"battle":"HistoricalBattleSetup","range":"TestRangeSetup","training":"TrainingMenu","research":"ResearchLab"}[mode])
func open_day_menu():
	open_day_mode=true
	stop_session()
	show_page("OpenDayMain")
func research_menu():
	open_day_mode=false
	stop_session()
	show_page("MainMenu")
func configure_demo(vehicle: String="t34_85"):
	open_day_mode=true
	session=Config.new()
	session.mode="demo"
	session.map="demo_arena"
	session.seconds=120
	# Vary the deterministic opening movement between new Open Day matches.
	session.battle_seed=int(Time.get_ticks_usec() & 0x7fffffff)
	session.blue_controller="rule"
	session.red_controller="brain"
	session.audio_mode="no_audio"
	session.vehicle_composition=vehicle
	session.demo_vehicle=vehicle
	session.demo_opponent=vehicle
	session.record=true
	session.host=settings.host
	session.port=int(settings.port)
func start_demo(vehicle: String="t34_85"):
	configure_demo(vehicle)
	launch()
func stop_backend():
	if backend_pid>0 and OS.is_process_running(backend_pid):OS.kill(backend_pid)
	backend_pid=-1
	backend_state="NOT REQUIRED"
func stop_job():
	if job_path!="" and job_pid>0 and OS.is_process_running(job_pid):
		FileAccess.open(job_path.path_join("cancel"),FileAccess.WRITE).store_string("cancel")

func toggle_job_pause():
	if job_path=="" or job_pid<=0 or not OS.is_process_running(job_pid):return
	var pause_path=job_path.path_join("pause")
	if FileAccess.file_exists(pause_path):DirAccess.remove_absolute(pause_path)
	else:FileAccess.open(pause_path,FileAccess.WRITE).store_string("pause")

func request_job_checkpoint():
	if job_path!="" and job_pid>0 and OS.is_process_running(job_pid):
		FileAccess.open(job_path.path_join("save_checkpoint"),FileAccess.WRITE).store_string("save")
func stop_session():
	generation+=1
	stop_job()
	if marl_pid>0 and OS.is_process_running(marl_pid):
		FileAccess.open(marl_output.path_join("cancel"),FileAccess.WRITE).store_string("cancel")
		OS.kill(marl_pid)
	marl_pid=-1
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
	show_page("OpenDayMain" if open_day_mode else "MainMenu")
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
	current_page="Battle"
	set_battle_overlay_visible(true)
	backend_state="READY" if session.needs_brain() else "NOT REQUIRED"
func start_backend(token: int) -> bool:
	stop_backend()
	if session.host not in ["localhost","127.0.0.1"]:
		loading_message="Only the local managed backend is supported. Choose localhost in Settings."
		return false
	if not FileAccess.file_exists(python):
		loading_message=tr_text("Python environment is missing: ")+python+tr_text(". Rule AI and Test Range remain available.")
		return false
	var data_check=validate_malecns_dataset(str(settings.dataset_path))
	if not data_check.get("ready",false):
		loading_message=tr_text("MaleCNS dataset is not ready: ")+str(data_check.get("error","missing data"))
		return false
	OS.set_environment("FLY_DATA",str(settings.dataset_path))
	status_path=new_output("backend").path_join("status.json")
	var args=PackedStringArray()
	if not packaged_app:args.append_array(["-m","flyswarm.bridge.server"])
	args.append_array(["--port",str(session.port),"--seed",str(session.battle_seed),"--once","--status-file",status_path,"--parent-pid",str(OS.get_process_id()),"--blue-controller",session.blue_controller,"--red-controller",session.red_controller])
	if str(session.mode)=="demo":args.append("--demo")
	for team in ["blue","red"]:
		if session.get(team+"_controller")=="adapter":args.append_array(["--"+team+"-policy",session.get(team+"_policy")])
	backend_state="STARTING"
	backend_pid=OS.create_process(python,args)
	var started=Time.get_ticks_msec()
	while token==generation and Time.get_ticks_msec()-started<120000:
		var state=read_json(status_path)
		loading_message=state.get("stage","Starting Python backend…")
		if state.get("stage","")=="READY":backend_state="CONNECTING";loading_message="Connecting backend";return true
		if state.get("error")!=null:loading_message=tr_text("Backend error: ")+str(state.error);break
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
	battle.suspend_active_clock()
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
		battle.resume_active_clock()
		battle.paused=false
		backend_dialog_open=false
		clear_view()
		current_page="Battle"
		set_battle_overlay_visible(true)
	else:view.disconnect_dialog(loading_message)
func pause_menu():
	if not is_instance_valid(battle):return
	battle.suspend_active_clock()
	battle.paused=true
	show_page("PauseMenu")
func resume():
	if is_instance_valid(battle):battle.resume_active_clock();battle.paused=false
	clear_view()
	current_page="Battle"
	set_battle_overlay_visible(true)
func on_completed(report: Dictionary):
	last_report=report
	stop_backend()
	show_page("DemoResult" if session.mode=="demo" else "ResultsScreen")
func rerun():
	stop_session()
	launch()
func start_job(evaluate=false):
	if job_pid>0 and OS.is_process_running(job_pid):view.notice("The previous job is still stopping. Please retry shortly.");return
	var error=session.validate()
	if error!="":view.notice(error);return
	if not FileAccess.file_exists(python):view.notice("Python .venv is missing. Configure dependencies before starting this job.");return
	job_path=new_output("combat-training" if session.mode=="combat_training" else ("training" if session.mode=="training" else "research"))
	var config=session.as_dict()
	config.output=job_path
	config.evaluate=evaluate
	config.godot=OS.get_executable_path()
	config.parent_pid=OS.get_process_id()
	config.dataset_path=str(settings.dataset_path)
	if packaged_app:
		config.packaged=true
		config.backend_executable=python
		config.support_root=root_path
	FileAccess.open(job_path.path_join("job.json"),FileAccess.WRITE).store_string(JSON.stringify(config,"  "))
	if packaged_app:job_pid=OS.create_process(python,["--job-config",job_path.path_join("job.json")])
	else:job_pid=OS.create_process(python,[root_path.path_join("tools/app_job.py"),job_path.path_join("job.json")])
	backend_state="BUSY"
	show_page("JobProgress")
func _process(dt):
	if dataset_validation_thread != null and dataset_validation_thread.is_started() and not dataset_validation_thread.is_alive():
		dataset_validation_result=dataset_validation_thread.wait_to_finish()
		_apply_malecns_dataset_result(dataset_validation_path,dataset_validation_result)
		dataset_validation_state="ready" if dataset_validation_result.get("ready",false) else "error"
		dataset_validation_thread=null
	marl_poll_elapsed += dt
	job_poll_elapsed += dt
	if marl_pid>0:
		if marl_poll_elapsed >= .2:
			marl_poll_elapsed = fmod(marl_poll_elapsed,.2)
			var progress=read_json(marl_output.path_join("progress.json"))
			if not progress.is_empty():marl_progress=progress
			if not OS.is_process_running(marl_pid):
				marl_pid=-1
				var has_result=FileAccess.file_exists(marl_output.path_join("summary.json")) or FileAccess.file_exists(marl_output.path_join("manifest.json"))
				if str(marl_progress.get("state","")) not in ["error","cancelled"]:marl_progress["state"]="complete" if has_result else "error"
				if not has_result and not marl_progress.has("message"):marl_progress["message"]="Experiment process exited without writing a result manifest."
		if current_page=="MarlLaboratory" and is_instance_valid(view) and view.has_method("update_marl_status"):
			view.update_marl_status(marl_progress,marl_output)
	if current_page=="JobProgress" and job_path!="" and job_poll_elapsed >= .2:
		job_poll_elapsed = fmod(job_poll_elapsed,.2)
		var state=read_json(job_path.path_join("progress.json"))
		if state.get("state","") in ["complete","cancelled","error"]:
			backend_state="NOT REQUIRED"
		elif job_pid>0 and not OS.is_process_running(job_pid):
			backend_state="ERROR"
			state={"state":"error","message":"Worker exited unexpectedly; inspect the results folder."}
		if is_instance_valid(view):view.update_job(state)
func quit_app():
	stop_session()
	stop_marl_job()
	# Give the supervised job time to terminate its owned child processes.
	if marl_pid>0:
		for attempt in range(300):
			if not OS.is_process_running(marl_pid):break
			await get_tree().create_timer(.1).timeout
	if job_pid>0:
		for attempt in range(30):
			if not OS.is_process_running(job_pid):break
			await get_tree().create_timer(.1).timeout
	get_tree().quit()
func _notification(what):
	if what==NOTIFICATION_WM_CLOSE_REQUEST:quit_app()
