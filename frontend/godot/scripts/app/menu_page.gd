extends Control
@export var page="MainMenu"
var body: VBoxContainer
var status: Label
var headline: Label
var progress: ProgressBar
var job_text: Label
var results_button: Button
var replay_items=[]
var replay_list: ItemList
var form_controls={}
const IDS=["panther_g","tiger_i","jagdpanther","t34_85","is2_1944","su100"]
const VEHICLES=["Panther Ausf. G","Tiger I · late 1944","Jagdpanther","T-34-85 · 1944","IS-2 · 1944","SU-100"]
func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var theme_resource=Theme.new()
	theme_resource.default_font_size=19
	for kind in ["normal","hover","pressed","focus","disabled"]:
		var style=StyleBoxFlat.new()
		style.bg_color=Color("253532") if kind=="hover" else Color("172622")
		if kind=="disabled":style.bg_color=Color("151c1c")
		style.border_color=Color("bba16c") if kind in ["hover","focus"] else Color("35433e")
		style.set_border_width_all(1)
		style.set_corner_radius_all(3)
		style.content_margin_left=18;style.content_margin_right=18;style.content_margin_top=12;style.content_margin_bottom=12
		theme_resource.set_stylebox(kind,"Button",style)
		theme_resource.set_stylebox(kind,"OptionButton",style)
	theme_resource.set_color("font_color","Button",Color("e7e6dc"))
	theme_resource.set_color("font_disabled_color","Button",Color("78817b"))
	theme=theme_resource
	var bg=ColorRect.new();bg.color=Color("0b1414");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var layout=MarginContainer.new();layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:layout.add_theme_constant_override("margin_"+side,40)
	add_child(layout)
	var col=VBoxContainer.new();col.add_theme_constant_override("separation",18);layout.add_child(col)
	var top=HBoxContainer.new();col.add_child(top)
	var brand=label(top,"F / S     FLYSWARM",19);brand.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	status=label(top,"",14);status.modulate=Color("afbdab")
	var sep=HSeparator.new();col.add_child(sep)
	var scroll=ScrollContainer.new();scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;col.add_child(scroll)
	body=VBoxContainer.new();body.size_flags_horizontal=Control.SIZE_EXPAND_FILL;body.add_theme_constant_override("separation",14);scroll.add_child(body)
	match page:
		"MainMenu":main_menu()
		"HistoricalBattleSetup":battle_setup()
		"ResearchLab":research()
		"TrainingMenu":training()
		"TestRangeSetup":test_range()
		"ReplayBrowser":replays()
		"Settings":settings_menu()
		"LoadingScreen":title("SESSION PREPARATION","Loading");headline=label(body,"Preparing simulation…",28);button(body,"Cancel",AppState.menu)
		"ResultsScreen":results()
		"PauseMenu":pause_screen()
		"JobProgress":job_progress()
	label(col,"LOCAL RESEARCH BUILD     /     Historical geometry and armour data remain under validation",13).modulate=Color("7f9389")
	var buttons=find_children("*","Button",true,false)
	if not buttons.is_empty():buttons[0].grab_focus()
func label(parent: Node,text: String,size=19) -> Label:
	var node=Label.new();node.text=AppState.tr_text(text);node.add_theme_font_size_override("font_size",size);parent.add_child(node);return node
func text_block(text: String):
	var node=label(body,text,17);node.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;node.modulate=Color("b3c0b8");return node
func title(kicker: String,text: String):
	label(body,kicker,14).modulate=Color("c1a573")
	label(body,text,40)
func button(parent: Node,text: String,callback: Callable) -> Button:
	var node=Button.new();node.text=AppState.tr_text(text);node.name=text.to_pascal_case();node.custom_minimum_size.y=48;node.pressed.connect(callback);parent.add_child(node);return node
