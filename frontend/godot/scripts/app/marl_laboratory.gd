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
var code_status_label: Label
var code_cursor_label: Label
var code_file_tabs: Dictionary = {}
var code_stop_button: Button
var code_dirty := false
var loading_code := false

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
	var toolbar=HBoxContainer.new();toolbar.add_theme_constant_override("separation",6);panel.add_child(toolbar)
	var agent_tab=Button.new();agent_tab.text="agent.py";agent_tab.pressed.connect(func():_switch_code("agent"));toolbar.add_child(agent_tab)
	var reward_tab=Button.new();reward_tab.text="reward.py";reward_tab.pressed.connect(func():_switch_code("reward"));toolbar.add_child(reward_tab)
	code_file_tabs={"agent":agent_tab,"reward":reward_tab}
	for key in code_file_tabs:
		var file_tab:Button=code_file_tabs[key];file_tab.toggle_mode=true;file_tab.button_pressed=key==active_code
		file_tab.add_theme_stylebox_override("normal",DesignSystem.tab_style(appearance,key==active_code));file_tab.add_theme_stylebox_override("hover",DesignSystem.tab_style(appearance,key==active_code));file_tab.add_theme_stylebox_override("pressed",DesignSystem.tab_style(appearance,true));file_tab.add_theme_color_override("font_color",DesignSystem.text_for(appearance))
	var spacer=Control.new();spacer.size_flags_horizontal=Control.SIZE_EXPAND_FILL;toolbar.add_child(spacer)
	var save_button=Button.new();save_button.text=_t("Сохранить","Save");save_button.tooltip_text="⌘S / Ctrl+S";save_button.pressed.connect(_save_current_code);toolbar.add_child(save_button)
	var check=Button.new();check.text=_t("Проверить","Check");check.pressed.connect(func():_confirm_student_run("check"));toolbar.add_child(check)
	var run=Button.new();run.text=_t("▶ Запустить","▶ Run");run.pressed.connect(func():_confirm_student_run("student"));toolbar.add_child(run)
	code_stop_button=Button.new();code_stop_button.text=_t("Остановить","Stop");code_stop_button.visible=false;code_stop_button.pressed.connect(AppState.stop_marl_job);toolbar.add_child(code_stop_button)
	var more=MenuButton.new();more.text="⋯";more.tooltip_text=_t("Другие действия","More actions");toolbar.add_child(more)
	var more_menu=more.get_popup();more_menu.add_item(_t("Импортировать файл Python…","Import Python file…"),1);more_menu.add_item(_t("Восстановить шаблон","Restore template"),2);more_menu.add_separator();more_menu.add_item(_t("Экспортировать практическую…","Export practical…"),3);more_menu.add_separator();more_menu.add_item(_t("О безопасности Python…","About Python security…"),4)
	more_menu.id_pressed.connect(_on_editor_menu_action)
	var editor_split=VSplitContainer.new();editor_split.size_flags_vertical=Control.SIZE_EXPAND_FILL;editor_split.size_flags_horizontal=Control.SIZE_EXPAND_FILL;panel.add_child(editor_split)
	code_editor=CodeEdit.new();code_editor.custom_minimum_size.y=300;code_editor.size_flags_vertical=Control.SIZE_EXPAND_FILL;code_editor.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_editor.gutters_draw_line_numbers=true;code_editor.gutters_draw_fold_gutter=true;code_editor.indent_automatic=true;code_editor.indent_use_spaces=true;code_editor.indent_size=4;code_editor.auto_brace_completion_enabled=true;code_editor.add_theme_color_override("font_color",DesignSystem.text_for(appearance));code_editor.add_theme_color_override("font_readonly_color",DesignSystem.muted_for(appearance));code_editor.add_theme_color_override("current_line_color",Color("edf1e7") if DesignSystem.is_light(appearance) else Color("293229"));code_editor.add_theme_color_override("line_number_color",Color("788273") if DesignSystem.is_light(appearance) else Color("8c9889"));code_editor.add_theme_color_override("caret_color",DesignSystem.accent_for(appearance));code_editor.add_theme_color_override("selection_color",Color("b8c9a5",0.48) if DesignSystem.is_light(appearance) else Color("829a6b",0.42));code_editor.add_theme_color_override("brace_mismatch_color",Color("df746a"));code_editor.add_theme_color_override("word_highlighted_color",Color("d8e4ce",0.18) if DesignSystem.is_light(appearance) else Color("bbd49c",0.14));code_editor.add_theme_constant_override("line_spacing",3)
	var mono=SystemFont.new();mono.font_names=PackedStringArray(["SF Mono","Menlo","Monaco","monospace"]);code_editor.add_theme_font_override("font",mono);code_editor.add_theme_font_size_override("font_size",17);editor_split.add_child(code_editor)
	code_editor.syntax_highlighter=_make_python_highlighter(appearance)
	code_editor.text_changed.connect(_on_code_changed);code_editor.caret_changed.connect(_update_code_cursor)
	var output_panel=VBoxContainer.new();output_panel.custom_minimum_size.y=140;output_panel.size_flags_vertical=Control.SIZE_EXPAND_FILL;output_panel.add_theme_constant_override("separation",4);editor_split.add_child(output_panel)
	var output_header=HBoxContainer.new();output_panel.add_child(output_header)
	var output_title=Label.new();output_title.text=_t("ВЫВОД И ОШИБКИ","OUTPUT & ERRORS");output_title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;output_title.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));output_header.add_child(output_title)
	var clear_output=Button.new();clear_output.text=_t("Очистить","Clear");clear_output.pressed.connect(func():code_console.clear());output_header.add_child(clear_output)
	code_console=TextEdit.new();code_console.size_flags_vertical=Control.SIZE_EXPAND_FILL;code_console.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_console.editable=false;code_console.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;code_console.placeholder_text=_t("Проверка кода, запуск и ошибки появятся здесь","Code checks, runs and errors appear here");code_console.add_theme_color_override("font_color",Color("c8d1c4") if not DesignSystem.is_light(appearance) else Color("384237"));code_console.add_theme_color_override("font_readonly_color",Color("c8d1c4") if not DesignSystem.is_light(appearance) else Color("384237"));code_console.add_theme_color_override("caret_color",DesignSystem.muted_for(appearance));code_console.add_theme_stylebox_override("read_only",_code_panel_style(appearance));code_console.add_theme_font_override("font",mono);code_console.add_theme_font_size_override("font_size",14);output_panel.add_child(code_console)
	var status_bar=HBoxContainer.new();status_bar.add_theme_constant_override("separation",18);panel.add_child(status_bar)
	code_status_label=Label.new();code_status_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_status_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(code_status_label)
	code_cursor_label=Label.new();code_cursor_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(code_cursor_label)
	var language_label=Label.new();language_label.text="Python · UTF-8 · Spaces: 4";language_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(language_label)
	var security_label=Label.new();security_label.text=_t("НЕ ПЕСОЧНИЦА","NOT SANDBOXED");security_label.tooltip_text=_t("Python-код запускается с правами вашей учётной записи и доступом к её файлам. Запускайте только знакомый код.","Python runs with your account permissions and can access your files. Run code only if you trust it.");security_label.add_theme_color_override("font_color",Color("a9823d") if DesignSystem.is_light(appearance) else Color("c1a573"));status_bar.add_child(security_label)
	loading_code=true;code_editor.text=FileAccess.get_file_as_string(student_agent_path);loading_code=false;_set_code_dirty(false);_update_code_cursor()

