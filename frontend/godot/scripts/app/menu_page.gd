extends Control
const DesignSystem = preload("res://scripts/app/design_system.gd")
const HeroMap = preload("res://scripts/app/hero_map.gd")
@export var page="MainMenu"
var body: VBoxContainer
var status: Label
var headline: Label
var progress: ProgressBar
var loading_progress: ProgressBar
var job_text: Label
var results_button: Button
var replay_items=[]
var replay_list: ItemList
var form_controls={}
var reward_curve: Control
var reward_curve_refresh=0.0
const IDS=["panther_g","tiger_i","jagdpanther","t34_85","is2_1944","su100"]
const VEHICLES=["Panther Ausf. G","Tiger I · late 1944","Jagdpanther","T-34-85 · 1944","IS-2 · 1944","SU-100"]
func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var appearance=str(AppState.settings.get("appearance","dark"))
	theme=DesignSystem.make_theme(18,appearance)
	var bg=ColorRect.new();bg.color=DesignSystem.ink_for(appearance);bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var layout=MarginContainer.new();layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:layout.add_theme_constant_override("margin_"+side,32)
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
		"LoadingScreen":title("SESSION PREPARATION","Loading");headline=label(body,"Preparing simulation…",28);loading_progress=ProgressBar.new();loading_progress.indeterminate=true;loading_progress.custom_minimum_size.y=12;body.add_child(loading_progress);button(body,"Cancel",AppState.menu)
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
	var box=row(text);var node=LineEdit.new();node.text=AppState.session.get(field);node.placeholder_text=AppState.tr_text("Select a frozen .npz readout or combat PPO .zip");node.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(node)
	node.text_changed.connect(func(value):AppState.session.set(field,value))
	button(box,"Browse",func():
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.npz,*.zip ; "+AppState.tr_text("Readout or combat policy")]);add_child(dialog)
		dialog.file_selected.connect(func(path):node.text=path;AppState.session.set(field,path);dialog.queue_free())
		dialog.popup_centered_ratio(.75))
func back():button(body,"Back",AppState.menu)
func menu_entry(parent: VBoxContainer,title_text: String,description_text: String,callback: Callable):
	var frame=PanelContainer.new()
	frame.custom_minimum_size=Vector2(440,94)
	frame.add_theme_stylebox_override("panel",DesignSystem.panel_style(str(AppState.settings.get("appearance","dark"))))
	parent.add_child(frame)
	var card=VBoxContainer.new()
	card.add_theme_constant_override("separation",5)
	frame.add_child(card)
	var entry_button=button(card,title_text,callback)
	entry_button.custom_minimum_size=Vector2(420,52)
	entry_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	entry_button.alignment=HORIZONTAL_ALIGNMENT_LEFT
	var description=label(card,description_text,14)
	description.custom_minimum_size=Vector2(420,34)
	description.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	description.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	description.modulate=Color("9aaba2")
