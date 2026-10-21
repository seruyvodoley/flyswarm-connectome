extends Control
const DesignSystem = preload("res://scripts/app/design_system.gd")

var status_label: Label
var detail_label: Label
var status_progress: ProgressBar
var checkpoint_path=""
var seed_value=101
var episode_steps=600
var training_steps=2048
var training_tier="C"
var training_architecture="parameter_sharing"
var current_replay=""
var result_path=""
var code_editor: CodeEdit
var code_console: TextEdit
var active_code="agent"
var student_agent_path=""
var student_reward_path=""
var code_status_label: Label
var code_cursor_label: Label
var code_file_items: Dictionary = {}
var code_explorer: VBoxContainer
var code_search_popup: PanelContainer
var code_search_layer: CanvasLayer
var code_search_mode: OptionButton
var code_find_input: LineEdit
var code_find_status: Label
var code_find_last_query := ""
var code_find_last_match := -1
var code_breadcrumb: Label
var code_stop_button: Button
var editor_split: VSplitContainer
var terminal_cwd_input: LineEdit
var terminal_command_input: LineEdit
var terminal_environment_button: Button
var terminal_stop_button: Button
var terminal_cwd := ""
var terminal_venv := ""
var terminal_pid := -1
var terminal_output_path := ""
var terminal_status_path := ""
var terminal_last_output := ""
var terminal_console_prefix := ""
var terminal_poll_elapsed := 0.0
var console_mode := "jobs"
var code_dirty := false
var loading_code := false