func row(text: String) -> HBoxContainer:
	var box=HBoxContainer.new();box.add_theme_constant_override("separation",20);body.add_child(box)
	var caption=label(box,text);caption.custom_minimum_size.x=280;return box
func dropdown(text: String,names: Array,values: Array,current,callback: Callable) -> OptionButton:
	var box=row(text);var node=OptionButton.new();node.name=text.to_pascal_case();node.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(node)
	for item in names:node.add_item(AppState.tr_text(str(item)))
	node.select(maxi(0,values.find(current)))
	node.item_selected.connect(func(i):callback.call(values[i]))
	form_controls[text]=node
	return node
func number(text: String,value: float,minimum: float,maximum: float,callback: Callable) -> SpinBox:
	var box=row(text);var node=SpinBox.new();node.name=text.to_pascal_case();node.min_value=minimum;node.max_value=maximum;node.value=value;node.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(node);node.value_changed.connect(callback);return node
func toggle(text: String,value: bool,callback: Callable):
	var node=CheckBox.new();node.text=AppState.tr_text(text);node.button_pressed=value;node.toggled.connect(callback);body.add_child(node)
func policy_field(text: String,field: String):
	var box=row(text);var node=LineEdit.new();node.text=AppState.session.get(field);node.placeholder_text=AppState.tr_text("Select a frozen .npz readout");node.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(node)
	node.text_changed.connect(func(value):AppState.session.set(field,value))
	button(box,"Browse",func():
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.npz ; "+AppState.tr_text("Readout policy")]);add_child(dialog)
		dialog.file_selected.connect(func(path):node.text=path;AppState.session.set(field,path);dialog.queue_free())
		dialog.popup_centered_ratio(.75))
func back():button(body,"Back",AppState.menu)
func main_menu():
	var split=HBoxContainer.new();split.add_theme_constant_override("separation",70);body.add_child(split)
	var left=VBoxContainer.new();left.custom_minimum_size.x=400;left.add_theme_constant_override("separation",10);split.add_child(left)
	label(left,"CONNECTOME / EMBODIMENT",14).modulate=Color("c1a573")
	label(left,"FLYSWARM",58)
	label(left,"A world to observe. A network to study.",16)
	var spacer=Control.new();spacer.custom_minimum_size.y=20;left.add_child(spacer)
	for item in [["HISTORICAL BATTLE","battle"],["RESEARCH LABORATORY","research"],["TRAINING","training"],["TEST RANGE","range"]]:
		button(left,item[0],AppState.configure.bind(item[1]))
	button(left,"REPLAYS",AppState.show_page.bind("ReplayBrowser"))
	button(left,"SETTINGS",AppState.show_page.bind("Settings"))
	button(left,AppState.language_switch_label(),AppState.toggle_language)
	button(left,"EXIT",AppState.quit_app)
	var right=VBoxContainer.new();right.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_theme_constant_override("separation",20);split.add_child(right)
	var map_view=TextureRect.new();map_view.custom_minimum_size=Vector2(450,330);map_view.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;map_view.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var image=Image.create(600,360,false,Image.FORMAT_RGB8)
	for y in range(360):
		for x in range(600):
			var height=sin(x*.016)*cos(y*.023)+.5*sin((x+y)*.019)
			var contour=absf(fmod(height*10,1))<.08
			var grid=x%60==0 or y%60==0
			image.set_pixel(x,y,Color("506553") if contour else (Color("253b32") if grid else Color("14241f")))
	map_view.texture=ImageTexture.create_from_image(image);right.add_child(map_view)
	label(right,"KRASNY VALLEY  /  1944",24)
	var copy=label(right,"16 embodied agents · 6 vehicle families\nTwo independent MaleCNS instances: 2 × batch 8\n2,667,200 simulated neuron states\n\nRule AI and the manual test range work offline.",18);copy.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;copy.modulate=Color("bac5bb")
