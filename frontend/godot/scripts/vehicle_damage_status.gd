extends Control

var vehicle

func show_vehicle(value) -> void:
	vehicle=value
	queue_redraw()

func _draw() -> void:
	if vehicle==null:return
	var cfg: Dictionary=vehicle.cfg
	var centre=Vector2(size.x*.5,size.y*.50)
	var scale_factor=minf((size.x-74.0)/maxf(1.0,float(cfg.width_m)*1.55),(size.y-24.0)/maxf(1.0,float(cfg.length_m)))
	var half_width=float(cfg.width_m)*scale_factor*.5
	var half_length=float(cfg.length_m)*scale_factor*.5
	var hull=Rect2(centre-Vector2(half_width*.8,half_length*.84),Vector2(half_width*1.6,half_length*1.68))
	var outline=Color(.69,.78,.69,.88)
	var fill=Color(.19,.27,.24,.72)
	var track_width=maxf(7.0,half_width*.22)
	for side in [-1.0,1.0]:
		var x=centre.x+side*(half_width-track_width*.3)-track_width*.5
		var track=Rect2(x,centre.y-half_length,track_width,half_length*2.0)
		draw_rect(track,Color(.12,.18,.17,.82),true)
		draw_rect(track,outline,false,1.3)
		for step in range(8):
			var z=track.position.y+(float(step)+.5)*track.size.y/8.0
			draw_line(Vector2(x,z),Vector2(x+track_width,z),Color(.55,.65,.57,.6),1.0)
	draw_rect(hull,fill,true)
	draw_rect(hull,outline,false,1.6)
	var upper=centre-Vector2(0,half_length*.19)
	if bool(cfg.get("turreted",true)):
		draw_circle(upper,minf(half_width*.65,half_length*.32),Color(.3,.39,.34,.88))
		draw_arc(upper,minf(half_width*.65,half_length*.32),0.0,TAU,32,outline,1.7)
	else:
		var casemate=Rect2(upper-Vector2(half_width*.54,half_length*.28),Vector2(half_width*1.08,half_length*.56))
		draw_rect(casemate,Color(.3,.39,.34,.88),true)
		draw_rect(casemate,outline,false,1.7)
	draw_line(upper,upper-Vector2(0,half_length*.77),outline,8.0)
	draw_line(upper,upper-Vector2(0,half_length*.77),Color(.15,.22,.2),5.0)
	for key in vehicle.volumes:
		var point: Vector3=vehicle.volumes[key]
		var pos=centre+Vector2(point.x,-point.z)*scale_factor
		var enabled=bool(vehicle.modules.get(key,true))
		var damage=float(vehicle.module_damage.get(key,0.0))
		var colour=Color(.39,.89,.63) if enabled and damage<=0.0 else (Color(1.0,.74,.23) if enabled else Color(1.0,.29,.21))
		var crew=key in ["driver","gunner","commander","loader","radio_operator"]
		if crew:
			draw_circle(pos,6.0,Color(.04,.07,.06,.95))
			draw_circle(pos,4.6,colour)
		else:
			var box=Rect2(pos-Vector2(5.0,5.0),Vector2(10.0,10.0))
			draw_rect(box,Color(.04,.07,.06,.95),true)
			draw_rect(Rect2(pos-Vector2(3.4,3.4),Vector2(6.8,6.8)),colour,true)
	var font=ThemeDB.fallback_font
	var font_size=10
	var russian=str(AppState.settings.language)=="ru"
	draw_string(font,Vector2(8,14),"ПЕРЕД" if russian else "FRONT",HORIZONTAL_ALIGNMENT_LEFT,-1,font_size,Color(.78,.88,.77))
	draw_line(Vector2(33,18),Vector2(33,29),Color(.78,.88,.77),1.5)
	draw_colored_polygon(PackedVector2Array([Vector2(29,25),Vector2(37,25),Vector2(33,19)]),Color(.78,.88,.77))
	var legend_y=16.0
	draw_circle(Vector2(size.x-140,legend_y),3.5,Color(.39,.89,.63))
	draw_string(font,Vector2(size.x-133,20),"ЦЕЛО" if russian else "OK",HORIZONTAL_ALIGNMENT_LEFT,-1,9,Color(.78,.88,.77))
	draw_circle(Vector2(size.x-91,legend_y),3.5,Color(1.0,.74,.23))
	draw_string(font,Vector2(size.x-84,20),"УЩЕРБ" if russian else "HIT",HORIZONTAL_ALIGNMENT_LEFT,-1,9,Color(.78,.88,.77))
	draw_circle(Vector2(size.x-42,legend_y),3.5,Color(1.0,.29,.21))
	draw_string(font,Vector2(size.x-35,20),"ВЫБЫЛ" if russian else "OUT",HORIZONTAL_ALIGNMENT_LEFT,-1,9,Color(.78,.88,.77))