func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var appearance=str(AppState.settings.get("appearance","dark"))
	theme=DesignSystem.make_theme(18,appearance)
	var bg=ColorRect.new();bg.color=DesignSystem.ink_for(appearance);bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,26)
	add_child(margin)
	var column=VBoxContainer.new();column.add_theme_constant_override("separation",10);margin.add_child(column)
	var top=HBoxContainer.new();column.add_child(top)
	var title=Label.new();title.text=_t("ЛАБОРАТОРИЯ MARL","MARL LABORATORY");title.add_theme_font_size_override("font_size",34);title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;top.add_child(title)
	var back=Button.new();back.text=_t("В меню","Back");back.pressed.connect(AppState.menu);top.add_child(back)
	var intro=Label.new();intro.text=_t("16 машин · настройте политику, запустите и сравните результаты","16 vehicles · configure a policy, run it, and compare results");intro.modulate=Color("bdc7bd");column.add_child(intro)
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
		AppState.run_marl_job("baseline",["--episodes","3","--seed",str(seed_value),"--max-steps",str(episode_steps),"--tier",training_tier]))
	var b=Button.new();b.text=_t("Смотреть последний случайный бой","Watch last Random battle");b.pressed.connect(func():_open_replay("random-seed-"+str(seed_value)+".jsonl"));left.add_child(b)
	_section(left,"B · ОБУЧЕНИЕ PPO","B · PPO TRAINING")
	var tier_row=HBoxContainer.new();left.add_child(tier_row)
	var tier_label=Label.new();tier_label.text=_t("Учебная задача","Learning task");tier_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;tier_row.add_child(tier_label)
	var tier_picker=OptionButton.new();tier_picker.add_item(_t("A · захват точки · 1 на 1 без стрельбы","A · capture basics · 1v1 without weapons"));tier_picker.add_item(_t("B · тактика · 4 на 4","B · tactics · 4v4"));tier_picker.add_item(_t("C · полный бой · 8 на 8","C · full battle · 8v8"));tier_picker.selected=0;tier_picker.item_selected.connect(func(index):training_tier=chr(65+index));tier_row.add_child(tier_picker)
	var architecture_row=HBoxContainer.new();left.add_child(architecture_row)
	var architecture_label=Label.new();architecture_label.text=_t("Архитектура PPO","PPO architecture");architecture_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;architecture_row.add_child(architecture_label)
	var architecture_picker=OptionButton.new();architecture_picker.add_item(_t("Общая политика на каждый танк","Shared policy per vehicle"));architecture_picker.add_item(_t("Централизованная политика на команду","Centralized team policy"));architecture_picker.selected=0
	architecture_picker.item_selected.connect(func(index):training_architecture="parameter_sharing" if index==0 else "centralized");architecture_row.add_child(architecture_picker)
	var architecture_note=Label.new();architecture_note.text=_t("Общая политика получает наблюдение одного танка и выдаёт 6 действий. Это parameter-sharing PPO с локальной value-сетью, не MAPPO.","Shared PPO reads one vehicle observation and outputs six actions. It uses a local value function; it is not MAPPO.");architecture_note.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;architecture_note.modulate=DesignSystem.muted_for(appearance);left.add_child(architecture_note)
	_number(left,"Training steps / Шаги обучения",training_steps,64,500000,func(v):training_steps=int(v))
	_action(left,_t("Обучить PPO и сохранить checkpoint","Train PPO and save checkpoint"),func():
		AppState.run_marl_job("train",["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps),"--tier",training_tier,"--architecture",training_architecture]))
	_action(left,_t("Обучить PPO с reward.py","Train PPO with reward.py"),func():
		_save_current_code()
		_confirm_python_job("train",["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps),"--tier",training_tier,"--architecture",training_architecture,"--reward-file",student_reward_path]))
	checkpoint_path=_find_checkpoint()
	var select=Button.new();select.text=_t("Выбрать checkpoint…","Choose checkpoint…");select.pressed.connect(_choose_checkpoint);left.add_child(select)
	_action(left,_t("Продолжить выбранный checkpoint","Continue selected checkpoint"),func():
		if checkpoint_path=="" or not FileAccess.file_exists(checkpoint_path):status_label.text=_t("Сначала выберите checkpoint PPO","Choose a PPO checkpoint first");return
		var args=["--steps",str(training_steps),"--seed",str(seed_value),"--max-steps",str(episode_steps),"--tier",training_tier,"--continue-from",checkpoint_path]
		var metadata=AppState.read_json(checkpoint_path.get_base_dir().path_join("ppo_team.metadata.json"))
		args.append_array(["--architecture","parameter_sharing" if str(metadata.get("architecture",""))=="parameter_sharing_mlp_128x2" else "centralized"])
		if str(metadata.get("custom_reward_sha256",""))!="":args.append_array(["--reward-file",student_reward_path])
		AppState.run_marl_job("train",args))
	_section(left,"C · ОЦЕНКА","C · EVALUATION")
	_action(left,_t("Оценить модель на тестовых seed","Evaluate checkpoint on test seeds"),func():_run_checkpoint("evaluate"))
	_action(left,_t("Сравнить Random и PPO на одинаковых seed","Compare Random and PPO on paired seeds"),func():_run_checkpoint("compare"))
	_action(left,_t("Сравнить четыре стратегии на одинаковых условиях","Compare all four policies"),func():
		_save_current_code()
		var standard=_find_checkpoint_kind(false);var custom=_find_checkpoint_kind(true)
		if standard=="" or custom=="":status_label.text=_t("Сначала обучите PPO со стандартной и пользовательской наградой","Train PPO with standard and custom rewards first");return
		_confirm_python_job("compare-all",["--agent-file",student_agent_path,"--standard-checkpoint",standard,"--custom-reward-checkpoint",custom,"--episodes","3","--seed",str(seed_value+2000),"--max-steps",str(episode_steps),"--tier",training_tier]))
	var trained=Button.new();trained.text=_t("Смотреть бой PPO","Watch trained PPO battle");trained.pressed.connect(func():_open_matching_replay("trained-seed-"));left.add_child(trained)
	var choose_replay=Button.new();choose_replay.text=_t("Открыть любой повтор…","Open any replay…");choose_replay.pressed.connect(_choose_replay);left.add_child(choose_replay)
	var compare_csv=Button.new();compare_csv.text=_t("Открыть CSV сравнения","Open comparison CSV");compare_csv.pressed.connect(func():_open_result_file("comparison.csv"));left.add_child(compare_csv)
	var graph=Button.new();graph.text=_t("Открыть график обучения","Open training graph");graph.pressed.connect(func():_open_result_file("plots/learning_curve.png"));left.add_child(graph)
	var diagnostics_graph=Button.new();diagnostics_graph.text=_t("Открыть диагностику PPO","Open PPO diagnostics");diagnostics_graph.pressed.connect(func():_open_result_file("plots/ppo_diagnostics.png"));left.add_child(diagnostics_graph)
	var results=Button.new();results.text=_t("Открыть папку результатов","Open results folder");results.pressed.connect(func():OS.shell_open(AppState.results_root().path_join("marl")));left.add_child(results)
	var history=Button.new();history.text=_t("История экспериментов…","Experiment history…");history.pressed.connect(_show_history);left.add_child(history)
	var right=VBoxContainer.new();right.size_flags_horizontal=Control.SIZE_EXPAND_FILL;right.add_theme_constant_override("separation",14);split.add_child(right)
	var status_card=PanelContainer.new();status_card.add_theme_stylebox_override("panel",DesignSystem.panel_style(appearance));right.add_child(status_card)
	var status_content=VBoxContainer.new();status_content.add_theme_constant_override("separation",10);status_card.add_child(status_content)
	_section(status_content,"СТАТУС ЭКСПЕРИМЕНТА","EXPERIMENT STATUS")
	status_label=Label.new();status_label.text=_t("Готово к запуску","Ready");status_label.add_theme_font_size_override("font_size",24);status_content.add_child(status_label)
	status_progress=ProgressBar.new();status_progress.min_value=0;status_progress.max_value=1;status_progress.indeterminate=true;status_progress.custom_minimum_size.y=12;status_content.add_child(status_progress)
	detail_label=Label.new();detail_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;detail_label.modulate=DesignSystem.muted_for(appearance);status_content.add_child(detail_label)
	var control_row=HBoxContainer.new();status_content.add_child(control_row)
	var pause_training=Button.new();pause_training.text=_t("Пауза / продолжить","Pause / resume");pause_training.pressed.connect(AppState.toggle_marl_pause);control_row.add_child(pause_training)
	var stop_training=Button.new();stop_training.text=_t("Остановить и сохранить","Stop and save");stop_training.pressed.connect(AppState.stop_marl_job);control_row.add_child(stop_training)
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
	var panel=VBoxContainer.new();panel.name=_t("Python","Python");panel.add_theme_constant_override("separation",4);tabs.add_child(panel)
	student_agent_path=_workspace_dir().path_join("agent.py");student_reward_path=_workspace_dir().path_join("reward.py")
	DirAccess.make_dir_recursive_absolute(_workspace_dir())
	if not FileAccess.file_exists(student_agent_path):FileAccess.open(student_agent_path,FileAccess.WRITE).store_string('import numpy as np\n\ndef act(observation, context=None):\n    action = np.zeros(6, dtype=np.float32)\n    action[0] = 0.5\n    return action\n')
	if not FileAccess.file_exists(student_reward_path):FileAccess.open(student_reward_path,FileAccess.WRITE).store_string('def calculate_reward(components):\n    return float(3.0 * components["objective_capture"] + 0.01 * components["damage_dealt"] - 4.0 * components["own_death"])\n')
	var toolbar_frame=PanelContainer.new();toolbar_frame.add_theme_stylebox_override("panel",_editor_toolbar_style(appearance));panel.add_child(toolbar_frame)
	var toolbar=HBoxContainer.new();toolbar.add_theme_constant_override("separation",5);toolbar_frame.add_child(toolbar)
	var save_button=Button.new();save_button.text=_t("Сохранить","Save");save_button.tooltip_text=_t("Сохранить текущий файл · ⌘S / Ctrl+S","Save current file · ⌘S / Ctrl+S");save_button.pressed.connect(_save_current_code);toolbar.add_child(save_button)
	var check=Button.new();check.text=_t("Проверить код","Check code");check.tooltip_text=_t("Проверить agent.py и reward.py","Validate agent.py and reward.py");check.pressed.connect(func():_confirm_student_run("check"));toolbar.add_child(check)
	var run=Button.new();run.text=_t("▶ Запустить агента","▶ Run agent");run.tooltip_text=_t("Оценить агента на трёх эпизодах · F5","Evaluate the agent over three episodes · F5");run.pressed.connect(func():_confirm_student_run("student"));toolbar.add_child(run)
	code_stop_button=Button.new();code_stop_button.text=_t("Остановить","Stop");code_stop_button.visible=false;code_stop_button.pressed.connect(AppState.stop_marl_job);toolbar.add_child(code_stop_button)
	var more=MenuButton.new();more.text="⋯";more.tooltip_text=_t("Другие действия","More actions");toolbar.add_child(more)
	var more_menu=more.get_popup();more_menu.add_item(_t("Импортировать файл Python…","Import Python file…"),1);more_menu.add_item(_t("Восстановить шаблон","Restore template"),2);more_menu.add_separator();more_menu.add_item(_t("Экспортировать практическую…","Export practical…"),3)
	more_menu.id_pressed.connect(_on_editor_menu_action)
	var workspace=HBoxContainer.new();workspace.size_flags_vertical=Control.SIZE_EXPAND_FILL;workspace.size_flags_horizontal=Control.SIZE_EXPAND_FILL;workspace.add_theme_constant_override("separation",0);panel.add_child(workspace)
	var activity=VBoxContainer.new();activity.custom_minimum_size.x=48;activity.add_theme_constant_override("separation",8);workspace.add_child(activity)
	var explorer_icon=Button.new();explorer_icon.text="▤";explorer_icon.tooltip_text=_t("Проводник","Explorer");explorer_icon.pressed.connect(func():code_explorer.visible=true);activity.add_child(explorer_icon)
	var search_icon=Button.new();search_icon.text="⌕";search_icon.tooltip_text=_t("Поиск · ⌘F / Ctrl+F; поиск по проекту · ⇧⌘F / Ctrl+Shift+F","Search · ⌘F / Ctrl+F; search project · ⇧⌘F / Ctrl+Shift+F");search_icon.custom_minimum_size=Vector2(44,44);search_icon.add_theme_font_size_override("font_size",24);search_icon.pressed.connect(func():_open_code_search(false));activity.add_child(search_icon)
	var activity_spacer=Control.new();activity_spacer.size_flags_vertical=Control.SIZE_EXPAND_FILL;activity.add_child(activity_spacer)
	var explorer_split=HSplitContainer.new();explorer_split.size_flags_vertical=Control.SIZE_EXPAND_FILL;explorer_split.size_flags_horizontal=Control.SIZE_EXPAND_FILL;explorer_split.split_offset=205;explorer_split.dragger_visibility=SplitContainer.DRAGGER_VISIBLE;workspace.add_child(explorer_split)
	var explorer_panel=PanelContainer.new();explorer_panel.custom_minimum_size=Vector2(176,0);explorer_panel.add_theme_stylebox_override("panel",DesignSystem.panel_style(appearance));explorer_split.add_child(explorer_panel)
	code_explorer=VBoxContainer.new();code_explorer.add_theme_constant_override("separation",6);explorer_panel.add_child(code_explorer)
	var explorer_header=HBoxContainer.new();code_explorer.add_child(explorer_header)
	var explorer_title=Label.new();explorer_title.text=_t("ПРОВОДНИК","EXPLORER");explorer_title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;explorer_title.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));explorer_header.add_child(explorer_title)
	var files_header=Label.new();files_header.text=_t("ФАЙЛЫ ПРОЕКТА","PROJECT FILES");files_header.add_theme_font_size_override("font_size",13);files_header.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));code_explorer.add_child(files_header)
	for key in ["agent","reward"]:
		var file_item=Button.new();file_item.alignment=HORIZONTAL_ALIGNMENT_LEFT;file_item.custom_minimum_size.y=44;file_item.text="›  "+key+".py";file_item.tooltip_text="";file_item.pressed.connect(func():_switch_code(key));file_item.add_theme_stylebox_override("normal",DesignSystem.tab_style(appearance,key==active_code));file_item.add_theme_stylebox_override("hover",DesignSystem.tab_style(appearance,true));file_item.add_theme_color_override("font_color",DesignSystem.text_for(appearance));code_explorer.add_child(file_item);code_file_items[key]=file_item
	var editor_column=VBoxContainer.new();editor_column.size_flags_vertical=Control.SIZE_EXPAND_FILL;editor_column.size_flags_horizontal=Control.SIZE_EXPAND_FILL;editor_column.add_theme_constant_override("separation",0);explorer_split.add_child(editor_column)
	var breadcrumb_bar=HBoxContainer.new();breadcrumb_bar.custom_minimum_size.y=30;breadcrumb_bar.add_theme_constant_override("separation",6);editor_column.add_child(breadcrumb_bar)
	code_breadcrumb=Label.new();code_breadcrumb.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_breadcrumb.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));breadcrumb_bar.add_child(code_breadcrumb)
	code_search_layer=CanvasLayer.new();code_search_layer.layer=10;add_child(code_search_layer)
	code_search_popup=PanelContainer.new();code_search_popup.visible=false;code_search_popup.custom_minimum_size=Vector2(420,0);code_search_popup.z_index=100;code_search_popup.add_theme_stylebox_override("panel",DesignSystem.panel_style(appearance));code_search_layer.add_child(code_search_popup);code_search_popup.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	var search_popup_content=VBoxContainer.new();search_popup_content.add_theme_constant_override("separation",6);code_search_popup.add_child(search_popup_content)
	var search_popup_header=HBoxContainer.new();search_popup_content.add_child(search_popup_header)
	var search_popup_title=Label.new();search_popup_title.text=_t("ПОИСК","SEARCH");search_popup_title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;search_popup_header.add_child(search_popup_title)
	var close_search=Button.new();close_search.text="×";close_search.tooltip_text=_t("Закрыть · Esc","Close · Esc");close_search.pressed.connect(_close_code_search);search_popup_header.add_child(close_search)
	var search_mode_row=HBoxContainer.new();search_mode_row.add_theme_constant_override("separation",6);search_popup_content.add_child(search_mode_row)
	code_search_mode=OptionButton.new();code_search_mode.add_item(_t("В текущем файле","Current file"),0);code_search_mode.add_item(_t("В файлах проекта","Project files"),1);code_search_mode.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_search_mode.item_selected.connect(_on_code_search_mode_changed);search_mode_row.add_child(code_search_mode)
	code_find_input=LineEdit.new();code_find_input.placeholder_text=_t("Найти","Find");code_find_input.text_changed.connect(_on_code_search_query_changed);search_popup_content.add_child(code_find_input)
	var search_results_scroll=ScrollContainer.new();search_results_scroll.custom_minimum_size.y=96;search_results_scroll.size_flags_horizontal=Control.SIZE_EXPAND_FILL;search_popup_content.add_child(search_results_scroll)
	code_find_status=Label.new();code_find_status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;code_find_status.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_find_status.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));search_results_scroll.add_child(code_find_status)
	code_find_input.gui_input.connect(_on_find_input_key)
	code_search_popup.resized.connect(_schedule_code_search_position);editor_column.resized.connect(_schedule_code_search_position)
	editor_split=VSplitContainer.new();editor_split.size_flags_vertical=Control.SIZE_EXPAND_FILL;editor_split.size_flags_horizontal=Control.SIZE_EXPAND_FILL;editor_split.split_offset=390;editor_split.dragger_visibility=SplitContainer.DRAGGER_VISIBLE;editor_column.add_child(editor_split)
	code_editor=CodeEdit.new();code_editor.custom_minimum_size.y=130;code_editor.size_flags_vertical=Control.SIZE_EXPAND_FILL;code_editor.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_editor.gutters_draw_line_numbers=true;code_editor.gutters_draw_fold_gutter=true;code_editor.indent_automatic=true;code_editor.indent_use_spaces=true;code_editor.indent_size=4;code_editor.auto_brace_completion_enabled=true;code_editor.add_theme_color_override("font_color",DesignSystem.text_for(appearance));code_editor.add_theme_color_override("font_readonly_color",DesignSystem.muted_for(appearance));code_editor.add_theme_color_override("current_line_color",Color("edf1e7") if DesignSystem.is_light(appearance) else Color("293229"));code_editor.add_theme_color_override("line_number_color",Color("788273") if DesignSystem.is_light(appearance) else Color("8c9889"));code_editor.add_theme_color_override("caret_color",DesignSystem.accent_for(appearance));code_editor.add_theme_color_override("selection_color",Color("b8c9a5",0.48) if DesignSystem.is_light(appearance) else Color("829a6b",0.42));code_editor.add_theme_color_override("brace_mismatch_color",Color("df746a"));code_editor.add_theme_color_override("word_highlighted_color",Color("d8e4ce",0.18) if DesignSystem.is_light(appearance) else Color("bbd49c",0.14));code_editor.add_theme_constant_override("line_spacing",3)
	var mono=SystemFont.new();mono.font_names=PackedStringArray(["SF Mono","Menlo","Monaco","monospace"]);code_editor.add_theme_font_override("font",mono);code_editor.add_theme_font_size_override("font_size",17);editor_split.add_child(code_editor)
	code_editor.syntax_highlighter=_make_python_highlighter(appearance)
	code_editor.text_changed.connect(_on_code_changed);code_editor.caret_changed.connect(_update_code_cursor);code_editor.caret_changed.connect(_update_code_breadcrumb)
	var output_panel=VBoxContainer.new();output_panel.custom_minimum_size.y=84;output_panel.size_flags_vertical=Control.SIZE_EXPAND_FILL;output_panel.add_theme_constant_override("separation",4);editor_split.add_child(output_panel)
	var output_header=HBoxContainer.new();output_header.add_theme_constant_override("separation",6);output_panel.add_child(output_header)
	var output_title=Label.new();output_title.text=_t("Терминал","Terminal");output_title.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));output_title.size_flags_horizontal=Control.SIZE_EXPAND_FILL;output_header.add_child(output_title)
	terminal_environment_button=Button.new();terminal_environment_button.text=_t("Python: системный","Python: system");terminal_environment_button.tooltip_text=_t("Выбрать виртуальное окружение Python","Choose a Python virtual environment");terminal_environment_button.pressed.connect(_choose_terminal_environment);output_header.add_child(terminal_environment_button)
	var clear_output=Button.new();clear_output.text=_t("Очистить","Clear");clear_output.pressed.connect(func():code_console.clear());output_header.add_child(clear_output)
	terminal_stop_button=Button.new();terminal_stop_button.text=_t("Остановить","Stop");terminal_stop_button.visible=false;terminal_stop_button.pressed.connect(_stop_terminal_command);output_header.add_child(terminal_stop_button)
	var collapse_terminal=Button.new();collapse_terminal.text="⌄";collapse_terminal.tooltip_text=_t("Свернуть или развернуть терминал","Collapse or expand terminal");collapse_terminal.pressed.connect(func():editor_split.collapsed=not editor_split.collapsed);output_header.add_child(collapse_terminal)
	var terminal_path_row=HBoxContainer.new();terminal_path_row.add_theme_constant_override("separation",6);output_panel.add_child(terminal_path_row)
	terminal_cwd=_workspace_dir();terminal_cwd_input=LineEdit.new();terminal_cwd_input.text=terminal_cwd;terminal_cwd_input.placeholder_text=_t("Рабочая папка — введите путь или используйте «Обзор»","Working folder — enter a path or use Browse");terminal_cwd_input.tooltip_text=_t("Команды выполняются в этой папке","Commands run in this folder");terminal_cwd_input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;terminal_cwd_input.custom_minimum_size.x=160;terminal_cwd_input.text_submitted.connect(_set_terminal_cwd);terminal_path_row.add_child(terminal_cwd_input)
	var browse_cwd=Button.new();browse_cwd.text=_t("Обзор…","Browse…");browse_cwd.tooltip_text=_t("Выбрать папку на любом подключённом диске","Choose a folder on any mounted drive");browse_cwd.pressed.connect(_choose_terminal_cwd);terminal_path_row.add_child(browse_cwd)
	code_console=TextEdit.new();code_console.custom_minimum_size.y=52;code_console.size_flags_vertical=Control.SIZE_EXPAND_FILL;code_console.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_console.editable=false;code_console.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;code_console.placeholder_text=_t("Вывод команд, проверки и ошибок","Command output, checks, and errors");code_console.add_theme_color_override("font_color",Color("c8d1c4") if not DesignSystem.is_light(appearance) else Color("384237"));code_console.add_theme_color_override("font_readonly_color",Color("c8d1c4") if not DesignSystem.is_light(appearance) else Color("384237"));code_console.add_theme_color_override("caret_color",DesignSystem.muted_for(appearance));code_console.add_theme_stylebox_override("read_only",_code_panel_style(appearance));code_console.add_theme_font_override("font",mono);code_console.add_theme_font_size_override("font_size",14);output_panel.add_child(code_console)
	var terminal_input_row=HBoxContainer.new();terminal_input_row.add_theme_constant_override("separation",6);output_panel.add_child(terminal_input_row)
	var prompt=Label.new();prompt.text="❯";prompt.add_theme_color_override("font_color",DesignSystem.accent_for(appearance));terminal_input_row.add_child(prompt)
	terminal_command_input=LineEdit.new();terminal_command_input.placeholder_text=_t("Команда · например: python3 -m venv .venv","Command · for example: python3 -m venv .venv");terminal_command_input.tooltip_text=_t("После создания окружения выполните source .venv/bin/activate или выберите его кнопкой Python","After creating an environment, run source .venv/bin/activate or choose it with the Python button");terminal_command_input.size_flags_horizontal=Control.SIZE_EXPAND_FILL;terminal_command_input.text_submitted.connect(_run_terminal_command);terminal_input_row.add_child(terminal_command_input)
	var status_bar=HBoxContainer.new();status_bar.add_theme_constant_override("separation",18);panel.add_child(status_bar)
	code_status_label=Label.new();code_status_label.size_flags_horizontal=Control.SIZE_EXPAND_FILL;code_status_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(code_status_label)
	code_cursor_label=Label.new();code_cursor_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(code_cursor_label)
	var language_label=Label.new();language_label.text="Python · UTF-8 · Spaces: 4";language_label.add_theme_color_override("font_color",DesignSystem.muted_for(appearance));status_bar.add_child(language_label)
	loading_code=true;code_editor.text=FileAccess.get_file_as_string(student_agent_path);loading_code=false;_set_code_dirty(false);_update_code_cursor();_update_code_breadcrumb()