func common_battle():
	var s=AppState.session
	dropdown("Map",["Krasny Valley"],["krasny_valley"],s.map,func(v):s.map=v)
	dropdown("Physics",["Historical · provisional data","Normalized research control"],["historical","normalized"],s.physics_mode,func(v):s.physics_mode=v)
	for team in ["blue","red"]:
		var key=team+"_controller"
		dropdown(team.to_upper()+" controller",["Rule AI","MaleCNS","Trained adapter"],["rule","brain","adapter"],s.get(key),func(v):s.set(key,v))
		policy_field(team.to_upper()+" policy",team+"_policy")
	dropdown("Communication",["No Audio","Team Audio","All Audio"],["no_audio","team_audio","all_audio"],s.audio_mode,func(v):s.audio_mode=v)
	number("Battle seed",s.battle_seed,0,999999,func(v):s.battle_seed=int(v))
	number("Map seed",s.map_seed,0,999999,func(v):s.map_seed=int(v))
	number("Duration (simulation seconds)",s.seconds,1,3600,func(v):s.seconds=v)
	toggle("Side swap",s.swap,func(v):s.swap=v)
	toggle("Record replay",s.record,func(v):s.record=v)
func battle_setup():
	title("1944 MIXED BATTLE","Historical Battle")
	var teams=HBoxContainer.new();teams.add_theme_constant_override("separation",80);body.add_child(teams)
	label(teams,"BLUE / GERMANY\n4 × Panther G\n2 × Tiger I\n2 × Jagdpanther",22).modulate=Color("9ac4db")
	label(teams,"RED / USSR\n4 × T-34-85\n2 × IS-2 Model 1944\n2 × SU-100",22).modulate=Color("dcab96")
	common_battle()
	button(body,"START BATTLE",AppState.launch);back()
func research():
	title("REPRODUCIBLE CONDITIONS","Research Laboratory")
	var s=AppState.session
	dropdown("Experiment",["Communication: none / team / all","Historical vs normalized","Same-vehicle mirror","Side-swap control","Vehicle-specific policy evaluation","Zero-shot vehicle transfer","Trained vs baseline"],["communication","embodiment","mirror","side_swap","policy","transfer","trained_baseline"],s.research_experiment,func(v):s.research_experiment=v)
	text_block("Runs measured conditions with independent seeds. Rule AI ignores neural communication; select MaleCNS for communication experiments. Transfer keeps the loaded readout unchanged.")
	number("Seed count",s.seed_count,1,20,func(v):s.seed_count=int(v))
	dropdown("Vehicle preset",["1944 mixed"]+VEHICLES,["mixed_1944"]+IDS,s.vehicle_composition,func(v):s.vehicle_composition=v)
	dropdown("Source / mirror vehicle",VEHICLES,IDS,s.training_vehicle,func(v):s.training_vehicle=v)
	dropdown("Transfer target",VEHICLES,IDS,s.target_vehicle,func(v):s.target_vehicle=v)
	dropdown("Render",["Headless · measured wall time","Visual"],["headless","visual"],s.render_mode,func(v):s.render_mode=v)
	common_battle()
	button(body,"RUN EXPERIMENT",AppState.start_job);back()
