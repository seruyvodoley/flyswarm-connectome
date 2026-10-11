extends PanelContainer

class ImpactDiagram extends Control:
	var impact: Dictionary = {}
	func _draw():
		var c=Vector2(size.x*.5,size.y*.52)
		var hull=Rect2(c.x-30,c.y-50,60,100)
		draw_rect(hull,Color("68736d"),true)
		draw_rect(hull,Color("bba16c"),false,2)
		draw_circle(c+Vector2(0,3),17,Color("424b47"))
		draw_rect(Rect2(c.x-2,c.y-51,4,29),Color("d2c19a"),true)
		var p=impact.get("point_local",[])
		if not p is Array or p.size()<3:return
		var hit=Vector2(c.x+clampf(float(p[0]),-2.4,2.4)*12.0,c.y-clampf(float(p[2]),-4.0,4.0)*12.0)
		var d=impact.get("incoming_local",[])
		if d is Array and d.size()>=3:
			var incoming=Vector2(float(d[0]),-float(d[2])).normalized()
			if incoming.length()>0.1:
				var tail=hit-incoming*34.0
				draw_line(tail,hit,Color("f1a34a"),3,true)
				draw_circle(tail,3,Color("f1a34a"))
		draw_circle(hit,7,Color("ff5147"))
		draw_arc(hit,10,0,TAU,24,Color("ffe2a1"),2,true)

var diagram: ImpactDiagram
var title: Label
var body: Label

func _ready():
	set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	offset_left=-230
	offset_right=230
	offset_top=-140
	offset_bottom=-20
	custom_minimum_size=Vector2(460,120)
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	var style=StyleBoxFlat.new()
	style.bg_color=Color(.025,.035,.04,.94)
	style.border_color=Color(.72,.43,.24,.95)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.content_margin_left=12
	style.content_margin_right=12
	style.content_margin_top=10
	style.content_margin_bottom=10
	add_theme_stylebox_override("panel",style)
	var row=HBoxContainer.new()
	row.add_theme_constant_override("separation",12)
	add_child(row)
	diagram=ImpactDiagram.new()
	diagram.custom_minimum_size=Vector2(100,95)
	row.add_child(diagram)
	var info=VBoxContainer.new()
	info.size_flags_horizontal=Control.SIZE_EXPAND_FILL
	row.add_child(info)
	title=Label.new()
	title.add_theme_font_size_override("font_size",12)
	title.add_theme_color_override("font_color",Color("ead58f"))
	info.add_child(title)
	body=Label.new()
	body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override("font_size",10)
	body.add_theme_color_override("font_color",Color("edf0e8"))
	body.size_flags_vertical=Control.SIZE_EXPAND_FILL
	info.add_child(body)
	hide()

func show_impact(event: Dictionary):
	var impact: Dictionary=event.get("impact",{})
	var russian=str(AppState.settings.language)=="ru"
	var vehicle_name=str(event.get("vehicle","vehicle"))
	var shell_name=str(event.get("shell",impact.get("shell","unknown")))
	var penetrated=bool(impact.get("penetrated",false))
	var damaged=impact.get("damaged",[])
	var disabled=impact.get("disabled",[])
	var damaged_text="Нет внутренних повреждений" if russian else "No internal damage"
	if damaged is Array and not damaged.is_empty():
		var readable=[]
		for module in damaged:readable.append(str(module).replace("_"," "))
		damaged_text=", ".join(PackedStringArray(readable))
		if disabled is Array and not disabled.is_empty():
			var disabled_readable=[]
			for module in disabled:disabled_readable.append(str(module).replace("_"," "))
			damaged_text+=(" · выведено из строя: " if russian else " · disabled: ")+", ".join(PackedStringArray(disabled_readable))
	title.text=("КРИТИЧЕСКОЕ ПОПАДАНИЕ · КИЛЛКАМ" if russian else "FATAL HIT · IMPACT CAM") if bool(event.get("fatal",false)) else ("ПОСЛЕДНЕЕ ПОПАДАНИЕ · КИЛЛКАМ" if russian else "LAST IMPACT · HIT CAM")
	var result="ПРОБИТИЕ" if penetrated and russian else ("PENETRATED" if penetrated else ("РИКОШЕТ" if russian and bool(impact.get("ricochet",false)) else ("RICOCHET" if bool(impact.get("ricochet",false)) else ("НЕ ПРОБИЛО" if russian else "STOPPED"))))
	var outcome=str(impact.get("outcome",""))
	var outcome_text=""
	if penetrated:
		if outcome=="critical":outcome_text="КРИТИЧЕСКИЙ УРОН" if russian else "CRITICAL DAMAGE"
		elif outcome=="minor_damage":outcome_text="НЕЗНАЧИТЕЛЬНЫЙ УРОН" if russian else "MINOR DAMAGE"
		elif outcome=="penetration_no_internal_damage":outcome_text="ПРОБИТИЕ БЕЗ ПОРАЖЕНИЯ МОДУЛЕЙ" if russian else "PENETRATION, NO MODULE HIT"
	body.text="%s\n%s · %s %s\n%s: %s\n%s: %.0f / %.0f mm\n%s: %s" % [vehicle_name,shell_name,result,outcome_text,"Зона попадания" if russian else "Hit zone",str(impact.get("zone","unknown")),"Пробитие" if russian else "Penetration",float(impact.get("capability",0.0)),float(impact.get("effective",0.0)),"Повреждения" if russian else "Damage",damaged_text]
	diagram.impact=impact.duplicate(true)
	diagram.queue_redraw()
	show()