func _editor_toolbar_style(appearance:String)->StyleBoxFlat:
	var style=StyleBoxFlat.new();style.bg_color=DesignSystem.surface_for(appearance);style.border_color=Color("c5c8bd") if DesignSystem.is_light(appearance) else Color("465044");style.set_border_width_all(1);style.set_corner_radius_all(10);style.content_margin_left=7;style.content_margin_right=7;style.content_margin_top=4;style.content_margin_bottom=4;return style

func _search_code_files(query:String):
	if not is_instance_valid(code_find_status):return
	var q=query.strip_edges().to_lower()
	if q=="":code_find_status.text="";return
	var matches=[]
	for key in ["agent","reward"]:
		var lines=FileAccess.get_file_as_string(_code_path_for(key)).split("\n")
		for index in range(lines.size()):
			if String(lines[index]).to_lower().contains(q):matches.append("%s.py:%d  %s" % [key,index+1,String(lines[index]).strip_edges()])
	code_find_status.text="\n".join(matches.slice(0,24)) if not matches.is_empty() else _t("Совпадений нет","No matches")
	if matches.size()>24:code_find_status.text+="\n… %d %s" % [matches.size()-24,_t("ещё совпадений","more matches")]

func _open_code_search(project_wide:bool):
	if not is_instance_valid(code_search_popup):return
	code_search_mode.select(1 if project_wide else 0)
	code_find_input.clear()
	code_find_status.text=""
	code_find_last_query=""
	code_find_last_match=-1
	code_search_popup.visible=true
	call_deferred("_position_code_search_popup")
	code_find_input.grab_focus()

