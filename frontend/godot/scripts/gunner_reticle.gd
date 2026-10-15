extends Control

var ammo=0
var reload_left=0.0
var scoped=false
var weapon_block=""
var aim_screen_position=Vector2(-1,-1)
var has_aim_screen_position=false
var aim_ready=false
var camera_center_marker=false

func _ready():
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

func set_weapon_state(new_ammo: int,new_reload: float,new_scoped: bool=false,new_block: String=""):
	ammo=new_ammo
	reload_left=new_reload
	scoped=new_scoped
	weapon_block=new_block
	queue_redraw()

func block_message() -> String:
	var russian=str(AppState.settings.language)=="ru"
	match weapon_block:
		"destroyed":return "ТАНК УНИЧТОЖЕН" if russian else "TANK DESTROYED"
		"gunner":return "НАВОДЧИК ВЫБЫЛ" if russian else "GUNNER DOWN"
		"breech":return "КАЗЁННИК СЛОМАН" if russian else "BREECH DISABLED"
		"ammo":return "НЕТ СНАРЯДОВ" if russian else "OUT OF AMMO"
	return ""

func set_aim_screen_position(screen_position: Vector2):
	aim_screen_position=screen_position
	has_aim_screen_position=true
	queue_redraw()

func set_aim_ready(ready: bool):
	aim_ready=ready
	queue_redraw()

func _draw():
	var c=aim_screen_position if has_aim_screen_position else size*.5
	var colour=Color("8ff0a4") if aim_ready else (Color("e5ddb5") if scoped else Color(0.88,0.92,0.82,0.92))
	var shadow=Color(0.02,0.03,0.02,0.82)
	if camera_center_marker:
		var camera_center=size*.5
		var marker_colour=Color("63d8d1",.9)
		draw_arc(camera_center,8.0,0.0,TAU,32,marker_colour,1.5,true)
		draw_circle(camera_center,1.5,marker_colour)
	if scoped:
		# Calibrated optic overlay: graduated marks and a strong bezel stay
		# readable against both sky and terrain.
		var radius=minf(265.0,minf(size.x,size.y)*.38)
		draw_arc(c,radius,0.0,TAU,128,Color(0.01,0.02,0.02,.9),11.0,true)
		draw_arc(c,radius-8.0,0.0,TAU,128,colour,2.0,true)
		for sign_value in [-1,1]:
			for mark in range(1,13):
				var offset=Vector2(sign_value*float(mark)*18.0,0)
				var length=11.0 if mark%3==0 else 5.0
				draw_line(c+offset+Vector2(0,-length),c+offset+Vector2(0,length),colour,1.0)
				var vertical=Vector2(0,sign_value*float(mark)*18.0)
				draw_line(c+vertical+Vector2(-length,0),c+vertical+Vector2(length,0),colour,1.0)
	for offset in [Vector2(1,1),Vector2.ZERO]:
		var ink=shadow if offset!=Vector2.ZERO else colour
		if scoped:
			draw_line(c+Vector2(-44,0)+offset,c+Vector2(-5,0)+offset,ink,2.0)
			draw_line(c+Vector2(5,0)+offset,c+Vector2(44,0)+offset,ink,2.0)
			draw_line(c+Vector2(0,-44)+offset,c+Vector2(0,-5)+offset,ink,2.0)
			draw_line(c+Vector2(0,5)+offset,c+Vector2(0,44)+offset,ink,2.0)
			draw_circle(c,3.0,ink)
		else:
			draw_line(c+Vector2(-34,0)+offset,c+Vector2(-7,0)+offset,ink,2.0)
			draw_line(c+Vector2(7,0)+offset,c+Vector2(34,0)+offset,ink,2.0)
			draw_line(c+Vector2(0,-34)+offset,c+Vector2(0,-7)+offset,ink,2.0)
			draw_line(c+Vector2(0,7)+offset,c+Vector2(0,34)+offset,ink,2.0)
			for mark in range(1,5):
				var d=float(mark)*36.0
				draw_line(c+Vector2(-d,-5)+offset,c+Vector2(-d,5)+offset,ink,1.5)
				draw_line(c+Vector2(d,-5)+offset,c+Vector2(d,5)+offset,ink,1.5)
				draw_line(c+Vector2(-5,-d)+offset,c+Vector2(5,-d)+offset,ink,1.5)
				draw_line(c+Vector2(-5,d)+offset,c+Vector2(5,d)+offset,ink,1.5)
	var state=block_message()
	if state.is_empty():state="READY" if reload_left<=0.0 else "RELOAD %.1f s" % reload_left
	if scoped:state="SNIPER · "+state
	var state_colour=Color("ff8068") if not weapon_block.is_empty() and weapon_block!="reload" else colour
	draw_string(ThemeDB.fallback_font,c+Vector2(-155,190),"%s   ·   AMMO %d" % [state,ammo],HORIZONTAL_ALIGNMENT_CENTER,310,16,state_colour)
