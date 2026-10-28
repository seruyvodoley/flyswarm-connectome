extends Control
const DesignSystem = preload("res://scripts/app/design_system.gd")
@export var page="OpenDayMain"
const FlyPreview=preload("res://scripts/app/fly_preview.gd")
const VehiclePreview=preload("res://scripts/app/vehicle_preview.gd")
const OpenDayController=preload("res://scripts/app/open_day_controller.gd")
var selected_vehicle="t34_85"
var attract_elapsed=0.0
var attract_active=false
var attract_label: Label
var vehicle_preview: SubViewportContainer
var vehicle_buttons: Dictionary={}
var selected_vehicle_label: Label
var opponent_picker: OptionButton
var policy_status_label: Label
var attract_phase=0
var attract_clock=0.0

const RU_COPY={
	"OPEN DAY":"ДЕНЬ ОТКРЫТЫХ ДВЕРЕЙ","FLYSWARM":"FLYSWARM","A fly controls a tank.":"Муха управляет танком.",
	"Fight a reconstructed model of the Drosophila nervous system.":"Сразись с реконструированной моделью нервной системы дрозофилы.",
	"QUICK BATTLE: VISITOR VS FLY":"БЫСТРЫЙ БОЙ: ТЫ ПРОТИВ МУХИ","AUTONOMOUS BATTLE":"АВТОНОМНЫЙ БОЙ",
	"HOW IT WORKS":"КАК ЭТО РАБОТАЕТ","TEST RANGE":"ПОЛИГОН","REPLAYS":"ПОВТОРЫ","SETTINGS":"НАСТРОЙКИ",
	"This is Drosophila.":"Это дрозофила.","We use a reconstructed model of its nervous system to control an agent in a virtual environment.":"Реконструированная модель её нервной системы управляет агентом в виртуальном мире.",
	"We use a reconstructed nervous system model to control an agent in a virtual world.":"Реконструированная модель нервной системы управляет агентом в виртуальном мире.",
	"CHOOSE YOUR VEHICLE":"ВЫБЕРИ ТАНК","WHY A FLY?":"ПОЧЕМУ МУХА?","EYES":"ЗРИТЕЛЬНЫЕ СИГНАЛЫ",
	"IS-2 (44)":"ИС-2 (обр. 1944)","SU-100":"СУ-100",
	"DROSOPHILA · 3D VIEW":"ДРОЗОФИЛА · 3D-ПРОСМОТР","VEHICLE · 3D VIEW":"ТЕХНИКА · 3D-ПРОСМОТР",
	"DRAG TO INSPECT · DOUBLE-CLICK TO RESET":"ПЕРЕТАСКИВАЙ ДЛЯ ОСМОТРА · ДВОЙНОЙ ЩЕЛЧОК — СБРОС",
	"Visual signals enter the reconstructed sensory pathways.":"Зрительные сигналы поступают в реконструированные сенсорные пути.","NERVOUS SYSTEM":"НЕРВНАЯ СИСТЕМА",
	"The fixed MaleCNS model processes those signals.":"Зафиксированная модель MaleCNS обрабатывает сигналы.","MOVEMENT":"УПРАВЛЕНИЕ",
	"Descending-neuron signals pass through an external engineered motor adapter.":"Сигналы нисходящих нейронов преобразует внешний инженерный адаптер.","START DEMO":"НАЧАТЬ ДЕМО","RESEARCH INTERFACE":"ИССЛЕДОВАТЕЛЬСКИЙ РЕЖИМ",
	"HOW DOES THE FLY CONTROL A TANK?":"КАК МУХА УПРАВЛЯЕТ ТАНКОМ?","1. FLY":"1. МУХА","Sensory signals from the virtual world":"Сенсорные сигналы из виртуального мира",
	"2. BIOLOGICAL MODEL":"2. БИОЛОГИЧЕСКАЯ МОДЕЛЬ","FIXED MALECNS":"ЗАФИКСИРОВАННАЯ MALECNS",
	"Reconstructed connectome\nDNp09 · DNa02 · DNp01 · wing/song":"Реконструированный коннектом\nDNp09 · DNa02 · DNp01 · wing/song",
	"The connectome is frozen and does not understand tanks, objectives or tactics.":"Коннектом зафиксирован: он не понимает танки, цели или тактику.","3. ENGINEERED ADAPTER":"3. ИНЖЕНЕРНЫЙ АДАПТЕР","SIGNALS → CONTROLS":"СИГНАЛЫ → КОМАНДЫ",
	"motor decoder\nmovement auxiliary\naiming and firing helper":"декодер движений\nвспомогательное управление\nпомощь в наведении и стрельбе",
	"This external layer converts neural activity into safe vehicle controls.":"Внешний слой преобразует активность нейронов в команды управления техникой.","motor decoder · movement auxiliary\naiming and firing helper":"декодер движений · помощь в манёвре\nнаведении и стрельбе","movement · turning · aiming · firing":"движение · поворот · наведение · стрельба","4. VIRTUAL VEHICLE":"4. ВИРТУАЛЬНЫЙ ТАНК",
	"movement\nturning\naiming\nfiring":"движение\nповорот\nнаведение\nвыстрел","The existing FlySwarm physics, armour and ballistics remain active.":"Физика FlySwarm, броня и баллистика остаются активны.","BACK":"НАЗАД",
	"YOU DEFEATED THE FLY":"ТЫ ПОБЕДИЛ МУХУ","THE FLY WON":"МУХА ПОБЕДИЛА","DRAW":"НИЧЬЯ","Neither vehicle was destroyed; no winner was awarded.":"Ни одна машина не уничтожена; победитель не определён.","Yes. A reconstructed model of the Drosophila nervous system just won this round.":"Да. Реконструированная модель нервной системы дрозофилы выиграла этот раунд.",
	"Time: %.1f s   ·   shots: %d   ·   penetrating hits: %d":"Время: %.1f с   ·   выстрелы: %d   ·   пробития: %d","MaleCNS + external engineered motor/tactical layer":"MaleCNS + внешний инженерный адаптер управления",
	"PLAY AGAIN":"ЕЩЁ РАЗ","OPEN DAY MENU":"В МЕНЮ ДЕМО","A FLY CONTROLS A TANK":"МУХА УПРАВЛЯЕТ ТАНКОМ","REAL MALECNS ACTIVITY":"АКТИВНОСТЬ МОДЕЛИ MALECNS","CAN YOU DEFEAT THE FLY?\nCLICK TO FIGHT":"СМОЖЕШЬ ПОБЕДИТЬ МУХУ?\nНАЖМИ, ЧТОБЫ СРАЗИТЬСЯ",
	"OPPONENT POLICY":"ПОЛИТИКА ПРОТИВНИКА","MaleCNS Baseline":"MALECNS · БАЗОВАЯ","MaleCNS + Trained PPO":"MALECNS + ОБУЧЕННАЯ PPO",
	"Choose deployment policy…":"ВЫБРАТЬ ПОЛИТИКУ…","Baseline: real MaleCNS with the existing Open Day controller.":"Базовый режим: MaleCNS и текущий контроллер Open Day.",
	"Choose an evaluated MaleCNS deployment ZIP.":"Выберите оценённую политику MaleCNS для Open Day.","Policy metadata is missing.":"Не найдены метаданные политики.",
	"Policy schema, MaleCNS mode, evaluation or checksum is invalid.":"Схема, режим MaleCNS, оценка или контрольная сумма не прошли проверку."
}