func _close_code_search():
	code_search_popup.visible=false
	if is_instance_valid(code_editor):code_editor.grab_focus()

func _position_code_search_popup():
	if not is_instance_valid(code_search_popup) or not is_instance_valid(code_editor):return
	var viewport_size=get_viewport_rect().size
	var popup_size=code_search_popup.get_combined_minimum_size()
	popup_size.x=minf(420.0,maxf(300.0,viewport_size.x-32.0))
	popup_size.y=minf(popup_size.y,maxf(220.0,viewport_size.y-32.0))
	code_search_popup.size=popup_size
	var editor_rect=code_editor.get_global_rect()
	var target=Vector2(editor_rect.end.x-popup_size.x-8.0,editor_rect.position.y+8.0)
	target.x=clampf(target.x,8.0,maxf(8.0,viewport_size.x-popup_size.x-8.0))
	target.y=clampf(target.y,8.0,maxf(8.0,viewport_size.y-popup_size.y-8.0))
	code_search_popup.position=target

func _schedule_code_search_position():
	if code_search_popup.visible:call_deferred("_position_code_search_popup")

func _on_code_search_mode_changed(index:int):
	code_find_input.placeholder_text=_t("Найти в agent.py и reward.py","Search agent.py and reward.py") if index==1 else _t("Найти в текущем файле","Find in current file")
	code_find_status.text=""
	code_find_last_query=""
	code_find_last_match=-1
	if not code_find_input.text.is_empty():_on_code_search_query_changed(code_find_input.text)