func _on_editor_menu_action(id:int):
	match id:
		1:_import_python()
		2:_restore_template()
		3:
			_save_current_code()
			AppState.run_marl_job("export",["--workspace",_workspace_dir(),"--sessions-root",AppState.results_root().path_join("marl")])
		4:
			var dialog=AcceptDialog.new();dialog.title=_t("Безопасность Python","Python security");dialog.dialog_text=_t("Python работает в отдельном процессе с правами вашей учётной записи и доступом к её файлам. Это не песочница: запускайте только код, которому доверяете.","Python runs in a separate process with your account permissions and access to your files. This is not a sandbox: only run code you trust.");add_child(dialog);dialog.confirmed.connect(dialog.queue_free);dialog.popup_centered()

func _make_python_highlighter(appearance:String)->CodeHighlighter:
	var light=DesignSystem.is_light(appearance)
	var keyword_color=Color("8157a6") if light else Color("d7a5f2")
	var type_color=Color("12678d") if light else Color("83c9e8")
	var builtin_color=Color("8c5a10") if light else Color("e4bf80")
	var string_color=Color("477c38") if light else Color("a9cb8b")
	var comment_color=Color("6a7662") if light else Color("879487")
	var number_color=Color("ad4b27") if light else Color("f0a27e")
	var function_color=Color("176d64") if light else Color("83cdb9")
	var symbol_color=Color("725d3d") if light else Color("d9c59e")
	var highlighter=CodeHighlighter.new()
	highlighter.number_color=number_color;highlighter.symbol_color=symbol_color;highlighter.function_color=function_color
	highlighter.add_color_region("\"\"\"","\"\"\"",string_color);highlighter.add_color_region("'''","'''",string_color)
	highlighter.add_color_region("\"","\"",string_color);highlighter.add_color_region("'","'",string_color)
	highlighter.add_color_region("#","",comment_color,true)
	for word in ["def","class","return","yield","import","from","as","if","elif","else","for","while","in","not","and","or","is","try","except","finally","raise","pass","break","continue","with","lambda","global","nonlocal","assert","del","async","await"]:highlighter.add_keyword_color(word,keyword_color)
	for word in ["True","False","None","NotImplemented","Ellipsis"]:highlighter.add_keyword_color(word,builtin_color)
	# Keep Python and NumPy scalar/container types visibly distinct from plain identifiers.
	for word in ["int","float","bool","str","bytes","list","tuple","dict","set","frozenset","complex","object","type","range","slice","bytearray","memoryview","int8","int16","int32","int64","uint8","uint16","uint32","uint64","float16","float32","float64","float128","bool_","ndarray"]:highlighter.add_keyword_color(word,type_color)
	for word in ["np.int","np.float","np.bool","np.str","np.int8","np.int16","np.int32","np.int64","np.uint8","np.uint16","np.uint32","np.uint64","np.float16","np.float32","np.float64","np.bool_","np.ndarray"]:highlighter.add_keyword_color(word,type_color)
	for word in ["print","len","enumerate","zip","map","filter","sum","min","max","abs","round","isinstance","super","open"]:highlighter.add_keyword_color(word,builtin_color)
	return highlighter