func _ready():
	OpenDayController.configure()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var appearance=str(AppState.settings.get("appearance","dark"))
	theme=DesignSystem.make_theme(18,appearance)
	var bg=ColorRect.new();bg.color=DesignSystem.ink_for(appearance);bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,28)
	add_child(margin)
	var root=VBoxContainer.new();root.add_theme_constant_override("separation",14);margin.add_child(root)
	var top=HBoxContainer.new();root.add_child(top)
	var brand=label(top,"F / S   FLYSWARM",18);brand.size_flags_horizontal=Control.SIZE_EXPAND_FILL;brand.autowrap_mode=TextServer.AUTOWRAP_OFF
	var badge=label(top,"OPEN DAY · MALECNS",14);badge.modulate=Color("c1a573");badge.autowrap_mode=TextServer.AUTOWRAP_OFF;badge.custom_minimum_size.x=190
	root.add_child(HSeparator.new())
	match page:
		"OpenDayMain":build_main(root)
		"HowItWorks":build_how(root)
		"DemoResult":build_result(root)
	call_deferred("focus_first_controller_button")

func label(parent: Node,text: String,size=18) -> Label:
	var value=Label.new();value.text=copy_text(text);value.add_theme_font_size_override("font_size",size);value.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;parent.add_child(value);return value