func _on_code_search_query_changed(query:String):
	code_find_status.text=""
	code_find_last_query=""
	code_find_last_match=-1
	if code_search_mode.selected==1:_search_code_files(query)
	else:_find_in_current_file(false)

func _code_path_for(key:String)->String:return student_agent_path if key=="agent" else student_reward_path

func _update_code_breadcrumb():
	if not is_instance_valid(code_editor) or not is_instance_valid(code_breadcrumb):return
	var lines=code_editor.text.split("\n")
	var line=min(code_editor.get_caret_line(),lines.size()-1)
	var symbol=""
	for index in range(line,-1,-1):
		var candidate=String(lines[index]).strip_edges()
		if candidate.begins_with("def ") or candidate.begins_with("class "):
			symbol=candidate.trim_suffix(":");break
	var guidance=_t("управление · act(...) → 6 значений","policy · act(...) → 6 values") if active_code=="agent" else _t("награда · calculate_reward(...) → одно число","reward · calculate_reward(...) → one number")
	code_breadcrumb.text=active_code+".py"+("  ›  "+symbol if symbol!="" else "")+"   ·   "+guidance

func _on_editor_menu_action(id:int):
	match id:
		1:_import_python()
		2:_restore_template()
		3:
			_save_current_code()
			AppState.run_marl_job("export",["--workspace",_workspace_dir(),"--sessions-root",AppState.results_root().path_join("marl")])

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
	var sidebar_item=code_file_items.get(active_code)
	if is_instance_valid(sidebar_item):sidebar_item.text=("›  " if not dirty else "● ")+active_code+".py";sidebar_item.add_theme_stylebox_override("normal",DesignSystem.tab_style(str(AppState.settings.get("appearance","dark")),true))
	for key in code_file_items:
		var item=code_file_items.get(key)
		if is_instance_valid(item) and key!=active_code:item.text="   "+key+".py";item.add_theme_stylebox_override("normal",DesignSystem.tab_style(str(AppState.settings.get("appearance","dark")),false))
	if is_instance_valid(code_status_label):code_status_label.text=_t("Не сохранено","Unsaved changes") if dirty else _t("Сохранено","Saved")

