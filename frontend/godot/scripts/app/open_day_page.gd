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
	"PLAY AGAIN":"ЕЩЁ РАЗ","OPEN DAY MENU":"В МЕНЮ ДЕМО","A FLY CONTROLS A TANK":"МУХА УПРАВЛЯЕТ ТАНКОМ","REAL MALECNS ACTIVITY":"АКТИВНОСТЬ МОДЕЛИ MALECNS","CAN YOU DEFEAT THE FLY?\nCLICK TO FIGHT":"СМОЖЕШЬ ПОБЕДИТЬ МУХУ?\nНАЖМИ, ЧТОБЫ СРАЗИТЬСЯ"
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
func panel(parent: Node) -> VBoxContainer:
	var frame=PanelContainer.new();frame.size_flags_vertical=Control.SIZE_EXPAND_FILL;frame.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	frame.add_theme_stylebox_override("panel",DesignSystem.panel_style(str(AppState.settings.get("appearance","dark"))));parent.add_child(frame)
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",12);frame.add_child(box);return box
func preview(parent: Node,min_size=Vector2(480,340)):
	var fly=FlyPreview.new();fly.custom_minimum_size=min_size;fly.size_flags_vertical=Control.SIZE_EXPAND_FILL;fly.size_flags_horizontal=Control.SIZE_EXPAND_FILL;parent.add_child(fly);return fly

func build_main(root: VBoxContainer):
	var columns=HBoxContainer.new();columns.size_flags_vertical=Control.SIZE_EXPAND_FILL;columns.add_theme_constant_override("separation",18);root.add_child(columns)
	columns.name="OpenDayColumns"
	var left=panel(columns);left.name="OpenDayLeft";left.custom_minimum_size.x=310
	label(left,"OPEN DAY",14).modulate=Color("c1a573");label(left,"FLYSWARM",44);label(left,"A fly controls a tank.",27);label(left,"Fight a reconstructed model of the Drosophila nervous system.",16).modulate=Color("aebcb4")
	var start=button(left,"QUICK BATTLE: VISITOR VS FLY",func():AppState.start_demo(selected_vehicle));start.custom_minimum_size.y=72
	button(left,"AUTONOMOUS BATTLE",func():AppState.configure("battle"))
	button(left,"HOW IT WORKS",AppState.show_page.bind("HowItWorks"))
	button(left,"TEST RANGE",func():AppState.configure("range"))
	button(left,"REPLAYS",AppState.show_page.bind("ReplayBrowser"))
	button(left,"SETTINGS",AppState.show_page.bind("Settings"))
	var center=panel(columns);center.name="OpenDayCenter";center.custom_minimum_size.x=450
	preview(center,Vector2(400,185))
	label(center,"This is Drosophila.",20)
	var summary=label(center,"We use a reconstructed nervous system model to control an agent in a virtual world.",14);summary.modulate=Color("aebcb4")
	label(center,"CHOOSE YOUR VEHICLE",13).modulate=Color("c1a573")
	var choices=GridContainer.new();choices.columns=3;choices.add_theme_constant_override("h_separation",6);choices.add_theme_constant_override("v_separation",4);center.add_child(choices)
	for choice in [["T-34-85","t34_85"],["IS-2 (44)","is2_1944"],["PANTHER G","panther_g"],["TIGER I","tiger_i"],["JAGDPANTHER","jagdpanther"],["SU-100","su100"]]:
		var choice_button=button(choices,choice[0],func(id=choice[1]):select_vehicle(id));choice_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL;choice_button.custom_minimum_size.y=44;choice_button.add_theme_font_size_override("font_size",15)
		vehicle_buttons[choice[1]]=choice_button
	selected_vehicle_label=label(center,"T-34-85",12);selected_vehicle_label.modulate=Color("c1a573")
	vehicle_preview=VehiclePreview.new();vehicle_preview.custom_minimum_size=Vector2(400,155);vehicle_preview.size_flags_horizontal=Control.SIZE_EXPAND_FILL;vehicle_preview.vehicle_id=selected_vehicle;center.add_child(vehicle_preview)
	_update_vehicle_selection()
	var right=panel(columns);right.name="OpenDayRight";right.custom_minimum_size.x=285
	label(right,"WHY A FLY?",22);label(right,"EYES",14).modulate=Color("c1a573");label(right,"Visual signals enter the reconstructed sensory pathways.",15)
	label(right,"NERVOUS SYSTEM",14).modulate=Color("c1a573");label(right,"The fixed MaleCNS model processes those signals.",15)
	label(right,"MOVEMENT",14).modulate=Color("c1a573");label(right,"Descending-neuron signals pass through an external engineered motor adapter.",15)
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
		selected_vehicle_label.text={"t34_85":"T-34-85","is2_1944":"IS-2 (1944)","panther_g":"PANTHER G","tiger_i":"TIGER I","jagdpanther":"JAGDPANTHER","su100":"SU-100"}.get(selected_vehicle,selected_vehicle)
	for id in vehicle_buttons:
		var choice_button: Button=vehicle_buttons[id]
		choice_button.modulate=Color.WHITE
		if id==selected_vehicle:
			var selected_style := StyleBoxFlat.new()
			selected_style.bg_color=Color("294044")
			selected_style.border_color=DesignSystem.ACCENT
			selected_style.set_border_width_all(2)
			selected_style.set_corner_radius_all(10)
			selected_style.content_margin_left=18;selected_style.content_margin_right=18;selected_style.content_margin_top=12;selected_style.content_margin_bottom=12
			choice_button.add_theme_stylebox_override("normal",selected_style)
			choice_button.add_theme_color_override("font_color",DesignSystem.ACCENT)
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
	var buttons=controller_buttons()
	if not buttons.is_empty():buttons[0].grab_focus()

func controller_buttons() -> Array[Button]:
	var buttons: Array[Button]=[]
	for node in find_children("*","Button",true,false):
		if node is Button and node.visible and not node.disabled and node.focus_mode!=Control.FOCUS_NONE:buttons.append(node)
	return buttons