func button(parent: Node,text: String,callback: Callable) -> Button:
	var value=Button.new();value.text=copy_text(text);value.name=text.to_pascal_case();value.custom_minimum_size.y=48;value.pressed.connect(callback);parent.add_child(value);return value
func copy_text(text: String) -> String:
	if str(AppState.settings.language)=="ru":return str(RU_COPY.get(text,AppState.tr_text(text)))
	return AppState.tr_text(text)
func _choose_open_day_policy() -> void:
	var dialog=FileDialog.new();dialog.access=FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE
	dialog.filters=PackedStringArray(["*.zip ; Evaluated FlySwarm PPO deployment"])
	add_child(dialog)
	dialog.file_selected.connect(func(path):
		AppState.open_day_policy_path=path
		_update_policy_status()
		dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free)
	dialog.popup_centered_ratio(.75)

func _update_policy_status() -> void:
	if not is_instance_valid(policy_status_label):return
	if AppState.open_day_policy_mode!="trained":
		policy_status_label.text=copy_text("Baseline: real MaleCNS with the existing Open Day controller.")
		return
	var path=AppState.open_day_policy_path
	if path=="" or not FileAccess.file_exists(path):
		policy_status_label.text=copy_text("Choose an evaluated MaleCNS deployment ZIP.")
		return
	var sidecar=path.get_base_dir().path_join("metadata.json")
	if not FileAccess.file_exists(sidecar):
		policy_status_label.text=copy_text("Policy metadata is missing.")
		return
	var file=FileAccess.open(sidecar,FileAccess.READ)
	var metadata=JSON.parse_string(file.get_as_text()) if file else null
	var valid=metadata is Dictionary and metadata.get("schema")=="flyswarm_malecns_combat_v2" and metadata.get("male_cns_required",false) and metadata.get("independent_evaluation")=="passed_independent_analytic_evaluation" and metadata.get("sha256",metadata.get("checkpoint_sha256",""))==FileAccess.get_sha256(path)
	policy_status_label.text=(copy_text("Ready · ")+path.get_file()) if valid else copy_text("Policy schema, MaleCNS mode, evaluation or checksum is invalid.")
	policy_status_label.add_theme_color_override("font_color",Color("aebe9a") if valid else Color("e18f82"))
	if valid:
		AppState.settings.open_day_policy_mode="trained"
		AppState.settings.open_day_policy_path=path
		AppState.save_settings()
func panel(parent: Node) -> VBoxContainer:
	var frame=PanelContainer.new();frame.size_flags_vertical=Control.SIZE_EXPAND_FILL;frame.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	frame.add_theme_stylebox_override("panel",DesignSystem.panel_style(str(AppState.settings.get("appearance","dark"))));parent.add_child(frame)
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",12);frame.add_child(box);return box
func preview(parent: Node,min_size=Vector2(480,340)):
	var fly=FlyPreview.new();fly.custom_minimum_size=min_size;fly.size_flags_vertical=Control.SIZE_EXPAND_FILL;fly.size_flags_horizontal=Control.SIZE_EXPAND_FILL;parent.add_child(fly);return fly