func _update_code_cursor():
	if not is_instance_valid(code_editor) or not is_instance_valid(code_cursor_label):return
	code_cursor_label.text="Ln %d, Col %d" % [code_editor.get_caret_line()+1,code_editor.get_caret_column()+1]

func _unhandled_key_input(event:InputEvent):
	if not event is InputEventKey or not event.pressed or event.echo or not is_instance_valid(code_editor):return
	var key=event as InputEventKey
	if not code_editor.is_visible_in_tree():return
	var command_modifier=key.ctrl_pressed or key.meta_pressed
	if key.keycode==KEY_S and command_modifier:
		_save_current_code();get_viewport().set_input_as_handled()
	elif key.keycode==KEY_F and command_modifier and not key.shift_pressed:
		_open_code_search(false);get_viewport().set_input_as_handled()
	elif key.keycode==KEY_F and command_modifier and key.shift_pressed:
		_open_code_search(true);get_viewport().set_input_as_handled()
	elif key.keycode==KEY_F5:
		_confirm_student_run("student");get_viewport().set_input_as_handled()
	elif key.keycode==KEY_ESCAPE and code_search_popup.visible:
		_close_code_search();get_viewport().set_input_as_handled()

func _on_find_input_key(event:InputEvent):
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_ENTER:
			if code_search_mode.selected==1:_search_code_files(code_find_input.text)
			else:_find_in_current_file(event.shift_pressed)
			get_viewport().set_input_as_handled()
		elif event.keycode==KEY_ESCAPE:
			_close_code_search();get_viewport().set_input_as_handled()

func _process(delta:float):
	if terminal_pid<=0:return
	terminal_poll_elapsed+=delta
	if terminal_poll_elapsed<.2:return
	terminal_poll_elapsed=0.0
	var live_output=FileAccess.get_file_as_string(terminal_output_path) if FileAccess.file_exists(terminal_output_path) else ""
	if live_output!=terminal_last_output:
		terminal_last_output=live_output
		code_console.text=terminal_console_prefix+live_output
		code_console.scroll_vertical=code_console.get_line_count()
	if not OS.is_process_running(terminal_pid):
		terminal_pid=-1
		terminal_stop_button.visible=false
		terminal_command_input.editable=true
		var exit_code=FileAccess.get_file_as_string(terminal_status_path) if FileAccess.file_exists(terminal_status_path) else "?"
		code_console.text=terminal_console_prefix+live_output+"\n[exit %s]" % exit_code
		code_console.scroll_vertical=code_console.get_line_count()

func _exit_tree():
	if terminal_pid>0 and OS.is_process_running(terminal_pid):OS.kill(terminal_pid)

func _terminal_note(message:String):
	console_mode="terminal"
	code_console.text+=message+"\n"
	code_console.scroll_vertical=code_console.get_line_count()

func _shell_quote(value:String)->String:
	return "'"+value.replace("'","'\\''")+"'"

func _set_terminal_cwd(value:String):
	var target=value.strip_edges().trim_prefix("\"").trim_suffix("\"").trim_prefix("'").trim_suffix("'")
	if target=="":return
	if target=="~":target=OS.get_environment("HOME")
	elif target.begins_with("~/"):target=OS.get_environment("HOME").path_join(target.substr(2))
	elif not target.is_absolute_path():target=terminal_cwd.path_join(target)
	target=target.simplify_path()
	if not DirAccess.dir_exists_absolute(target):_terminal_note(_t("Папка не найдена: ","Folder not found: ")+target);return
	terminal_cwd=target
	terminal_cwd_input.text=target
	_terminal_note("%s %s" % [_t("Рабочая папка:","Working directory:"),terminal_cwd])

func _choose_terminal_cwd():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_DIR;dialog.current_dir=terminal_cwd;add_child(dialog)
	dialog.dir_selected.connect(func(path):_set_terminal_cwd(path);dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.8)

func _choose_terminal_environment():
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.file_mode=FileDialog.FILE_MODE_OPEN_DIR;dialog.current_dir=terminal_cwd;add_child(dialog)
	dialog.dir_selected.connect(func(path):_activate_terminal_environment(path);dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.8)

func _activate_terminal_environment(path:String):
	var candidate=path.strip_edges().trim_suffix("/bin").trim_suffix("/Scripts")
	var python_path=candidate.path_join("Scripts/python.exe") if OS.get_name()=="Windows" else candidate.path_join("bin/python")
	if not FileAccess.file_exists(python_path):
		_terminal_note(_t("В папке не найден Python виртуального окружения.","No virtual-environment Python was found in that folder."));return
	terminal_venv=candidate.simplify_path()
	terminal_environment_button.text="Python: "+terminal_venv.get_file()
	terminal_environment_button.tooltip_text=terminal_venv
	_terminal_note(_t("Активировано окружение: ","Activated environment: ")+terminal_venv)