func training():
	title("READOUT ADAPTATION","Training")
	var s=AppState.session
	text_block("MaleCNS: FIXED / FROZEN · only the small motor readout is fitted. The available task uses teacher imitation; reward is not defined.")
	dropdown("Vehicle",VEHICLES,IDS,s.training_vehicle,func(v):s.training_vehicle=v)
	var tasks=dropdown("Task",["Turret tracking · available","Mobility familiarisation · unavailable","Waypoint navigation · unavailable","Slope traversal · unavailable","Stationary gunnery · unavailable","Moving-target gunnery · unavailable","1v1 combat · unavailable","Capture objective · unavailable"],["turret_tracking","mobility","waypoint","slope","stationary","moving","combat","capture"],s.training_task,func(v):s.training_task=v)
	for i in range(1,8):tasks.set_item_disabled(i,true)
	text_block("Other curriculum tasks have no training implementation yet and are disabled.")
	dropdown("Adapter",["Vehicle-specific","Shared policy"],["vehicle","shared"],s.adapter,func(v):s.adapter=v)
	number("Episodes",s.episodes,1,20,func(v):s.episodes=int(v))
	number("Training seed",s.battle_seed,0,999999,func(v):s.battle_seed=int(v))
	number("Validation seed",s.validation_seed,0,999999,func(v):s.validation_seed=int(v))
	number("Seconds per episode",s.seconds,1,60,func(v):s.seconds=v)
	s.render_mode="headless"
	toggle("Render during training",false,func(v):s.render_mode="visual" if v else "headless")
	policy_field("Load policy","blue_policy")
	button(body,"START TRAINING",AppState.start_job)
	button(body,"EVALUATE POLICY",func():
		if not FileAccess.file_exists(s.blue_policy):notice("Load an existing .npz policy first.")
		else:AppState.start_job(true))
	back()
func test_range():
	title("MANUAL VEHICLE CONTROL","Test Range")
	var s=AppState.session
	dropdown("Vehicle",VEHICLES,IDS,s.training_vehicle,func(v):s.training_vehicle=v)
	dropdown("Target vehicle",VEHICLES,IDS,s.target_vehicle,func(v):s.target_vehicle=v)
	dropdown("Distance",["100 m","500 m","1000 m","1500 m"],[100,500,1000,1500],s.range_distance,func(v):s.range_distance=v)
	dropdown("Target angle",["0°","30°","45°","60°"],[0,30,45,60],s.target_angle,func(v):s.target_angle=v)
	dropdown("Mode",["Free drive","Mobility","Gunnery","Armour","Module damage"],["free","mobility","gunnery","armour","modules"],s.range_mode,func(v):s.range_mode=v)
	text_block("W/S drive · A/D steer · Q/E turret · R/F elevation · left mouse/Space fire\nRight mouse drag aims. C camera · F1 armour debug · ESC pause/menu. Target remains stationary.")
	button(body,"START",AppState.launch);back()
func replays():
	title("RECORDED WORLD STATES","Replays")
	text_block("Playback uses recorded transforms and projectiles; no MaleCNS is loaded.")
	replay_list=ItemList.new();replay_list.max_text_lines=2;replay_list.custom_minimum_size.y=330;body.add_child(replay_list)
	scan_replays(AppState.results_root(),0)
	for path in replay_items:
		var manifest=AppState.read_json(path.path_join("manifest.json"));var summary=AppState.read_json(path.path_join("summary.json"))
		var cfg=manifest.get("session",{})
		replay_list.add_item("%s  |  %s  |  seed %s  |  %s  |  %.1fs\n%s" % [manifest.get("date",path.get_file()),AppState.tr_text(str(cfg.get("mode","battle"))),manifest.get("map_seed","?"),AppState.tr_text(str(manifest.get("map","?"))),summary.get("time",0)," / ".join([AppState.tr_text(str(cfg.get("vehicle_composition","mixed_1944"))),AppState.tr_text(str(cfg.get("blue_controller","unknown"))),AppState.tr_text(str(cfg.get("red_controller","unknown")))])])
	if replay_items.is_empty():text_block("No saved replays yet. Enable recording in a battle or use Save Replay in the pause menu.")
	button(body,"PLAY",func():
		var path=selected_replay()
		if path!="":AppState.session=AppState.Config.new();AppState.session.mode="replay";AppState.session.replay_path=path.path_join("replay.jsonl");AppState.launch())
	button(body,"DELETE",func():
		var path=selected_replay()
		if path=="":return
		var dialog=ConfirmationDialog.new();dialog.dialog_text=AppState.tr_text("Move this replay recording to Trash?")+"\n"+path;add_child(dialog)
		dialog.confirmed.connect(func():
			var result=OS.move_to_trash(path.path_join("replay.jsonl"))
			if result==OK:AppState.show_page("ReplayBrowser")
			else:notice("Could not move replay to Trash."))
		dialog.popup_centered())
	back()