func main_menu():
	var split=HBoxContainer.new();split.add_theme_constant_override("separation",40);body.add_child(split)
	var left=VBoxContainer.new();left.custom_minimum_size.x=520;left.add_theme_constant_override("separation",8);split.add_child(left)
	label(left,"CONNECTOME / EMBODIMENT",14).modulate=DesignSystem.ACCENT
	label(left,"FLYSWARM",58).add_theme_color_override("font_color",DesignSystem.text_for(str(AppState.settings.get("appearance","dark"))))
	label(left,"A world to observe. A network to study.",16)
	var spacer=Control.new();spacer.custom_minimum_size.y=20;left.add_child(spacer)
	menu_entry(left,"OPEN DAY DEMO","A fast 1v1: a visitor against a tank controlled by the reconstructed MaleCNS model.",AppState.open_day_menu)
	menu_entry(left,"AUTONOMOUS BATTLE","Run or observe an 8×8 battle using Rule AI, MaleCNS or a trained adapter.",AppState.configure.bind("battle"))
	menu_entry(left,"RESEARCH LABORATORY","Run reproducible experiment series across seeds and compare conditions.",AppState.configure.bind("research"))
	if str(AppState.settings.get("language","en"))=="ru":
		menu_entry(left,"ЛАБОРАТОРИЯ MARL","Обучите командную политику PPO, сравните её со случайной и просмотрите записанный бой.",AppState.show_page.bind("MarlLaboratory"))
	else:
		menu_entry(left,"MARL LABORATORY","Train a PettingZoo team policy, compare it with Random and replay Python-authoritative battles.",AppState.show_page.bind("MarlLaboratory"))
	menu_entry(left,"READOUT TRAINING","Fit and evaluate an external motor readout from MaleCNS features. Teacher imitation; no reward.",AppState.configure.bind("training"))
	menu_entry(left,"TEST RANGE","Manually drive and fire to inspect mobility, armour, ballistics and damage.",AppState.configure.bind("range"))
	menu_entry(left,"REPLAYS","Open recorded simulations without running MaleCNS again.",AppState.show_page.bind("ReplayBrowser"))
	var secondary=HBoxContainer.new();secondary.add_theme_constant_override("separation",8);left.add_child(secondary)
	var settings_button=button(secondary,"SETTINGS",AppState.show_page.bind("Settings"));settings_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var language_button=button(secondary,AppState.language_switch_label(),AppState.toggle_language);language_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var exit_button=button(secondary,"EXIT",AppState.quit_app);exit_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var right=VBoxContainer.new();right.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_theme_constant_override("separation",20);split.add_child(right)
	var map_view=HeroMap.new();map_view.custom_minimum_size=Vector2(450,330);map_view.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_child(map_view)
	label(right,"KRASNY VALLEY  /  1944",24).add_theme_color_override("font_color",DesignSystem.GOLD)
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
	title("FIXED MALECNS · RIDGE IMITATION","Readout Training")
	var s=AppState.session
	text_block("MaleCNS: FIXED / FROZEN · Method: teacher imitation / ridge readout · Reward: not used. Only the implemented turret-tracking task is shown.")
	dropdown("Vehicle",VEHICLES,IDS,s.training_vehicle,func(v):s.training_vehicle=v)
	s.training_task="turret_tracking"
	dropdown("Task",["Turret tracking · available"],["turret_tracking"],s.training_task,func(v):s.training_task=v)
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
	label(body,"MALECNS COMBAT TRAINING",25).modulate=Color("c1a573")
	text_block("Train an external combat policy with PPO. The connectome stays frozen. MaleCNS mode uses the real FlyBrain(batch=1) and requires the configured dataset; Gameplay Pretraining is labelled separately and does not use neural signals.")
	dropdown("Neural input",["MaleCNS Training / Fine-tuning","Gameplay Pretraining · no MaleCNS"],["malecns","pretraining"],s.training_stage,func(v):s.training_stage=v)
	dropdown("Training program",["Automatic curriculum","Full battle"],["automatic","full_battle"],s.training_program,func(v):s.training_program=v)
	number("PPO steps",s.training_steps,16,200000,func(v):s.training_steps=int(v))
	number("Maximum training time (minutes)",s.training_time_minutes,1,4320,func(v):s.training_time_minutes=int(v))
	number("Episode limit (seconds)",s.training_seconds,30,600,func(v):s.training_seconds=int(v))
	number("Training seed",s.training_seed,0,2147480000,func(v):s.training_seed=int(v))
	number("Checkpoint interval (steps)",s.checkpoint_interval,64,10000,func(v):s.checkpoint_interval=int(v))
	var checkpoint_box=row("Checkpoint (.zip)")
	var checkpoint_edit=LineEdit.new();checkpoint_edit.name="CombatCheckpoint";checkpoint_edit.text=s.combat_checkpoint;checkpoint_edit.placeholder_text=AppState.tr_text("Select a PPO checkpoint");checkpoint_edit.size_flags_horizontal=Control.SIZE_EXPAND_FILL;checkpoint_box.add_child(checkpoint_edit)
	checkpoint_edit.text_changed.connect(func(value):s.combat_checkpoint=value)
	button(checkpoint_box,"Browse…",func():
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.zip ; PPO checkpoint or deployment policy"]);add_child(dialog)
		dialog.file_selected.connect(func(path):checkpoint_edit.text=path;s.combat_checkpoint=path;dialog.queue_free())
		dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.75))
	var actions=HBoxContainer.new();actions.add_theme_constant_override("separation",10);body.add_child(actions)
	button(actions,"START NEW COMBAT TRAINING",func():
		s.mode="combat_training";s.combat_action="train";s.resume_checkpoint="";AppState.start_job())
	button(actions,"RESUME / CONTINUE",func():
		var checkpoint=s.combat_checkpoint
		if checkpoint=="":checkpoint=_find_combat_checkpoint()
		if checkpoint=="" or not FileAccess.file_exists(checkpoint):notice("Select an existing latest.zip checkpoint to resume training.");return
		s.combat_checkpoint=checkpoint;s.resume_checkpoint=checkpoint;s.mode="combat_training";s.combat_action="train";AppState.start_job())
	var combat_actions=HBoxContainer.new();combat_actions.add_theme_constant_override("separation",10);body.add_child(combat_actions)
	button(combat_actions,"EVALUATE MODEL",func():
		if s.combat_checkpoint=="" or not FileAccess.file_exists(s.combat_checkpoint):notice("Select a combat checkpoint first.");return
		s.mode="combat_training";s.combat_action="evaluate";AppState.start_job())
	button(combat_actions,"PREPARE FOR OPEN DAY",func():
		if s.combat_checkpoint=="" or not FileAccess.file_exists(s.combat_checkpoint):notice("Select a combat checkpoint first.");return
		s.mode="combat_training";s.combat_action="deploy";AppState.start_job())
	back()