func preview_stage(parent: Node, title: String, preview_script: Script, min_size: Vector2, vehicle_id := "") -> Control:
	var appearance := str(AppState.settings.get("appearance", "dark"))
	var frame := PanelContainer.new()
	frame.name = title.to_pascal_case().replace(" ", "") + "PreviewFrame"
	frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	frame.size_flags_vertical = Control.SIZE_EXPAND_FILL
	frame.size_flags_stretch_ratio = 1.0
	frame.add_theme_stylebox_override("panel", DesignSystem.preview_frame_style(appearance))
	parent.add_child(frame)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 3)
	frame.add_child(content)
	var heading := HBoxContainer.new()
	content.add_child(heading)
	var title_label := label(heading, title, 10)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_label.add_theme_color_override("font_color", DesignSystem.text_for(appearance))
	var instructions := label(heading, "DRAG TO INSPECT · DOUBLE-CLICK TO RESET", 8)
	instructions.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	instructions.autowrap_mode = TextServer.AUTOWRAP_OFF
	instructions.add_theme_color_override("font_color", DesignSystem.muted_for(appearance))
	var model = preview_script.new()
	model.custom_minimum_size = min_size
	model.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	model.size_flags_vertical = Control.SIZE_EXPAND_FILL
	if not vehicle_id.is_empty():
		model.vehicle_id = vehicle_id
	content.add_child(model)
	return model