func _terminal_activate_from_command(path:String)->bool:
	var target=path.strip_edges().trim_prefix("\"").trim_suffix("\"").trim_prefix("'").trim_suffix("'")
	if not target.is_absolute_path():target=terminal_cwd.path_join(target)
	target=target.simplify_path()
	if target.ends_with("/activate") or target.ends_with("/activate.fish") or target.ends_with("/Activate.ps1") or target.ends_with("/activate.bat"):
		var environment=target.get_base_dir().get_base_dir()
		_activate_terminal_environment(environment)
		return true
	return false

func _run_terminal_command(command:String):
	var text=command.strip_edges()
	terminal_command_input.clear()
	if text=="":return
	if terminal_pid>0 and OS.is_process_running(terminal_pid):
		_terminal_note(_t("Дождитесь завершения текущей команды.","Wait for the current command to finish."));return
	console_mode="terminal"
	if text=="clear":code_console.clear();return
	if text=="pwd":_terminal_note(terminal_cwd);return
	if text=="deactivate":terminal_venv="";terminal_environment_button.text=_t("Python: системный","Python: system");terminal_environment_button.tooltip_text=_t("Выбрать виртуальное окружение","Choose virtual environment");_terminal_note(_t("Виртуальное окружение отключено.","Virtual environment deactivated."));return
	if text.begins_with("cd ") or text=="cd":_set_terminal_cwd(text.substr(2).strip_edges() if text.length()>2 else OS.get_environment("HOME"));return
	if text.begins_with("use-venv "):_activate_terminal_environment(text.substr(9).strip_edges());return
	if text.begins_with("source ") or text.begins_with(". "):
		var source_path=text.substr(7).strip_edges() if text.begins_with("source ") else text.substr(2).strip_edges()
		if _terminal_activate_from_command(source_path):return
	terminal_console_prefix=code_console.text
	if terminal_console_prefix!="" and not terminal_console_prefix.ends_with("\n"):terminal_console_prefix+="\n"
	terminal_console_prefix+="%s %s\n" % [terminal_cwd.get_file()+" $",text]
	terminal_last_output=""
	var terminal_root=OS.get_user_data_dir().path_join("marl_terminal")
	DirAccess.make_dir_recursive_absolute(terminal_root)
	var stamp=str(Time.get_ticks_usec())
	terminal_output_path=terminal_root.path_join(stamp+".log")
	terminal_status_path=terminal_root.path_join(stamp+".exit")
	var shell_script=""
	var shell=""
	var args=PackedStringArray()
	if OS.get_name()=="Windows":
		shell="powershell.exe"
		shell_script="Set-Location -LiteralPath "+_powershell_quote(terminal_cwd)+"; "
		if terminal_venv!="":
			var environment_bin=terminal_venv.path_join("Scripts")
			shell_script+="$env:VIRTUAL_ENV="+_powershell_quote(terminal_venv)+"; $env:Path="+_powershell_quote(environment_bin)+"+';'+$env:Path; "
		shell_script+="& { "+text+" } *> "+_powershell_quote(terminal_output_path)+"; $flyswarm_exit=$LASTEXITCODE; Set-Content -NoNewline -LiteralPath "+_powershell_quote(terminal_status_path)+" -Value $flyswarm_exit"
		args=PackedStringArray(["-NoProfile","-Command",shell_script])
	else:
		shell="/bin/zsh"
		shell_script="cd "+_shell_quote(terminal_cwd)+" || exit 127; "
		if terminal_venv!="":
			var environment_bin=terminal_venv.path_join("bin")
			shell_script+="export VIRTUAL_ENV="+_shell_quote(terminal_venv)+"; export PATH="+_shell_quote(environment_bin)+":$PATH; "
		shell_script+="("+text+") > "+_shell_quote(terminal_output_path)+" 2>&1; flyswarm_exit=$?; printf '%s' \"$flyswarm_exit\" > "+_shell_quote(terminal_status_path)
		args=PackedStringArray(["-lc",shell_script])
	terminal_pid=OS.create_process(shell,args)
	if terminal_pid<=0:
		terminal_pid=-1
		_terminal_note(_t("Не удалось запустить команду.","Could not start the command."));return
	terminal_stop_button.visible=true
	terminal_command_input.editable=false
	code_console.text=terminal_console_prefix+_t("Выполняется…\n","Running…\n")
	code_console.scroll_vertical=code_console.get_line_count()

func _stop_terminal_command():
	if terminal_pid>0 and OS.is_process_running(terminal_pid):
		if OS.get_name()!="Windows":OS.execute("/usr/bin/pkill",["-TERM","-P",str(terminal_pid)])
		OS.kill(terminal_pid)
	terminal_pid=-1
	terminal_stop_button.visible=false
	terminal_command_input.editable=true
	_terminal_note(_t("Команда остановлена.","Command stopped."))

func _powershell_quote(value:String)->String:
	return "'"+value.replace("'","''")+"'"

func _find_in_current_file(backwards:bool):
	if not is_instance_valid(code_editor) or not is_instance_valid(code_find_input):return
	var query=code_find_input.text
	if query.is_empty():code_find_status.text="";return
	var source=code_editor.text
	if query!=code_find_last_query:code_find_last_query=query;code_find_last_match=-1
	var start_offset=code_find_last_match if backwards else code_find_last_match+query.length()
	if code_find_last_match<0:
		for line_index in range(code_editor.get_caret_line()):start_offset+=code_editor.get_line(line_index).length()+1
		start_offset+=code_editor.get_caret_column()
	var match_offset=source.rfind(query,start_offset-1) if backwards else source.find(query,start_offset)
	if match_offset<0:match_offset=source.rfind(query) if backwards else source.find(query)
	if match_offset<0:code_find_status.text=_t("Нет совпадений","No match");return
	code_find_last_match=match_offset
	var before=source.substr(0,match_offset).split("\n")
	var line_index=before.size()-1
	var column=before[before.size()-1].length()
	code_editor.set_caret_line(line_index);code_editor.set_caret_column(column);code_editor.select(line_index,column,line_index,column+query.length());code_editor.center_viewport_to_caret()
	var total=source.count(query);var current=1;var count_offset=0
	while count_offset<match_offset:
		var next_match=source.find(query,count_offset)
		if next_match<0 or next_match>=match_offset:break
		current+=1;count_offset=next_match+query.length()
	code_find_status.text="%d/%d" % [current,total]
