extends Control

var model: Node3D
var camera: Camera3D
var viewport_size=Vector2(430,250)
var entry=Vector3.ZERO
var start=Vector3.ZERO
var finish=Vector3.ZERO
var damaged={}
var progress=0.0
var active=false

func set_impact(tank: Node3D,view_camera: Camera3D,viewport_dimensions: Vector2,shot_start: Vector3,hit: Vector3,shot_end: Vector3,module_hits: Dictionary) -> void:
	model=tank
	camera=view_camera
	viewport_size=viewport_dimensions
	start=shot_start
	entry=hit
	finish=shot_end
	damaged=module_hits
	progress=0.0
	active=true
	queue_redraw()

func _point(local: Vector3) -> Vector2:
	var projected=camera.unproject_position(model.to_global(local))
	return Vector2(projected.x*size.x/viewport_size.x,projected.y*size.y/viewport_size.y)

func _draw() -> void:
	if not active or not is_instance_valid(model) or not is_instance_valid(camera):return
	var p_start=_point(start)
	var p_entry=_point(entry)
	var p_current=_point(start.lerp(finish,progress))
	var orange=Color(1.0,.42,.10)
	draw_line(p_start,p_entry,Color(.05,.06,.04,.85),6.0)
	draw_line(p_start,p_entry,orange,3.0)
	draw_circle(p_current,5.5,Color(.06,.07,.05,.9))
	draw_circle(p_current,3.7,Color(1.0,.93,.35))
	draw_arc(p_entry,8.0,0.0,TAU,24,Color(1.0,.92,.36),2.0)
	var font=ThemeDB.fallback_font
	var russian=str(AppState.settings.language)=="ru"
	var entry_label="ВХОД" if russian else "ENTRY"
	var label_pos=p_entry+Vector2(12,-17)
	label_pos.x=clampf(label_pos.x,3.0,maxf(3.0,size.x-48.0))
	label_pos.y=clampf(label_pos.y,13.0,maxf(13.0,size.y-4.0))
	draw_rect(Rect2(label_pos-Vector2(2,11),Vector2(46,15)),Color(.025,.05,.05,.85),true)
	draw_string(font,label_pos,entry_label,HORIZONTAL_ALIGNMENT_LEFT,-1,10,Color(1.0,.94,.57))
	var count=0
	for key in damaged:
		if count>=5:break
		var xyz=damaged[key]
		if not xyz is Vector3:continue
		var point=_point(xyz)
		draw_line(p_entry,point,Color(1.0,.48,.16,.7),1.5)
		draw_circle(point,5.5,Color(.08,.04,.03,.95))
		draw_circle(point,3.8,Color(1.0,.3,.12))
		var label_offset=Vector2(-72.0,28.0) if point.distance_to(p_entry)<45.0 else Vector2(7.0,-7.0)
		var marker=Vector2(clampf(point.x+label_offset.x,3.0,maxf(3.0,size.x-95.0)),clampf(point.y+label_offset.y,13.0,maxf(13.0,size.y-4.0)))
		var name=str(key).replace("_"," ")
		if russian:name={"gunner":"наводчик","driver":"водитель","commander":"командир","loader":"заряжающий","radio_operator":"радист","ammo_rack":"боекомплект","breech":"казённик","turret_drive":"привод башни","engine":"двигатель","transmission":"трансмиссия","fuel":"топливо","track_left":"левая гусеница","track_right":"правая гусеница"}.get(str(key),name)
		draw_rect(Rect2(marker-Vector2(2,11),Vector2(minf(90.0,12.0+name.length()*5.8),15)),Color(.025,.05,.05,.88),true)
		draw_string(font,marker,name,HORIZONTAL_ALIGNMENT_LEFT,90,10,Color(1.0,.73,.58))
		count+=1