func build_main(root: VBoxContainer):
	var columns=HBoxContainer.new();columns.size_flags_vertical=Control.SIZE_EXPAND_FILL;columns.add_theme_constant_override("separation",18);root.add_child(columns)
	columns.name="OpenDayColumns"
	var left=panel(columns);left.name="OpenDayLeft";left.custom_minimum_size.x=300;left.size_flags_stretch_ratio=0.80
	label(left,"OPEN DAY",14).modulate=Color("c1a573");label(left,"FLYSWARM",44);label(left,"A fly controls a tank.",31);label(left,"Fight a reconstructed model of the Drosophila nervous system.",16).modulate=Color("aebcb4")
	var start=button(left,"QUICK BATTLE: VISITOR VS FLY",func():AppState.start_demo(selected_vehicle));start.custom_minimum_size.y=72
	button(left,"AUTONOMOUS BATTLE",func():AppState.configure("battle"))
	button(left,"HOW IT WORKS",AppState.show_page.bind("HowItWorks"))
	button(left,"TEST RANGE",func():AppState.configure("range"))
	button(left,"REPLAYS",AppState.show_page.bind("ReplayBrowser"))
	button(left,"SETTINGS",AppState.show_page.bind("Settings"))
	var center=panel(columns);center.name="OpenDayCenter";center.custom_minimum_size.x=570;center.size_flags_stretch_ratio=1.50
	center.add_theme_constant_override("separation", 6)
	preview_stage(center,"DROSOPHILA · 3D VIEW",FlyPreview,Vector2(400,155))
	var selection=VBoxContainer.new();selection.name="OpenDaySelectionControl";selection.size_flags_horizontal=Control.SIZE_EXPAND_FILL;selection.add_theme_constant_override("separation",6);center.add_child(selection)
	var fly_caption=label(selection,"This is Drosophila.",20);fly_caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var summary=label(selection,"We use a reconstructed nervous system model to control an agent in a virtual world.",14);summary.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;summary.modulate=Color("aebcb4")
	var choose_caption=label(selection,"CHOOSE YOUR VEHICLE",13);choose_caption.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;choose_caption.modulate=Color("c1a573")
	var choices=GridContainer.new();choices.columns=3;choices.add_theme_constant_override("h_separation",6);choices.add_theme_constant_override("v_separation",4);selection.add_child(choices)
	for choice in [["T-34-85","t34_85"],["IS-2 (44)","is2_1944"],["PANTHER G","panther_g"],["TIGER I","tiger_i"],["JAGDPANTHER","jagdpanther"],["SU-100","su100"]]:
		var choice_button=button(choices,choice[0],func(id=choice[1]):select_vehicle(id));choice_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL;choice_button.custom_minimum_size.y=44;choice_button.add_theme_font_size_override("font_size",15)
		vehicle_buttons[choice[1]]=choice_button
	selected_vehicle_label=label(selection,"T-34-85",12);selected_vehicle_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;selected_vehicle_label.modulate=Color("c1a573")
	vehicle_preview=preview_stage(center,"VEHICLE · 3D VIEW",VehiclePreview,Vector2(400,155),selected_vehicle)
	_update_vehicle_selection()
	var right=panel(columns);right.name="OpenDayRight";right.custom_minimum_size.x=280;right.size_flags_stretch_ratio=0.80
	label(right,"WHY A FLY?",22);label(right,"EYES",14).modulate=Color("c1a573");label(right,"Visual signals enter the reconstructed sensory pathways.",15)
	label(right,"NERVOUS SYSTEM",14).modulate=Color("c1a573");label(right,"The fixed MaleCNS model processes those signals.",15)
	label(right,"MOVEMENT",14).modulate=Color("c1a573");label(right,"Descending-neuron signals pass through an external engineered motor adapter.",15)
	label(right,copy_text("OPPONENT POLICY"),14).modulate=Color("c1a573")
	opponent_picker=OptionButton.new();opponent_picker.name="OpenDayOpponentPolicy";opponent_picker.add_item(copy_text("MaleCNS Baseline"),0);opponent_picker.add_item(copy_text("MaleCNS + Trained PPO"),1);opponent_picker.select(1 if AppState.open_day_policy_mode=="trained" else 0);right.add_child(opponent_picker)
	opponent_picker.item_selected.connect(func(index):
		AppState.open_day_policy_mode="trained" if index==1 else "baseline"
		if index==0:
			AppState.settings.open_day_policy_mode="baseline";AppState.save_settings()
		_update_policy_status())
	var choose_policy=button(right,copy_text("Choose deployment policy…"),_choose_open_day_policy)
	choose_policy.custom_minimum_size.y=42
	policy_status_label=label(right,"",12);policy_status_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;policy_status_label.modulate=Color("aebcb4")
	_update_policy_status()
	var grow=Control.new();grow.size_flags_vertical=Control.SIZE_EXPAND_FILL;right.add_child(grow)
	button(right,"START DEMO",func():AppState.start_demo(selected_vehicle))
	button(right,AppState.language_switch_label(),AppState.toggle_language)
	button(right,"RESEARCH INTERFACE",AppState.research_menu)
	var attract_card=PanelContainer.new();attract_card.set_anchors_preset(Control.PRESET_CENTER);attract_card.offset_left=-460;attract_card.offset_right=460;attract_card.offset_top=-92;attract_card.offset_bottom=92;attract_card.mouse_filter=Control.MOUSE_FILTER_IGNORE
	var attract_style=StyleBoxFlat.new();attract_style.bg_color=Color(.035,.065,.06,.93);attract_style.border_color=Color("c1a573");attract_style.set_border_width_all(1);attract_style.set_corner_radius_all(7);attract_style.content_margin_left=28;attract_style.content_margin_right=28;attract_card.add_theme_stylebox_override("panel",attract_style)
	attract_label=Label.new();attract_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;attract_label.vertical_alignment=VERTICAL_ALIGNMENT_CENTER;attract_label.add_theme_font_size_override("font_size",40);attract_label.add_theme_color_override("font_color",Color("ead58f"));attract_label.add_theme_color_override("font_shadow_color",Color.BLACK);attract_label.add_theme_constant_override("shadow_offset_x",2);attract_label.add_theme_constant_override("shadow_offset_y",2);attract_label.mouse_filter=Control.MOUSE_FILTER_IGNORE;attract_card.add_child(attract_label);attract_card.visible=false;add_child(attract_card)