func _find_combat_checkpoint() -> String:
	var root=AppState.results_root()
	var dir=DirAccess.open(root)
	if dir==null:return ""
	var paths:Array[String]=[];dir.list_dir_begin();var name=dir.get_next()
	while name!="":
		if dir.current_is_dir() and name.begins_with("combat-training-"):
			var candidate=root.path_join(name).path_join("checkpoints/latest.zip")
			if FileAccess.file_exists(candidate):paths.append(candidate)
		name=dir.get_next()
	paths.sort();return paths.back() if not paths.is_empty() else ""
func test_range():
	title("MANUAL VEHICLE CONTROL","Test Range")
	var s=AppState.session
	dropdown("Vehicle",VEHICLES,IDS,s.training_vehicle,func(v):s.training_vehicle=v)
	dropdown("Target vehicle",VEHICLES,IDS,s.target_vehicle,func(v):s.target_vehicle=v)
	dropdown("Distance",["100 m","500 m","1000 m","1500 m"],[100,500,1000,1500],s.range_distance,func(v):s.range_distance=v)
	dropdown("Target angle",["0°","30°","45°","60°"],[0,30,45,60],s.target_angle,func(v):s.target_angle=v)
	dropdown("Mode",["Free drive","Mobility","Gunnery","Armour","Module damage"],["free","mobility","gunnery","armour","modules"],s.range_mode,func(v):s.range_mode=v)
	text_block("W/S drive · A/D steer · Q/E turret · R/F elevation · left mouse/Space fire\nRight mouse drag aims. C camera · F1 armour debug · ESC pause/menu. Target remains stationary.")
	text_block("Для уничтожения взорвите боеукладку или выведите из строя экипаж, оставив не более одного выжившего. Урон модулей накапливается между выстрелами. Каждое попадание отображается в отчёте; Enter восстанавливает цель." if str(AppState.settings.language)=="ru" else "To destroy the target: detonate its ammo rack or knock out all but one crew member. Module damage accumulates across shots. Every hit shows an impact report; Enter restores the target.")
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
	dropdown("Appearance",["Dark · charcoal and olive","Light · paper and spruce"],["dark","light"],str(s.get("appearance","dark")),func(v):s.appearance=v;AppState.show_page("Settings"))
	dropdown("Graphics preset",["Low","Medium","High"],[0,1,2],s.preset,func(v):s.preset=v;s.shadows=v>0;s.vegetation=[.25,.6,1.0][v];s.effects=[.3,.6,1.0][v];AppState.show_page("Settings"))
	dropdown("Window resolution",["1280 × 800","1440 × 900","1920 × 1080"],[0,1,2],s.resolution,func(v):s.resolution=v)
	toggle("Fullscreen",s.fullscreen,func(v):s.fullscreen=v)
	toggle("Shadows",s.shadows,func(v):s.shadows=v)
	dropdown("Vegetation density",["Sparse","Balanced","Full"],[.25,.6,1.0],s.vegetation,func(v):s.vegetation=v)
	dropdown("Environment profile",["Enhanced visuals","Enhanced physical","Legacy experiment"],["enhanced_visual","enhanced_physical","legacy"],str(s.get("environment_profile","enhanced_visual")),func(v):s.environment_profile=v)
	dropdown("LOD bias",["Performance","Balanced","Detail"],[2.0,1.0,.5],s.lod,func(v):s.lod=v)
	dropdown("Effects quality",["Low","Medium","High"],[.3,.6,1.0],s.effects,func(v):s.effects=v)
	toggle("Debug overlays by default",s.debug,func(v):s.debug=v)
	var box=row("Brain server host");var host=LineEdit.new();host.text=s.host;host.size_flags_horizontal=Control.SIZE_EXPAND_FILL;box.add_child(host);host.text_changed.connect(func(v):s.host=v)
	number("Brain server port",s.port,1024,65535,func(v):s.port=int(v))
	malecns_dataset_settings()
	dropdown("Default communication",["No Audio","Team Audio","All Audio"],["no_audio","team_audio","all_audio"],s.audio,func(v):s.audio=v)
	text_block("Enhanced visuals preserve the old heightfield collision and forest visibility. Enhanced physical changes terrain and obstacle collision and is a separate experiment condition. Legacy restores the previous scenery. Replays keep the profile they recorded. LOD bias uses imported mesh LODs where present.")
	button(body,"SAVE SETTINGS",func():AppState.save_settings();AppState.menu())
	button(body,"RESET DEFAULTS",func():AppState.settings={"preset":1,"fullscreen":false,"resolution":0,"shadows":true,"vegetation":.6,"lod":1.0,"effects":.6,"debug":false,"host":"127.0.0.1","port":8765,"audio":"no_audio","language":str(AppState.settings.get("language","en")),"appearance":"dark","dataset_path":str(AppState.settings.get("dataset_path","")),"environment_profile":"enhanced_visual"};AppState.save_settings();AppState.show_page("Settings"))
	back()

