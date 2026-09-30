extends Control
@export var page="OpenDayMain"
const FlyPreview=preload("res://scripts/app/fly_preview.gd")
var selected_vehicle="t34_85"
var attract_elapsed=0.0
var attract_active=false
var attract_label: Label
var attract_phase=0
var attract_clock=0.0

func _ready():
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var theme_resource=Theme.new();theme_resource.default_font_size=18
	for kind in ["normal","hover","pressed","focus","disabled"]:
		var style=StyleBoxFlat.new();style.bg_color=Color("253532") if kind=="hover" else Color("172622");style.border_color=Color("bba16c") if kind in ["hover","focus"] else Color("35433e");style.set_border_width_all(1);style.set_corner_radius_all(4);style.content_margin_left=18;style.content_margin_right=18;style.content_margin_top=11;style.content_margin_bottom=11;theme_resource.set_stylebox(kind,"Button",style)
	theme=theme_resource
	var bg=ColorRect.new();bg.color=Color("0b1414");bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);add_child(bg)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,30)
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

func label(parent: Node,text: String,size=18) -> Label:
	var value=Label.new();value.text=AppState.tr_text(text);value.add_theme_font_size_override("font_size",size);value.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;parent.add_child(value);return value
func button(parent: Node,text: String,callback: Callable) -> Button:
	var value=Button.new();value.text=AppState.tr_text(text);value.name=text.to_pascal_case();value.custom_minimum_size.y=48;value.pressed.connect(callback);parent.add_child(value);return value
func panel(parent: Node) -> VBoxContainer:
	var frame=PanelContainer.new();frame.size_flags_vertical=Control.SIZE_EXPAND_FILL;frame.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var style=StyleBoxFlat.new();style.bg_color=Color("101d1a");style.border_color=Color("3b5149");style.set_border_width_all(1);style.set_corner_radius_all(5);style.content_margin_left=20;style.content_margin_right=20;style.content_margin_top=18;style.content_margin_bottom=18;frame.add_theme_stylebox_override("panel",style);parent.add_child(frame)
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",12);frame.add_child(box);return box
func preview(parent: Node,min_size=Vector2(480,340)):
	var fly=FlyPreview.new();fly.custom_minimum_size=min_size;fly.size_flags_vertical=Control.SIZE_EXPAND_FILL;fly.size_flags_horizontal=Control.SIZE_EXPAND_FILL;parent.add_child(fly);return fly

func build_main(root: VBoxContainer):
	var columns=HBoxContainer.new();columns.size_flags_vertical=Control.SIZE_EXPAND_FILL;columns.add_theme_constant_override("separation",18);root.add_child(columns)
	var left=panel(columns);left.custom_minimum_size.x=310
	label(left,"OPEN DAY",14).modulate=Color("c1a573");label(left,"FLYSWARM",44);label(left,"A fly controls a tank.",27);label(left,"Fight a reconstructed model of the Drosophila nervous system.",16).modulate=Color("aebcb4")
	var start=button(left,"QUICK BATTLE: VISITOR VS FLY",func():AppState.start_demo(selected_vehicle));start.custom_minimum_size.y=72
	button(left,"AUTONOMOUS BATTLE",func():AppState.configure("battle"))
	button(left,"HOW IT WORKS",AppState.show_page.bind("HowItWorks"))
	button(left,"TEST RANGE",func():AppState.configure("range"))
	button(left,"REPLAYS",AppState.show_page.bind("ReplayBrowser"))
	button(left,"SETTINGS",AppState.show_page.bind("Settings"))
	var center=panel(columns);center.custom_minimum_size.x=450;preview(center,Vector2(450,330));label(center,"This is Drosophila.",22);label(center,"We use a reconstructed model of its nervous system to control an agent in a virtual environment.",16).modulate=Color("aebcb4")
	label(center,"CHOOSE YOUR VEHICLE",13).modulate=Color("c1a573")
	var choices=HBoxContainer.new();choices.add_theme_constant_override("separation",6);center.add_child(choices)
	for choice in [["T-34-85","t34_85"],["PANTHER G","panther_g"],["TIGER I","tiger_i"]]:
		var choice_button=button(choices,choice[0],func(id=choice[1]):selected_vehicle=id);choice_button.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	var right=panel(columns);right.custom_minimum_size.x=285
	label(right,"WHY A FLY?",22);label(right,"EYES",14).modulate=Color("c1a573");label(right,"Visual signals enter the reconstructed sensory pathways.",15)
	label(right,"NERVOUS SYSTEM",14).modulate=Color("c1a573");label(right,"The fixed MaleCNS model processes those signals.",15)
	label(right,"MOVEMENT",14).modulate=Color("c1a573");label(right,"Descending-neuron signals pass through an external engineered motor adapter.",15)
	var grow=Control.new();grow.size_flags_vertical=Control.SIZE_EXPAND_FILL;right.add_child(grow)
	button(right,"START DEMO",func():AppState.start_demo(selected_vehicle))
	button(right,AppState.language_switch_label(),AppState.toggle_language)
	button(right,"RESEARCH INTERFACE",AppState.research_menu)
	attract_label=Label.new();attract_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);attract_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;attract_label.vertical_alignment=VERTICAL_ALIGNMENT_CENTER;attract_label.add_theme_font_size_override("font_size",42);attract_label.add_theme_color_override("font_color",Color("ead58f"));attract_label.add_theme_color_override("font_shadow_color",Color.BLACK);attract_label.add_theme_constant_override("shadow_offset_x",3);attract_label.add_theme_constant_override("shadow_offset_y",3);attract_label.mouse_filter=Control.MOUSE_FILTER_IGNORE;attract_label.visible=false;add_child(attract_label)