func select_vehicle(vehicle_id: String) -> void:
	selected_vehicle=vehicle_id
	if is_instance_valid(vehicle_preview):vehicle_preview.set_vehicle(vehicle_id)
	_update_vehicle_selection()

func _update_vehicle_selection() -> void:
	if is_instance_valid(selected_vehicle_label):
		var vehicle_name: String = {"t34_85":"T-34-85","is2_1944":"IS-2 (1944)","panther_g":"PANTHER G","tiger_i":"TIGER I","jagdpanther":"JAGDPANTHER","su100":"SU-100"}.get(selected_vehicle,selected_vehicle)
		if str(AppState.settings.language) == "ru":
			vehicle_name = {"is2_1944":"ИС-2 обр. 1944","su100":"СУ-100"}.get(selected_vehicle, vehicle_name)
		selected_vehicle_label.text = ("ВЫБРАНО · " if str(AppState.settings.language) == "ru" else "SELECTED · ") + vehicle_name
		selected_vehicle_label.add_theme_color_override("font_color", DesignSystem.text_for(str(AppState.settings.get("appearance", "dark"))))
	for id in vehicle_buttons:
		var choice_button: Button=vehicle_buttons[id]
		choice_button.modulate=Color.WHITE
		if id==selected_vehicle:
			var selected_style := StyleBoxFlat.new()
			selected_style.bg_color=Color("34433d") if not DesignSystem.is_light(str(AppState.settings.get("appearance", "dark"))) else Color("e3e9dd")
			selected_style.border_color=DesignSystem.gold_for(str(AppState.settings.get("appearance", "dark")))
			selected_style.set_border_width_all(2)
			selected_style.set_corner_radius_all(10)
			selected_style.content_margin_left=18;selected_style.content_margin_right=18;selected_style.content_margin_top=12;selected_style.content_margin_bottom=12
			choice_button.add_theme_stylebox_override("normal",selected_style)
			choice_button.add_theme_color_override("font_color",DesignSystem.text_for(str(AppState.settings.get("appearance", "dark"))))
		else:
			choice_button.remove_theme_stylebox_override("normal")
			choice_button.remove_theme_color_override("font_color")

func build_how(root: VBoxContainer):
	label(root,"HOW DOES THE FLY CONTROL A TANK?",34)
	var flow=GridContainer.new();flow.name="HowItWorksCards";flow.columns=2;flow.size_flags_vertical=Control.SIZE_EXPAND_FILL;flow.size_flags_horizontal=Control.SIZE_EXPAND_FILL;flow.add_theme_constant_override("h_separation",14);flow.add_theme_constant_override("v_separation",12);root.add_child(flow)
	var fly=panel(flow);preview(fly,Vector2(250,142));label(fly,"1. FLY",22);label(fly,"Sensory signals from the virtual world",15).modulate=Color("aebcb4")
	var brain=panel(flow);label(brain,"2. BIOLOGICAL MODEL",13).modulate=Color("c1a573");label(brain,"FIXED MALECNS",24);label(brain,"Reconstructed connectome\nDNp09 · DNa02 · DNp01 · wing/song",15);label(brain,"The connectome is frozen and does not understand tanks, objectives or tactics.",13).modulate=Color("aebcb4")
	var adapter=panel(flow);label(adapter,"3. ENGINEERED ADAPTER",13).modulate=Color("c1a573");label(adapter,"SIGNALS → CONTROLS",23);label(adapter,"motor decoder · movement auxiliary\naiming and firing helper",15);label(adapter,"This external layer converts neural activity into safe vehicle controls.",13).modulate=Color("aebcb4")
	var tank=panel(flow);label(tank,"4. VIRTUAL VEHICLE",22);label(tank,"movement · turning · aiming · firing",17);label(tank,"The existing FlySwarm physics, armour and ballistics remain active.",13).modulate=Color("aebcb4")
	var footer=HBoxContainer.new();root.add_child(footer);button(footer,"START DEMO",func():AppState.start_demo("t34_85"));button(footer,"BACK",AppState.open_day_menu)