func scan_replays(path: String,depth: int):
	if depth>3 or not DirAccess.dir_exists_absolute(path):return
	if FileAccess.file_exists(path.path_join("replay.jsonl")):replay_items.append(path)
	for directory in DirAccess.get_directories_at(path):scan_replays(path.path_join(directory),depth+1)
func selected_replay() -> String:
	var selected=replay_list.get_selected_items()
	if selected.is_empty():notice("Select a replay first.");return ""
	return replay_items[selected[0]]
func settings_menu():
	title("LOCAL PREFERENCES","Settings")
	var s=AppState.settings
	dropdown("Language",["English","Русский"],["en","ru"],str(s.get("language","en")),func(v):AppState.set_language(str(v)))
	dropdown("Graphics preset",["Low","Medium","High"],[0,1,2],s.preset,func(v):s.preset=v;s.shadows=v>0;s.vegetation=[.25,.6,1.0][v];s.effects=[.3,.6,1.0][v];AppState.show_page("Settings"))
	dropdown("Window resolution",["1280 × 800","1440 × 900","1920 × 1080"],[0,1,2],s.resolution,func(v):s.resolution=v)
	toggle("Fullscreen",s.fullscreen,func(v):s.fullscreen=v)
	toggle("Shadows",s.shadows,func(v):s.shadows=v)
	dropdown("Vegetation density",["Sparse","Balanced","Full"],[.25,.6,1.0],s.vegetation,func(v):s.vegetation=v)
	dropdown("LOD bias",["Performance","Balanced","Detail"],[2.0,1.0,.5],s.lod,func(v):s.lod=v)
	dropdown("Effects quality",["Low","Medium","High"],[.3,.6,1.0],s.effects,func(v):s.effects=v)
	toggle("Debug overlays by default",s.debug,func(v):s.debug=v)
	var box=row("Brain server host");var host=LineEdit.new();host.text=s.host;host.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(host);host.text_changed.connect(func(v):s.host=v)
	number("Brain server port",s.port,1024,65535,func(v):s.port=int(v))
	dropdown("Default communication",["No Audio","Team Audio","All Audio"],["no_audio","team_audio","all_audio"],s.audio,func(v):s.audio=v)
	text_block("The launcher manages localhost only. Audio communication is a neural signal; application sound playback is not implemented. LOD bias uses imported mesh LODs where present.")
	button(body,"SAVE SETTINGS",func():AppState.save_settings();AppState.menu())
	button(body,"RESET DEFAULTS",func():AppState.settings={"preset":1,"fullscreen":false,"resolution":0,"shadows":true,"vegetation":.6,"lod":1.0,"effects":.6,"debug":false,"host":"127.0.0.1","port":8765,"audio":"no_audio","language":str(AppState.settings.get("language","en"))};AppState.save_settings();AppState.show_page("Settings"))
	back()
func pause_screen():
	title("SESSION PAUSED","Pause")
	button(body,"RESUME",AppState.resume)
	button(body,"DEBUG VIEW",func():AppState.battle.debug=not AppState.battle.debug;AppState.resume())
	button(body,"SAVE REPLAY",func():AppState.battle.save_replay();notice("Replay saved (up to the last 10 minutes if recording was disabled):\n"+AppState.battle.record_path))
	button(body,"RETURN TO MAIN MENU",AppState.menu)
	button(body,"EXIT APPLICATION",AppState.quit_app)