func malecns_dataset_settings() -> void:
	var russian=str(AppState.settings.get("language","en"))=="ru"
	var heading=label(body,"ДАННЫЕ MALECNS" if russian else "MALECNS DATASET",22)
	heading.modulate=Color("c1a573")
	var path_row=HBoxContainer.new();path_row.add_theme_constant_override("separation",12);body.add_child(path_row)
	var path_edit=LineEdit.new();path_edit.name="MaleCNSDatasetPath";path_edit.text=str(AppState.settings.dataset_path);path_edit.size_flags_horizontal=Control.SIZE_EXPAND_FILL;path_row.add_child(path_edit)
	var browse=Button.new();browse.text="Выбрать папку…" if russian else "Choose folder…";browse.custom_minimum_size.y=48;path_row.add_child(browse)
	var check=Button.new();check.text="Проверить MaleCNS" if russian else "Check MaleCNS data";body.add_child(check)
	var status=Label.new();status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;status.custom_minimum_size.y=32;body.add_child(status)
	status.text="Два файла данных не включены в приложение." if russian else "The connectome files are not included in the app."
	status.modulate=Color("b3c0b8")
	browse.pressed.connect(func():
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_DIR;dialog.use_native_dialog=true;add_child(dialog)
		dialog.dir_selected.connect(func(path):path_edit.text=path;AppState.set_dataset_path(path);dialog.queue_free())
		dialog.canceled.connect(func():dialog.queue_free())
		dialog.popup_centered_ratio(.75))
	check.pressed.connect(func():
		AppState.set_dataset_path(path_edit.text)
		status.text="Проверяю контрольные суммы…" if russian else "Checking dataset files and checksums…"
		var result=AppState.validate_malecns_dataset(path_edit.text)
		if result.get("ready",false):
			status.text=("MALECNS ГОТОВ · " if russian else "MALECNS READY · ")+str(result.get("path",path_edit.text))
			status.modulate=Color("8ccf9b")
		else:
			status.text=("ДАННЫЕ MALECNS НЕ НАЙДЕНЫ · " if russian else "MALECNS DATA NOT READY · ")+str(result.get("error",""))
			status.modulate=Color("ef9a7a"))

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
	progress=ProgressBar.new();progress.max_value=1;progress.indeterminate=true;progress.custom_minimum_size.y=12;body.add_child(progress)
	if AppState.session.mode=="combat_training":
		text_block("External PPO policy · frozen MaleCNS · analytical tank-duel environment. Training reward is not proof of combat quality.")
		reward_curve=Control.new();reward_curve.name="CombatRewardCurve";reward_curve.custom_minimum_size=Vector2(0,150);reward_curve.size_flags_horizontal=Control.SIZE_EXPAND_FILL;reward_curve.set_script(load("res://scripts/app/training_curve.gd"));body.add_child(reward_curve)
		var pause=button(body,"PAUSE / RESUME",AppState.toggle_job_pause);pause.name="PauseJob"
		var checkpoint=button(body,"SAVE CHECKPOINT NOW",AppState.request_job_checkpoint);checkpoint.name="SaveCheckpointNow"
	else:text_block("Reward / rolling reward: N/A for ridge imitation. No scientific interpretation is generated.")
	button(body,"STOP TRAINING" if AppState.session.mode=="combat_training" else "CANCEL",AppState.stop_job)
	results_button=button(body,"OPEN RESULTS FOLDER",func():OS.shell_open(AppState.job_path));results_button.disabled=true
	button(body,"RUN AGAIN",func():AppState.start_job()).disabled=true
	button(body,"RETURN",AppState.menu)