func build_result(root: VBoxContainer):
	var report=AppState.last_report;var human_alive=false;var fly_alive=false;var shots=0;var hits=0
	for state in report.get("vehicles",[]):
		if int(state.id)==0:human_alive=state.alive;shots=int(state.metrics.shots);hits=int(state.metrics.penetrations)
		if int(state.id)==8:fly_alive=state.alive
	var outcome=result_outcome(human_alive,fly_alive)
	var box=panel(root);box.alignment=BoxContainer.ALIGNMENT_CENTER
	var outcome_text="YOU DEFEATED THE FLY" if outcome=="human" else ("THE FLY WON" if outcome=="fly" else "DRAW")
	if str(AppState.settings.language)=="ru":outcome_text="ТЫ ПОБЕДИЛ МУХУ" if outcome=="human" else ("МУХА ПОБЕДИЛА" if outcome=="fly" else "НИЧЬЯ")
	preview(box,Vector2(520,280));label(box,outcome_text,40)
	if outcome=="fly":label(box,"Yes. A reconstructed model of the Drosophila nervous system just won this round.",20)
	if outcome=="draw":label(box,copy_text("Neither vehicle was destroyed; no winner was awarded."),18)
	var result_stats=("Time: %.1f s   ·   shots: %d   ·   penetrating hits: %d" % [report.get("time",0),shots,hits])
	if str(AppState.settings.language)=="ru":result_stats=("Время: %.1f с   ·   выстрелы: %d   ·   пробития: %d" % [report.get("time",0),shots,hits])
	label(box,result_stats,18)
	label(box,"MaleCNS + external engineered motor/tactical layer",14).modulate=Color("aebcb4")
	var buttons=HBoxContainer.new();box.add_child(buttons);button(buttons,"PLAY AGAIN",AppState.rerun);button(buttons,"HOW IT WORKS",AppState.show_page.bind("HowItWorks"));button(buttons,"OPEN DAY MENU",AppState.open_day_menu)

func result_outcome(human_alive: bool,fly_alive: bool) -> String:
	if human_alive and not fly_alive:return "human"
	if fly_alive and not human_alive:return "fly"
	return "draw"

func _process(delta):
	if page!="OpenDayMain":return
	# The attract-mode advertisement must never obscure controller navigation,
	# even when the player keeps the stick still while choosing a menu item.
	if not Input.get_connected_joypads().is_empty():
		attract_elapsed=0.0
		attract_active=false
		if is_instance_valid(attract_label):attract_label.get_parent().visible=false
		return
	attract_elapsed+=delta
	if attract_elapsed>=30.0:
		attract_active=true
		attract_clock+=delta
		if attract_clock>=4.0:attract_clock=0;attract_phase=(attract_phase+1)%3
		attract_label.get_parent().visible=true
		attract_label.text=copy_text(["A FLY CONTROLS A TANK","REAL MALECNS ACTIVITY","CAN YOU DEFEAT THE FLY?\nCLICK TO FIGHT"][attract_phase])

func _input(event):
	# Controller navigation belongs exclusively to AppState.
	if page!="OpenDayMain":return
	if attract_active and event is InputEventMouseButton and event.pressed:
		get_viewport().set_input_as_handled()
		AppState.start_demo(selected_vehicle)
		return
	if event is InputEventMouseMotion or event is InputEventKey:
		attract_elapsed=0.0
		attract_active=false
		if is_instance_valid(attract_label):attract_label.get_parent().visible=false

func focus_first_controller_button() -> void:
	if not is_inside_tree():return
	var buttons=controller_buttons()
	if not buttons.is_empty():buttons[0].grab_focus()

func controller_buttons() -> Array[Button]:
	var buttons: Array[Button]=[]
	for node in find_children("*","Button",true,false):
		if node is Button and node.visible and not node.disabled and node.focus_mode!=Control.FOCUS_NONE:buttons.append(node)
	return buttons

