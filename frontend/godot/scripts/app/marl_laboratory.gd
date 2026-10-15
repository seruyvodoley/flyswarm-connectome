extends Control

var status_label: Label
var detail_label: Label
var checkpoint_path=""
var seed_value=101
var episode_steps=600
var training_steps=2048
var current_replay=""
var result_path=""

func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg=ColorRect.new();bg.color=Color("0b1414");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,42)
	add_child(margin)
	var column=VBoxContainer.new();column.add_theme_constant_override("separation",16);margin.add_child(column)
	var top=HBoxContainer.new();column.add_child(top)
	var title=Label.new();title.text=_t("ЛАБОРАТОРИЯ MARL","MARL LABORATORY");title.add_theme_font_size_override("font_size",34);title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top.add_child(title)
	var back=Button.new();back.text=_t("В меню","Back");back.pressed.connect(AppState.menu);top.add_child(back)
	var intro=Label.new();intro.text=_t("PettingZoo Parallel · Stable-Baselines3 PPO · 16 машин · Python задаёт исход боя","PettingZoo Parallel · Stable-Baselines3 PPO · 16 vehicles · Python owns battle outcomes");intro.modulate=Color("bdc7bd");column.add_child(intro)
	var split=HBoxContainer.new();split.add_theme_constant_override("separation",36);column.add_child(split);split.size_flags_vertical=Control.SIZE_EXPAND_FILL
	var left=VBoxContainer.new();left.custom_minimum_size.x=540;left.add_theme_constant_override("separation",10);split.add_child(left)
	_section(left,"A · RANDOM BASELINE","A · СЛУЧАЙНАЯ БАЗА")
	_number(left,"Seed",seed_value,1,2147480000,func(v):seed_value=int(v))
	_number(left,"Episode steps / Шаги эпизода",episode_steps,16,1500,func(v):episode_steps=int(v))
	_action(left,_t("Запустить случайную политику","Run random baseline"),func():
		AppState.run_marl_job("baseline",["--episodes","3","--seed",str(seed_value),"--max-steps",str(episode_steps)]))
	var b=Button.new();b.text=_t("Смотреть последний случайный бой","Watch last Random battle");b.pressed.connect(func():_open_replay("random-seed-"+str(seed_value)+".jsonl"));left.add_child(b)
	_section(left,"B · PPO TRAINING","B · ОБУЧЕНИЕ PPO")
	_number(left,"Training steps / Шаги обучения",training_steps,64,500000,func(v):training_steps=int(v))
	_action(left,_t("Обучить PPO и сохранить checkpoint","Train PPO and save checkpoint"),func():
		AppState.run_marl_job("train",["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps)]))
	checkpoint_path=_find_checkpoint()
	var select=Button.new();select.text=_t("Выбрать checkpoint…","Choose checkpoint…");select.pressed.connect(_choose_checkpoint);left.add_child(select)
	_section(left,"C · EVALUATION","C · ОЦЕНКА")
	_action(left,_t("Оценить модель на тестовых seed","Evaluate checkpoint on test seeds"),func():_run_checkpoint("evaluate"))
	_action(left,_t("Сравнить Random и PPO на одинаковых seed","Compare Random and PPO on paired seeds"),func():_run_checkpoint("compare"))
	var trained=Button.new();trained.text=_t("Смотреть бой PPO","Watch trained PPO battle");trained.pressed.connect(func():_open_matching_replay("trained-seed-"));left.add_child(trained)
	var choose_replay=Button.new();choose_replay.text=_t("Открыть любой повтор…","Open any replay…");choose_replay.pressed.connect(_choose_replay);left.add_child(choose_replay)
	var compare_csv=Button.new();compare_csv.text=_t("Открыть CSV сравнения","Open comparison CSV");compare_csv.pressed.connect(func():_open_result_file("comparison.csv"));left.add_child(compare_csv)
	var graph=Button.new();graph.text=_t("Открыть график обучения","Open training graph");graph.pressed.connect(func():_open_result_file("plots/learning_curve.png"));left.add_child(graph)
	var results=Button.new();results.text=_t("Открыть папку результатов","Open results folder");results.pressed.connect(func():OS.shell_open(AppState.results_root().path_join("marl")));left.add_child(results)
	var right=VBoxContainer.new();right.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_theme_constant_override("separation",14);split.add_child(right)
	_section(right,"EXPERIMENT STATUS","СТАТУС ЭКСПЕРИМЕНТА")
	status_label=Label.new();status_label.text=_t("Готово к запуску","Ready");status_label.add_theme_font_size_override("font_size",24);right.add_child(status_label)
	detail_label=Label.new();detail_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;detail_label.modulate=Color("b4c0b6");right.add_child(detail_label)
	var caveat=Label.new();caveat.text=_t("Визуальный replay показывает записанную аналитическую траекторию. Godot не пересчитывает урон и победу. PPO обучает внешнее управление, не MaleCNS. Сравнивайте числа по нескольким независимым seed.","Replay renders the recorded analytical trajectory. Godot does not recalculate damage or winner. PPO trains an external controller, not MaleCNS. Compare metrics across independent seeds.");caveat.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;caveat.modulate=Color("c9b48a");right.add_child(caveat)
	update_marl_status(AppState.marl_progress,AppState.marl_output)

func _t(ru:String,en:String)->String:return ru if str(AppState.settings.get("language","en"))=="ru" else en
func _section(parent:Node,ru:String,en:String):
	var l=Label.new();l.text=_t(ru,en);l.add_theme_font_size_override("font_size",19);l.modulate=Color("c1a573");parent.add_child(l)
func _number(parent:Node,title_text:String,value:float,lo:float,hi:float,cb:Callable):
	var row=HBoxContainer.new();parent.add_child(row);var l=Label.new();l.text=title_text;l.size_flags_horizontal=Control.SIZE_EXPAND_FILL;row.add_child(l)
	var spin=SpinBox.new();spin.min_value=lo;spin.max_value=hi;spin.step=1;spin.value=value;spin.custom_minimum_size.x=150;spin.value_changed.connect(cb);row.add_child(spin)
func _action(parent:Node,caption:String,cb:Callable):
	var b=Button.new();b.text=caption;b.custom_minimum_size.y=48;b.pressed.connect(cb);parent.add_child(b)
func _find_checkpoint()->String:
	var dir=DirAccess.open(AppState.results_root().path_join("marl"));if dir==null:return ""
	var entries=[];dir.list_dir_begin();var n=dir.get_next()
	while n!="":
		if dir.current_is_dir():entries.append(n)
		n=dir.get_next()
	entries.sort();entries.reverse()
	for entry in entries:
		var path=AppState.results_root().path_join("marl").path_join(entry).path_join("checkpoint/ppo_team.zip")
		if FileAccess.file_exists(path):return path
	return ""
func _choose_checkpoint():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.zip ; PPO checkpoint"]);add_child(dialog)
	dialog.file_selected.connect(func(path):checkpoint_path=path;dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.75)
func _run_checkpoint(command:String):
	if checkpoint_path=="" or not FileAccess.file_exists(checkpoint_path):checkpoint_path=_find_checkpoint()
	if checkpoint_path=="":status_label.text=_t("Сначала обучите PPO или выберите checkpoint","Train PPO or choose a checkpoint first");return
	AppState.run_marl_job(command,[checkpoint_path,"--episodes","3","--seed",str(seed_value+1000),"--max-steps",str(episode_steps)])
func _open_replay(filename:String):
	var path=AppState.marl_output.path_join("replays").path_join(filename)
	if not FileAccess.file_exists(path):
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.current_dir=AppState.results_root().path_join("marl");dialog.filters=PackedStringArray(["*.jsonl ; MARL replay"]);add_child(dialog)
		dialog.file_selected.connect(func(selected):AppState.open_marl_replay(selected);dialog.queue_free());dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.8);return
	AppState.open_marl_replay(path)
func _open_matching_replay(prefix:String):
	var replay_dir=AppState.marl_output.path_join("replays")
	var dir=DirAccess.open(replay_dir)
	if dir!=null:
		dir.list_dir_begin();var name=dir.get_next()
		while name!="":
			if not dir.current_is_dir() and name.begins_with(prefix) and name.ends_with(".jsonl"):
				AppState.open_marl_replay(replay_dir.path_join(name));return
			name=dir.get_next()
	_choose_replay()
func _choose_replay():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.current_dir=AppState.results_root().path_join("marl");dialog.filters=PackedStringArray(["*.jsonl ; MARL replay"]);add_child(dialog)
	dialog.file_selected.connect(func(selected):AppState.open_marl_replay(selected);dialog.queue_free());dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.8)
func _open_result_file(relative_path:String):
	var path=AppState.marl_output.path_join(relative_path)
	if FileAccess.file_exists(path):OS.shell_open(path)
	else:
		var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.current_dir=AppState.results_root().path_join("marl");dialog.filters=PackedStringArray(["*.csv,*.png ; Experiment export"]);add_child(dialog)
		dialog.file_selected.connect(func(selected):OS.shell_open(selected);dialog.queue_free());dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.8)
func update_marl_status(progress:Dictionary,output_path:String):
	if not is_instance_valid(status_label):return
	var state=str(progress.get("state","ready"))
	status_label.text=_t("Обучение…","Training…") if state=="training" else (_t("Готово","Complete") if state=="complete" else state)
	var lines=[]
	for key in ["timesteps","target_timesteps","episodes","elapsed_seconds","latest_episode_reward"]:
		if progress.has(key):lines.append("%s: %s" % [key,str(progress[key])])
	if output_path!="":lines.append("\n"+output_path)
	detail_label.text="\n".join(lines)
