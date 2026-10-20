extends Control
const DesignSystem = preload("res://scripts/app/design_system.gd")

var status_label: Label
var detail_label: Label
var status_progress: ProgressBar
var checkpoint_path=""
var seed_value=101
var episode_steps=600
var training_steps=2048
var current_replay=""
var result_path=""
var code_editor: CodeEdit
var code_console: TextEdit
var active_code="agent"
var student_agent_path=""
var student_reward_path=""

func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var appearance=str(AppState.settings.get("appearance","dark"))
	theme=DesignSystem.make_theme(18,appearance)
	var bg=ColorRect.new();bg.color=DesignSystem.ink_for(appearance);bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,42)
	add_child(margin)
	var column=VBoxContainer.new();column.add_theme_constant_override("separation",16);margin.add_child(column)
	var top=HBoxContainer.new();column.add_child(top)
	var title=Label.new();title.text=_t("ЛАБОРАТОРИЯ MARL","MARL LABORATORY");title.add_theme_font_size_override("font_size",34);title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top.add_child(title)
	var back=Button.new();back.text=_t("В меню","Back");back.pressed.connect(AppState.menu);top.add_child(back)
	var intro=Label.new();intro.text=_t("PettingZoo Parallel · Stable-Baselines3 PPO · 16 машин · Python задаёт исход боя","PettingZoo Parallel · Stable-Baselines3 PPO · 16 vehicles · Python owns battle outcomes");intro.modulate=Color("bdc7bd");column.add_child(intro)
	var tab_row=HBoxContainer.new();tab_row.add_theme_constant_override("separation",6);column.add_child(tab_row)
	var tabs=TabContainer.new();tabs.tabs_visible=false;tabs.size_flags_vertical=Control.SIZE_EXPAND_FILL;column.add_child(tabs)
	var experiments_tab=Button.new();experiments_tab.text=_t("Эксперименты","Experiments");experiments_tab.toggle_mode=true;experiments_tab.button_pressed=true;tab_row.add_child(experiments_tab)
	var python_tab=Button.new();python_tab.text="Python";python_tab.toggle_mode=true;tab_row.add_child(python_tab)
	experiments_tab.pressed.connect(func():tabs.current_tab=0;experiments_tab.button_pressed=true;python_tab.button_pressed=false)
	python_tab.pressed.connect(func():tabs.current_tab=1;experiments_tab.button_pressed=false;python_tab.button_pressed=true)
	tabs.tab_changed.connect(func(index):experiments_tab.button_pressed=index==0;python_tab.button_pressed=index==1)
	for tab_button in [experiments_tab,python_tab]:
		tab_button.add_theme_stylebox_override("normal",DesignSystem.tab_style(appearance,false))
		tab_button.add_theme_stylebox_override("hover",DesignSystem.tab_style(appearance,false))
		tab_button.add_theme_stylebox_override("pressed",DesignSystem.tab_style(appearance,true))
		tab_button.add_theme_color_override("font_color",DesignSystem.text_for(appearance))
	var split=HBoxContainer.new();split.add_theme_constant_override("separation",36);tabs.add_child(split);split.name=_t("Эксперименты","Experiments");split.size_flags_vertical=Control.SIZE_EXPAND_FILL
	var left_scroll=ScrollContainer.new();left_scroll.custom_minimum_size.x=520;left_scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL;left_scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;split.add_child(left_scroll)
	var left=VBoxContainer.new();left.size_flags_horizontal=Control.SIZE_EXPAND_FILL;left.add_theme_constant_override("separation",10);left_scroll.add_child(left)
	_section(left,"A · СЛУЧАЙНАЯ БАЗА","A · RANDOM BASELINE")
	_number(left,"Seed",seed_value,1,2147480000,func(v):seed_value=int(v))
	_number(left,"Episode steps / Шаги эпизода",episode_steps,16,1500,func(v):episode_steps=int(v))
	_action(left,_t("Запустить случайную политику","Run random baseline"),func():
		AppState.run_marl_job("baseline",["--episodes","3","--seed",str(seed_value),"--max-steps",str(episode_steps)]))
	var b=Button.new();b.text=_t("Смотреть последний случайный бой","Watch last Random battle");b.pressed.connect(func():_open_replay("random-seed-"+str(seed_value)+".jsonl"));left.add_child(b)
	_section(left,"B · ОБУЧЕНИЕ PPO","B · PPO TRAINING")
	_number(left,"Training steps / Шаги обучения",training_steps,64,500000,func(v):training_steps=int(v))
	_action(left,_t("Обучить PPO и сохранить checkpoint","Train PPO and save checkpoint"),func():
		AppState.run_marl_job("train",["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps)]))
	_action(left,_t("Обучить PPO с reward.py","Train PPO with reward.py"),func():
		_save_current_code()
		_confirm_python_job("train",["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps),"--reward-file",student_reward_path]))
	checkpoint_path=_find_checkpoint()
	var select=Button.new();select.text=_t("Выбрать checkpoint…","Choose checkpoint…");select.pressed.connect(_choose_checkpoint);left.add_child(select)
	_section(left,"C · ОЦЕНКА","C · EVALUATION")
	_action(left,_t("Оценить модель на тестовых seed","Evaluate checkpoint on test seeds"),func():_run_checkpoint("evaluate"))
	_action(left,_t("Сравнить Random и PPO на одинаковых seed","Compare Random and PPO on paired seeds"),func():_run_checkpoint("compare"))
	_action(left,_t("Сравнить четыре стратегии на одинаковых условиях","Compare all four policies"),func():
		_save_current_code()
		var standard=_find_checkpoint_kind(false);var custom=_find_checkpoint_kind(true)
		if standard=="" or custom=="":status_label.text=_t("Сначала обучите PPO со стандартной и пользовательской наградой","Train PPO with standard and custom rewards first");return
		_confirm_python_job("compare-all",["--agent-file",student_agent_path,"--standard-checkpoint",standard,"--custom-reward-checkpoint",custom,"--episodes","3","--seed",str(seed_value+2000),"--max-steps",str(episode_steps)]))
	var trained=Button.new();trained.text=_t("Смотреть бой PPO","Watch trained PPO battle");trained.pressed.connect(func():_open_matching_replay("trained-seed-"));left.add_child(trained)
	var choose_replay=Button.new();choose_replay.text=_t("Открыть любой повтор…","Open any replay…");choose_replay.pressed.connect(_choose_replay);left.add_child(choose_replay)
	var compare_csv=Button.new();compare_csv.text=_t("Открыть CSV сравнения","Open comparison CSV");compare_csv.pressed.connect(func():_open_result_file("comparison.csv"));left.add_child(compare_csv)
	var graph=Button.new();graph.text=_t("Открыть график обучения","Open training graph");graph.pressed.connect(func():_open_result_file("plots/learning_curve.png"));left.add_child(graph)
	var results=Button.new();results.text=_t("Открыть папку результатов","Open results folder");results.pressed.connect(func():OS.shell_open(AppState.results_root().path_join("marl")));left.add_child(results)
	var history=Button.new();history.text=_t("История экспериментов…","Experiment history…");history.pressed.connect(_show_history);left.add_child(history)
	var right=VBoxContainer.new();right.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_theme_constant_override("separation",14);split.add_child(right)
	var status_card=PanelContainer.new();status_card.add_theme_stylebox_override("panel",DesignSystem.panel_style(appearance));right.add_child(status_card)
	var status_content=VBoxContainer.new();status_content.add_theme_constant_override("separation",10);status_card.add_child(status_content)
	_section(status_content,"СТАТУС ЭКСПЕРИМЕНТА","EXPERIMENT STATUS")
	status_label=Label.new();status_label.text=_t("Готово к запуску","Ready");status_label.add_theme_font_size_override("font_size",24);status_content.add_child(status_label)
	status_progress=ProgressBar.new();status_progress.min_value=0;status_progress.max_value=1;status_progress.indeterminate=true;status_progress.custom_minimum_size.y=12;status_content.add_child(status_progress)
	detail_label=Label.new();detail_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;detail_label.modulate=DesignSystem.muted_for(appearance);status_content.add_child(detail_label)
	var workflow_card=PanelContainer.new();workflow_card.add_theme_stylebox_override("panel",DesignSystem.panel_style(appearance));right.add_child(workflow_card)
	var workflow=VBoxContainer.new();workflow.add_theme_constant_override("separation",8);workflow_card.add_child(workflow)
	_section(workflow,"ПОРЯДОК РАБОТЫ","A CLEAR WORKFLOW")
	for item in [
		_t("01  Настройте seed и длину эпизода","01  Set the seed and episode length"),
		_t("02  Измените agent.py или reward.py","02  Edit agent.py or reward.py"),
		_t("03  Проверьте код и запустите стратегию","03  Check the code and run a strategy"),
		_t("04  Оцените и сравните на одинаковых seed","04  Evaluate and compare on paired seeds"),
		_t("05  Откройте повтор и экспортируйте работу","05  Review a replay and export the practical"),
	]:
		var step=Label.new();step.text=item;step.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;step.add_theme_color_override("font_color",DesignSystem.text_for(appearance));workflow.add_child(step)
	var caveat=Label.new();caveat.text=_t("Разделяйте награду при обучении и независимую оценку. PPO обучает внешнюю стратегию и не меняет MaleCNS.","Keep training reward separate from independent evaluation. PPO trains an external strategy and does not change MaleCNS.");caveat.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;caveat.modulate=DesignSystem.muted_for(appearance);right.add_child(caveat)
	_build_programming_tab(tabs)
	update_marl_status(AppState.marl_progress,AppState.marl_output)

func _workspace_dir()->String:
	return ProjectSettings.globalize_path("user://marl_workspace")
func _build_programming_tab(tabs:TabContainer):
	var appearance=str(AppState.settings.get("appearance","dark"))
	var panel=VBoxContainer.new();panel.name=_t("Python","Python");panel.add_theme_constant_override("separation",8);tabs.add_child(panel)
	student_agent_path=_workspace_dir().path_join("agent.py");student_reward_path=_workspace_dir().path_join("reward.py")
	DirAccess.make_dir_recursive_absolute(_workspace_dir())
	if not FileAccess.file_exists(student_agent_path):FileAccess.open(student_agent_path,FileAccess.WRITE).store_string('import numpy as np\n\ndef act(observation, context=None):\n    action = np.zeros(6, dtype=np.float32)\n    action[0] = 0.5\n    return action\n')
	if not FileAccess.file_exists(student_reward_path):FileAccess.open(student_reward_path,FileAccess.WRITE).store_string('def calculate_reward(components):\n    return float(3.0 * components["objective_capture"] + 0.01 * components["damage_dealt"] - 4.0 * components["own_death"])\n')
	var warning=Label.new();warning.text=_t("Python запускается в отдельном backend-процессе с правами вашей учётной записи. Это не песочница: запускайте только знакомый код.","Python runs in a separate backend process with your account permissions. This is not a sandbox: run code only if you trust it.");warning.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;warning.modulate=Color("e5c27b");panel.add_child(warning)
	var row=HBoxContainer.new();panel.add_child(row)
	var agent_tab=Button.new();agent_tab.text="agent.py";agent_tab.pressed.connect(func():_switch_code("agent"));row.add_child(agent_tab)
	var reward_tab=Button.new();reward_tab.text="reward.py";reward_tab.pressed.connect(func():_switch_code("reward"));row.add_child(reward_tab)
	var import_button=Button.new();import_button.text=_t("Импортировать .py…","Import .py…");import_button.pressed.connect(_import_python);row.add_child(import_button)
	var save_button=Button.new();save_button.text=_t("Сохранить","Save");save_button.pressed.connect(_save_current_code);row.add_child(save_button)
	var restore_button=Button.new();restore_button.text=_t("Шаблон","Template");restore_button.pressed.connect(_restore_template);row.add_child(restore_button)
	code_editor=CodeEdit.new();code_editor.size_flags_vertical=Control.SIZE_EXPAND_FILL;code_editor.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_editor.gutters_draw_line_numbers=true;code_editor.indent_automatic=true;code_editor.indent_use_spaces=true;code_editor.indent_size=4;code_editor.add_theme_color_override("font_color",DesignSystem.text_for(appearance));code_editor.add_theme_color_override("current_line_color",Color("e9eee2") if DesignSystem.is_light(appearance) else Color("283328"));code_editor.add_theme_color_override("line_number_color",DesignSystem.muted_for(appearance));panel.add_child(code_editor)
	var highlighter=CodeHighlighter.new();highlighter.number_color=Color("82928a");highlighter.symbol_color=Color("d1b579");highlighter.function_color=Color("8cc8b2");highlighter.add_color_region("\"","\"",Color("a7c88b"));highlighter.add_color_region("'","'",Color("a7c88b"));highlighter.add_keyword_color("def",Color("ce9aef"));highlighter.add_keyword_color("return",Color("ce9aef"));highlighter.add_keyword_color("import",Color("ce9aef"));highlighter.add_keyword_color("from",Color("ce9aef"));highlighter.add_keyword_color("if",Color("ce9aef"));highlighter.add_keyword_color("for",Color("ce9aef"));highlighter.add_keyword_color("in",Color("ce9aef"));code_editor.syntax_highlighter=highlighter
	var actions=HBoxContainer.new();panel.add_child(actions)
	var check=Button.new();check.text=_t("Проверить код","Check code");check.pressed.connect(func():_confirm_student_run("check"));actions.add_child(check)
	var run=Button.new();run.text=_t("Запустить свою стратегию","Run strategy");run.pressed.connect(func():_confirm_student_run("student"));actions.add_child(run)
	var export=Button.new();export.text=_t("Экспортировать работу","Export practical");export.pressed.connect(func():_save_current_code();AppState.run_marl_job("export",["--workspace",_workspace_dir(),"--sessions-root",AppState.results_root().path_join("marl")]));actions.add_child(export)
	var stop=Button.new();stop.text=_t("Остановить","Stop");stop.pressed.connect(AppState.stop_marl_job);actions.add_child(stop)
	code_console=TextEdit.new();code_console.custom_minimum_size.y=100;code_console.editable=false;code_console.placeholder_text=_t("Консоль и ошибки появятся здесь","Console and errors will appear here");panel.add_child(code_console)
	code_editor.text=FileAccess.get_file_as_string(student_agent_path)
func _active_code_path()->String:return student_agent_path if active_code=="agent" else student_reward_path
func _switch_code(next:String):
	if is_instance_valid(code_editor):_save_current_code()
	active_code=next
	if is_instance_valid(code_editor):code_editor.text=FileAccess.get_file_as_string(_active_code_path()) if FileAccess.file_exists(_active_code_path()) else ""
func _save_current_code():
	if not is_instance_valid(code_editor):return
	var file=FileAccess.open(_active_code_path(),FileAccess.WRITE)
	if file:file.store_string(code_editor.text)
func _restore_template():
	code_editor.text='import numpy as np\n\ndef act(observation, context=None):\n    action = np.zeros(6, dtype=np.float32)\n    action[0] = 0.5\n    return action\n' if active_code=="agent" else 'def calculate_reward(components):\n    return float(3.0 * components["objective_capture"] + 0.01 * components["damage_dealt"] - 4.0 * components["own_death"])\n'
	_save_current_code()
func _import_python():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.py ; Python source"]);add_child(dialog)
	dialog.file_selected.connect(func(path):code_editor.text=FileAccess.get_file_as_string(path);_save_current_code();dialog.queue_free());dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.75)
func _confirm_student_run(command:String):
	_save_current_code()
	var args=["--agent-file",student_agent_path,"--reward-file",student_reward_path]
	if command=="student":args.append_array(["--episodes","3","--seed",str(seed_value),"--max-steps",str(episode_steps)])
	_confirm_python_job(command,args)
func _confirm_python_job(command:String,args:Array):
	var consent=ConfirmationDialog.new();consent.title=_t("Запуск Python-кода","Run Python code");consent.dialog_text=_t("Код будет выполнен в отдельном процессе с доступом к файлам и возможностями вашей учётной записи. Это не песочница: запускайте только код, которому доверяете.","Code will run in a separate process with your account permissions. This is not a sandbox; run code only if you trust it.");add_child(consent)
	consent.confirmed.connect(func():AppState.run_marl_job(command,args);consent.queue_free())
	consent.canceled.connect(consent.queue_free);consent.popup_centered()

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
func _find_checkpoint_kind(custom_reward:bool)->String:
	var root=AppState.results_root().path_join("marl");var dir=DirAccess.open(root);if dir==null:return ""
	var entries=[];dir.list_dir_begin();var n=dir.get_next()
	while n!="":
		if dir.current_is_dir() and n not in [".",".."]:entries.append(n)
		n=dir.get_next()
	entries.sort();entries.reverse()
	for entry in entries:
		var base=root.path_join(entry);var manifest=AppState.read_json(base.path_join("manifest.json"));var checkpoint=base.path_join("checkpoint/ppo_team.zip")
		if FileAccess.file_exists(checkpoint) and bool(manifest.get("custom_reward",false))==custom_reward:return checkpoint
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
func _show_history():
	var dialog=AcceptDialog.new();dialog.title=_t("История экспериментов","Experiment history");dialog.dialog_text=_t("Выберите запуск и откройте его папку с кодом, метриками и повтором.","Select a run to open its folder with source, metrics and replay.");dialog.size=Vector2i(760,520);add_child(dialog)
	var list=ItemList.new();list.custom_minimum_size=Vector2(700,390);dialog.add_child(list)
	var entries=AppState.marl_history()
	for entry in entries:
		var manifest=entry.get("manifest",{});var label=str(entry.get("name",""))+" · "+str(manifest.get("experiment",manifest.get("algorithm",manifest.get("kind","experiment"))))
		list.add_item(label);list.set_item_metadata(list.item_count-1,str(entry.get("path","")))
	list.item_activated.connect(func(index):var path=str(list.get_item_metadata(index));if path!="":OS.shell_open(path);dialog.queue_free())
	if entries.is_empty():list.add_item(_t("Сохранённых запусков пока нет","No saved runs yet"))
	dialog.confirmed.connect(func():
		var selected=list.get_selected_items()
		if selected.size()>0:
			var path=str(list.get_item_metadata(selected[0]))
			if path!="":OS.shell_open(path)
		dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered()
func update_marl_status(progress:Dictionary,output_path:String):
	if not is_instance_valid(status_label):return
	var state=str(progress.get("state","ready"))
	var labels={
		"ready":_t("Готово к запуску","Ready to start"),
		"starting":_t("Запуск Python…","Starting Python…"),
		"initializing":_t("Подготовка модели…","Preparing model…"),
		"training":_t("Обучение PPO…","Training PPO…"),
		"finalizing":_t("Сохранение результатов…","Saving results…"),
		"complete":_t("Готово","Complete"),
		"error":_t("Ошибка","Error"),
		"cancelled":_t("Остановлено","Cancelled"),
	}
	status_label.text=str(labels.get(state,state.capitalize()))
	var current=float(progress.get("timesteps",progress.get("completed",0)))
	var target=float(progress.get("target_timesteps",progress.get("total",0)))
	var terminal=state in ["complete","error","cancelled"]
	status_progress.visible=state!="ready"
	status_progress.indeterminate=not terminal and (target<=0.0 or state in ["starting","initializing","finalizing"])
	status_progress.max_value=maxf(1.0,target)
	status_progress.value=target if state=="complete" else current
	var lines=[]
	for key in ["timesteps","target_timesteps","episodes","elapsed_seconds","latest_episode_reward"]:
		if progress.has(key):lines.append("%s: %s" % [key,str(progress[key])])
	if output_path!="":lines.append("\n"+output_path)
	detail_label.text="\n".join(lines)
	if is_instance_valid(code_console):
		var log_path=output_path.path_join("execution.log") if output_path!="" else ""
		var log_text=FileAccess.get_file_as_string(log_path) if log_path!="" and FileAccess.file_exists(log_path) else ""
		var message=str(progress.get("message",""))
		code_console.text=log_text if log_text!="" else message