func build_how(root: VBoxContainer):
	label(root,"HOW DOES THE FLY CONTROL A TANK?",34)
	var flow=HBoxContainer.new();flow.size_flags_vertical=Control.SIZE_EXPAND_FILL;flow.add_theme_constant_override("separation",16);root.add_child(flow)
	var fly=panel(flow);preview(fly,Vector2(300,240));label(fly,"1. FLY",24);label(fly,"Sensory signals from the virtual world",16)
	var brain=panel(flow);label(brain,"2. BIOLOGICAL MODEL",14).modulate=Color("c1a573");label(brain,"FIXED MALECNS",28);label(brain,"Reconstructed connectome\nDNp09 · DNa02 · DNp01 · wing/song",17);label(brain,"The connectome is frozen and does not understand tanks, objectives or tactics.",15).modulate=Color("aebcb4")
	var adapter=panel(flow);label(adapter,"3. ENGINEERED ADAPTER",14).modulate=Color("c1a573");label(adapter,"SIGNALS → CONTROLS",26);label(adapter,"motor decoder\nmovement auxiliary\naiming and firing helper",17);label(adapter,"This external layer converts neural activity into safe vehicle controls.",15).modulate=Color("aebcb4")
	var tank=panel(flow);label(tank,"4. VIRTUAL VEHICLE",24);label(tank,"movement\nturning\naiming\nfiring",20);label(tank,"The existing FlySwarm physics, armour and ballistics remain active.",15)
	var footer=HBoxContainer.new();root.add_child(footer);button(footer,"START DEMO",func():AppState.start_demo("t34_85"));button(footer,"BACK",AppState.open_day_menu)

func build_result(root: VBoxContainer):
	var report=AppState.last_report;var human_alive=false;var fly_alive=false;var human_health=0.0;var fly_health=0.0;var shots=0;var hits=0
	for state in report.get("vehicles",[]):
		var working=0
		for value in state.modules.values():working+=1 if value else 0
		var health=float(working)/maxf(1.0,float(state.modules.size())) if state.alive else 0.0
		if int(state.id)==0:human_alive=state.alive;human_health=health;shots=int(state.metrics.shots);hits=int(state.metrics.penetrations)
		if int(state.id)==8:fly_alive=state.alive;fly_health=health
	var human_won=(human_alive and not fly_alive) or (human_alive==fly_alive and human_health>fly_health)
	var box=panel(root);box.alignment=BoxContainer.ALIGNMENT_CENTER
	preview(box,Vector2(520,280));label(box,"YOU DEFEATED THE FLY" if human_won else "THE FLY WON",40)
	if not human_won:label(box,"Yes. A reconstructed model of the Drosophila nervous system just won this round.",20)
	label(box,"Time: %.1f s   ·   shots: %d   ·   penetrating hits: %d" % [report.get("time",0),shots,hits],18)
	label(box,"MaleCNS + external engineered motor/tactical layer",14).modulate=Color("aebcb4")
	var buttons=HBoxContainer.new();box.add_child(buttons);button(buttons,"PLAY AGAIN",AppState.rerun);button(buttons,"HOW IT WORKS",AppState.show_page.bind("HowItWorks"));button(buttons,"OPEN DAY MENU",AppState.open_day_menu)

func _process(delta):
	if page!="OpenDayMain":return
	attract_elapsed+=delta
	if attract_elapsed>=30.0:
		attract_active=true;attract_clock+=delta
		if attract_clock>=4.0:attract_clock=0;attract_phase=(attract_phase+1)%3
		attract_label.visible=true
		attract_label.text=AppState.tr_text(["A FLY CONTROLS A TANK","REAL MALECNS ACTIVITY","CAN YOU DEFEAT THE FLY?\nCLICK TO FIGHT"][attract_phase])

func _unhandled_input(event):
	if page=="OpenDayMain" and event is InputEventMouseButton and event.pressed:
		attract_elapsed=0;attract_active=false
		if is_instance_valid(attract_label):attract_label.visible=false