func update_job(data: Dictionary):
	if not is_instance_valid(job_text):return
	var combat_training: bool = AppState.session.mode=="combat_training"
	if combat_training:
		var state=str(data.get("state","starting"));var current=int(data.get("timesteps",0));var target=int(data.get("target_timesteps",AppState.session.training_steps))
		var male="MALECNS ACTIVE" if data.get("male_cns_active",AppState.session.training_stage=="malecns") else "GAMEPLAY PRETRAINING · NO MALECNS"
		job_text.text="%s\n%s · %s\nSteps: %d / %d · %.1f steps/sec · ETA %.1f min\nEpisodes: %s · Elapsed: %.1f min\nReward: %s\nCheckpoint: %s\n%s" % [state.to_upper(),male,str(data.get("stage","—")),current,target,float(data.get("steps_per_second",0)),float(data.get("eta_seconds",0))/60.0,str(data.get("episodes",0)),float(data.get("elapsed_seconds",0))/60.0,str(data.get("latest_episode_reward","not enough episodes")),str(data.get("checkpoint",AppState.tr_text("not saved yet"))),str(data.get("message",""))]
		if state=="complete":
			var evaluation=AppState.read_json(AppState.job_path.path_join("evaluation.json"))
			var score=evaluation.get("current_policy",{})
			if not score.is_empty():
				job_text.text+="\nIndependent evaluation · %d paired seeds\nWins %.0f%% · accuracy %.1f%% · damage %.2f\nShots %.1f · distance %.1f m · stuck recovery %.2f" % [evaluation.get("baseline_rule",{}).get("episodes",[]).size(),float(score.get("win_rate",0))*100.0,float(score.get("accuracy",0))*100.0,float(score.get("mean_damage",0)),float(score.get("mean_shots",0)),float(score.get("mean_distance_m",0)),float(score.get("mean_stuck_recoveries",0))]
		progress.indeterminate=target<=0 or state in ["starting","initializing","finalizing"]
		progress.max_value=maxf(1,target);progress.value=current
		var pause_button=find_child("PauseJob",true,false)
		if pause_button:pause_button.text="RESUME" if state=="paused" else "PAUSE"
	else:
		job_text.text=AppState.tr_format("job.progress",[AppState.tr_text(str(data.get("state","starting"))),data.get("condition","—"),data.get("seed","—"),data.get("run",0),data.get("total",0),data.get("sim_time",0),data.get("wall_time",0),AppState.tr_text(str(data.get("message",""))),AppState.job_path,data.get("checkpoint",AppState.tr_text("not saved yet"))])
	var again=find_child("RunAgain",true,false)
	if again:again.disabled=not data.get("state","") in ["complete","cancelled","error"]
	if not combat_training:
		var total=int(data.get("total",0));var completed=int(data.get("completed",0))
		progress.indeterminate=total<=0
		progress.max_value=maxi(1,total);progress.value=completed
	results_button.disabled=not data.get("state","") in ["complete","cancelled","error"]