func _active_code_path()->String:return student_agent_path if active_code=="agent" else student_reward_path
func _switch_code(next:String):
	if is_instance_valid(code_editor):_save_current_code()
	active_code=next
	if is_instance_valid(code_find_input):code_find_input.clear()
	if is_instance_valid(code_find_status):code_find_status.text=""
	if is_instance_valid(code_editor):
		loading_code=true;code_editor.text=FileAccess.get_file_as_string(_active_code_path()) if FileAccess.file_exists(_active_code_path()) else "";loading_code=false
		_set_code_dirty(false);_update_code_cursor();_update_code_breadcrumb()
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
	if command=="student":args.append_array(["--episodes","3","--seed",str(seed_value),"--max-steps",str(episode_steps),"--tier",training_tier])
	AppState.run_marl_job(command,args)
func _confirm_python_job(command:String,args:Array):
	var title=_t("Запустить обучение с reward.py?","Start training with reward.py?")
	var details=_t("Будет обучена PPO-политика на %s шагах с seed %s. Политика MaleCNS останется без изменений.","A PPO policy will train for %s steps with seed %s. The MaleCNS policy will remain unchanged.") % [str(training_steps),str(seed_value)]
	if command=="compare-all":
		title=_t("Сравнить четыре стратегии?","Compare four strategies?")
		details=_t("Random, agent.py, стандартный PPO и PPO с reward.py будут проверены на одинаковых seed.","Random, agent.py, standard PPO, and PPO with reward.py will use the same evaluation seeds.")
	var consent=ConfirmationDialog.new();consent.title=title;consent.dialog_text=details;add_child(consent);consent.get_ok_button().text=_t("Начать","Start")
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
	AppState.run_marl_job(command,[checkpoint_path,"--episodes","3","--seed",str(seed_value+1000),"--max-steps",str(episode_steps),"--tier",training_tier])
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
	if state=="starting":console_mode="jobs"
	if is_instance_valid(code_stop_button):code_stop_button.visible=state in ["starting","initializing","training","finalizing"]
	var labels={
		"ready":_t("Готово к запуску","Ready to start"),
		"starting":_t("Запуск Python…","Starting Python…"),
		"initializing":_t("Подготовка модели…","Preparing model…"),
		"training":_t("Обучение PPO…","Training PPO…"),
		"paused":_t("Пауза · checkpoint сохранён","Paused · checkpoint saved"),
		"finalizing":_t("Сохранение результатов…","Saving results…"),
		"complete":_t("Готово","Complete"),
		"error":_t("Ошибка","Error"),
		"cancelled":_t("Остановлено","Cancelled"),
	}
	status_label.text=str(labels.get(state,state.capitalize()))
	var current=float(progress.get("timesteps",progress.get("completed",0)))
	var target=float(progress.get("target_timesteps",progress.get("total",0)))
	if target>0.0 and current>target:target=current
	var terminal=state in ["complete","error","cancelled"]
	status_progress.visible=state!="ready"
	status_progress.indeterminate=not terminal and (target<=0.0 or state in ["starting","initializing","finalizing"])
	status_progress.max_value=maxf(1.0,target)
	status_progress.value=target if state=="complete" else current
	var lines=[]
	var progress_message=str(progress.get("message",""))
	var known_messages={
		"Starting the Python experiment worker…":_t("Запускаю процесс Python…","Starting Python worker…"),
		"Loading Stable-Baselines3 and preparing the PPO model.":_t("Загружаю PPO и готовлю модель.","Loading PPO and preparing the model."),
		"Preparing the training environment.":_t("Подготавливаю среду обучения.","Preparing the training environment."),
		"Constructing the PPO policy network.":_t("Создаю сеть политики PPO.","Creating the PPO policy network."),
		"PPO rollouts are running.":_t("Идут шаги обучения PPO.","PPO rollouts are running."),
		"Training finished; saving checkpoint and learning curve.":_t("Обучение завершено; сохраняю модель и график.","Training finished; saving model and chart."),
		"Training and checkpoint are ready.":_t("Обучение завершено, модель сохранена.","Training and checkpoint are ready."),
	}
	if known_messages.has(progress_message):progress_message=known_messages[progress_message]
	if progress_message!="":lines.append(progress_message)
	var phase=str(progress.get("phase",""))
	if phase!="":lines.append("%s: %s" % [_t("Этап","Phase"),phase])
	for key in ["timesteps","target_timesteps","episodes","steps_per_second","elapsed_seconds","eta_seconds","latest_episode_reward"]:
		if progress.has(key):lines.append("%s: %s" % [key,str(progress[key])])
	var metrics=progress.get("ppo_metrics",{})
	if metrics is Dictionary and not metrics.is_empty():
		lines.append("PPO: "+", ".join(PackedStringArray(["%s=%s" % [key,str(metrics[key])] for key in metrics])))
	var reward_totals=progress.get("reward_component_totals",{})
	if reward_totals is Dictionary and not reward_totals.is_empty():
		lines.append(_t("Компоненты награды","Reward components")+": "+", ".join(PackedStringArray(["%s=%s" % [key,str(reward_totals[key])] for key in reward_totals])))
	if output_path!="":lines.append("\n"+output_path)
	detail_label.text="\n".join(lines)
	if is_instance_valid(code_console) and console_mode=="jobs":
		var log_path=output_path.path_join("execution.log") if output_path!="" else ""
		var log_text=FileAccess.get_file_as_string(log_path) if log_path!="" and FileAccess.file_exists(log_path) else ""
		var message=str(progress.get("message",""))
		code_console.text=log_text if log_text!="" else message
		code_console.scroll_vertical=code_console.get_line_count()