func results():
	title("MEASURED SESSION RESULTS","Session complete")
	var report=AppState.last_report
	if report.has("tickets"):
		var winner="DRAW" if is_equal_approx(report.tickets[0],report.tickets[1]) else ("BLUE / GERMANY" if report.tickets[0]>report.tickets[1] else "RED / USSR")
		label(body,winner,32)
		for team in range(2):
			var alive=0;var shots=0;var kills=0;var pens=0;var capture=0.0
			for state in report.vehicles:
				if int(state.id/8)!=team:continue
				alive+=int(state.alive);shots+=int(state.metrics.shots);kills+=int(state.metrics.kills);pens+=int(state.metrics.penetrations);capture+=float(state.metrics.capture_s)
			text_block(AppState.tr_format("results.team",[AppState.tr_text("BLUE" if team==0 else "RED"),report.tickets[team],alive,shots,pens,kills,capture]))
		text_block(AppState.tr_format("results.duration",[report.time,report.get("wall_seconds",0)]))
	text_block(AppState.tr_format("results.saved",[AppState.last_output]))
	var play=button(body,"VIEW REPLAY",func():AppState.stop_session();AppState.session.mode="replay";AppState.session.replay_path=AppState.last_output.path_join("replay.jsonl");AppState.launch())
	play.disabled=not FileAccess.file_exists(AppState.last_output.path_join("replay.jsonl"))
	button(body,"RUN AGAIN",AppState.rerun)
	button(body,"RETURN TO MENU",AppState.menu)
func job_progress():
	title("MEASURED EXPERIMENT","Running session")
	job_text=text_block("Starting worker…")
	progress=ProgressBar.new();progress.max_value=1;body.add_child(progress)
	text_block("Reward / rolling reward: N/A for ridge imitation. No scientific interpretation is generated.")
	button(body,"CANCEL",AppState.stop_job)
	results_button=button(body,"OPEN RESULTS FOLDER",func():OS.shell_open(AppState.job_path));results_button.disabled=true
	button(body,"RUN AGAIN",func():AppState.start_job()).disabled=true
	button(body,"RETURN",AppState.menu)
func update_job(data: Dictionary):
	if not is_instance_valid(job_text):return
	job_text.text=AppState.tr_format("job.progress",[AppState.tr_text(str(data.get("state","starting"))),data.get("condition","—"),data.get("seed","—"),data.get("run",0),data.get("total",0),data.get("sim_time",0),data.get("wall_time",0),AppState.tr_text(str(data.get("message",""))),AppState.job_path,data.get("checkpoint",AppState.tr_text("not saved yet"))])
	var again=find_child("RunAgain",true,false)
	if again:again.disabled=not data.get("state","") in ["complete","cancelled","error"]
	progress.max_value=maxf(1,data.get("total",1));progress.value=data.get("completed",0)
	results_button.disabled=not data.get("state","") in ["complete","cancelled","error"]
func notice(message: String):
	var dialog=AcceptDialog.new();dialog.dialog_text=AppState.tr_text(message);add_child(dialog);dialog.popup_centered(Vector2i(650,220))
func backend_unavailable(reason: String):
	headline.text=AppState.tr_text("MaleCNS backend is unavailable.")
	text_block(reason)
	button(body,"Retry",AppState.launch)
	button(body,"Use Rule AI",func():AppState.session.blue_controller="rule";AppState.session.red_controller="rule";AppState.launch())
func disconnect_dialog(reason: String):
	headline.text=AppState.tr_text("BRAIN BACKEND DISCONNECTED")
	text_block(reason+"\n"+AppState.tr_text("Reconnect starts fresh neural state; the resumed episode is not scientifically continuous."))
	button(body,"RECONNECT",AppState.reconnect)
	button(body,"RETURN TO MENU",AppState.menu)
func _process(_dt):
	status.text=AppState.tr_text("BACKEND")+"  ·  "+AppState.tr_text(AppState.backend_state)
	if page=="LoadingScreen" and not AppState.backend_state in ["ERROR","DISCONNECTED"]:headline.text=AppState.tr_text(AppState.loading_message)
