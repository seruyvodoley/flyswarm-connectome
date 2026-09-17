extends Control

var ammo=0
var reload_left=0.0

func _ready():
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

func set_weapon_state(new_ammo: int,new_reload: float):
	ammo=new_ammo
	reload_left=new_reload
	queue_redraw()

func _draw():
	var c=size*.5
	var colour=Color(0.88,0.92,0.82,0.92)
	var shadow=Color(0.02,0.03,0.02,0.82)
	for offset in [Vector2(1,1),Vector2.ZERO]:
		var ink=shadow if offset!=Vector2.ZERO else colour
		draw_line(c+Vector2(-34,0)+offset,c+Vector2(-7,0)+offset,ink,2.0)
		draw_line(c+Vector2(7,0)+offset,c+Vector2(34,0)+offset,ink,2.0)
		draw_line(c+Vector2(0,-34)+offset,c+Vector2(0,-7)+offset,ink,2.0)
		draw_line(c+Vector2(0,7)+offset,c+Vector2(0,34)+offset,ink,2.0)
		for mark in range(1,5):
			var d=float(mark)*36.0
			draw_line(c+Vector2(-d,-5)+offset,c+Vector2(-d,5)+offset,ink,1.5)
			draw_line(c+Vector2(d,-5)+offset,c+Vector2(d,5)+offset,ink,1.5)
			draw_line(c+Vector2(-5,d)+offset,c+Vector2(5,d)+offset,ink,1.5)
	var state="READY" if reload_left<=0.0 else "RELOAD %.1f s" % reload_left
	draw_string(ThemeDB.fallback_font,c+Vector2(-74,190),"%s   ·   AMMO %d" % [state,ammo],HORIZONTAL_ALIGNMENT_CENTER,148,16,colour)