func _code_panel_style(appearance:String)->StyleBoxFlat:
	var style=StyleBoxFlat.new();style.bg_color=Color("fbfaf6") if DesignSystem.is_light(appearance) else Color("1b211b");style.border_color=Color("c5c8bd") if DesignSystem.is_light(appearance) else Color("465044");style.set_border_width_all(1);style.set_corner_radius_all(6);style.content_margin_left=10;style.content_margin_right=10;style.content_margin_top=8;style.content_margin_bottom=8;return style

func _on_code_changed():
	if loading_code:return
	_set_code_dirty(true);_update_code_cursor()

func _set_code_dirty(dirty:bool):
	code_dirty=dirty
	if code_file_tabs.is_empty():return
	var button=code_file_tabs.get(active_code)
	if is_instance_valid(button):button.text=("● " if dirty else "")+active_code+".py";button.button_pressed=true
	for key in code_file_tabs:
		var tab:Button=code_file_tabs[key]
		if is_instance_valid(tab) and key!=active_code:tab.button_pressed=false
	if is_instance_valid(code_status_label):code_status_label.text=_t("Не сохранено","Unsaved changes") if dirty else _t("Сохранено","Saved")

func _update_code_cursor():
	if not is_instance_valid(code_editor) or not is_instance_valid(code_cursor_label):return
	code_cursor_label.text="Ln %d, Col %d" % [code_editor.get_caret_line()+1,code_editor.get_caret_column()+1]

func _unhandled_key_input(event:InputEvent):
	if not event is InputEventKey or not event.pressed or event.echo or not is_instance_valid(code_editor):return
	var key=event as InputEventKey
	if key.keycode==KEY_S and (key.ctrl_pressed or key.meta_pressed):
		_save_current_code();get_viewport().set_input_as_handled()
func _active_code_path()->String:return student_agent_path if active_code=="agent" else student_reward_path
func _switch_code(next:String):
	if is_instance_valid(code_editor):_save_current_code()
	active_code=next
	if is_instance_valid(code_editor):
		loading_code=true;code_editor.text=FileAccess.get_file_as_string(_active_code_path()) if FileAccess.file_exists(_active_code_path()) else "";loading_code=false
		_set_code_dirty(false);_update_code_cursor()
func _save_current_code():
	if not is_instance_valid(code_editor):return
	var file=FileAccess.open(_active_code_path(),FileAccess.WRITE)
	if file:file.store_string(code_editor.text);file.close();_set_code_dirty(false)
func _restore_template():
	loading_code=true
	code_editor.text='import numpy as np\n\ndef act(observation, context=None):\n    action = np.zeros(6, dtype=np.float32)\n    action[0] = 0.5\n    return action\n' if active_code=="agent" else 'def calculate_reward(components):\n    return float(3.0 * components["objective_capture"] + 0.01 * components["damage_dealt"] - 4.0 * components["own_death"])\n'
	loading_code=false;_set_code_dirty(true);_save_current_code()
func _import_python():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.filters=PackedStringArray(["*.py ; Python source"]);add_child(dialog)
	dialog.file_selected.connect(func(path):loading_code=true;code_editor.text=FileAccess.get_file_as_string(path);loading_code=false;_set_code_dirty(true);_save_current_code();_update_code_cursor();dialog.queue_free());dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.75)
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
	if is_instance_valid(code_stop_button):code_stop_button.visible=state in ["starting","initializing","training","finalizing"]
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
		code_console.scroll_vertical=code_console.get_line_count()