func notice(message: String):
	var dialog=AcceptDialog.new();dialog.dialog_text=AppState.tr_text(message);add_child(dialog);dialog.popup_centered(Vector2i(650,220))
func backend_unavailable(reason: String):
	headline.text=AppState.tr_text("MaleCNS backend is unavailable.")
	text_block(reason)
	button(body,"Retry",AppState.launch)
	if AppState.session.mode=="demo":
		text_block("The interactive Fly battle requires the real MaleCNS backend. Rule AI is never presented as the fly.")
		button(body,"MALECNS DATASET SETTINGS",func():AppState.show_page("Settings"))
		button(body,"RETURN TO OPEN DAY",AppState.open_day_menu)
	else:
		button(body,"Use Rule AI",func():AppState.session.blue_controller="rule";AppState.session.red_controller="rule";AppState.launch())
func disconnect_dialog(reason: String):
	headline.text=AppState.tr_text("BRAIN BACKEND DISCONNECTED")
	text_block(reason+"\n"+AppState.tr_text("Reconnect starts fresh neural state; the resumed episode is not scientifically continuous."))
	button(body,"RECONNECT",AppState.reconnect)
	button(body,"RETURN TO MENU",AppState.menu)
func _refresh_training_curve():
	if not is_instance_valid(reward_curve):return
	var metrics_path=AppState.job_path.path_join("metrics.csv")
	if not FileAccess.file_exists(metrics_path):return
	var lines=FileAccess.get_file_as_string(metrics_path).split("\n",false)
	if lines.size()<2:return
	var columns=lines[0].split(",")
	var reward_index=columns.find("episode_reward")
	if reward_index<0:return
	var samples:Array[float]=[]
	for line in lines.slice(1):
		var fields=line.split(",")
		if fields.size()>reward_index:samples.append(float(fields[reward_index]))
	reward_curve.call("set_samples",samples)
func _process(dt):
	status.text=AppState.tr_text("BACKEND")+"  ·  "+AppState.tr_text(AppState.backend_state)
	if page=="LoadingScreen" and not AppState.backend_state in ["ERROR","DISCONNECTED"]:
		headline.text=AppState.tr_text(AppState.loading_message)
		if is_instance_valid(loading_progress):loading_progress.indeterminate=AppState.backend_state in ["STARTING","CONNECTING","BUSY"]
	if page=="JobProgress" and AppState.session.mode=="combat_training":
		reward_curve_refresh+=dt
		if reward_curve_refresh>=.5:reward_curve_refresh=0.0;_refresh_training_curve()
