extends PanelContainer

class ImpactModelView extends SubViewportContainer:
	var viewport: SubViewport
	var stage: Node3D
	var model: Node3D

	func _ready():
		stretch=true
		viewport=SubViewport.new()
		viewport.size=Vector2i(430,250)
		viewport.transparent_bg=true
		viewport.own_world_3d=true
		viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
		add_child(viewport)
		stage=Node3D.new()
		viewport.add_child(stage)
		var camera=Camera3D.new()
		camera.position=Vector3(4.5,4.2,6.0)
		camera.fov=35
		stage.add_child(camera)
		camera.look_at(Vector3(0,.75,0))
		var light=DirectionalLight3D.new()
		light.rotation=Vector3(deg_to_rad(-48),deg_to_rad(-28),0)
		light.light_energy=1.6
		stage.add_child(light)
		var fill=OmniLight3D.new()
		fill.position=Vector3(-3,2,2)
		fill.light_energy=.7
		stage.add_child(fill)

	func show_event(event: Dictionary):
		for child in stage.get_children():
			if child is Node3D and child is not Camera3D and child is not DirectionalLight3D and child is not OmniLight3D:
				stage.remove_child(child)
				child.queue_free()
		var vehicle_id=str(event.get("vehicle_id","t34_85"))
		var packed=load("res://assets/vehicles/"+vehicle_id+".glb") as PackedScene
		if packed==null:return
		model=packed.instantiate()
		model.rotation.y=deg_to_rad(-26)
		_apply_xray(model)
		stage.add_child(model)
		var turret=model.find_child("TurretPivot",true,false)
		if turret is Node3D:turret.rotation.y=float(event.get("turret_angle",0.0))
		var impact: Dictionary=event.get("impact",{})
		var centers: Dictionary=event.get("module_positions",{})
		var broken: Array=event.get("destroyed_modules",impact.get("destroyed_modules",[]))
		var damaged: Array=event.get("damaged_modules",impact.get("damaged",[]))
		for key in centers:
			var p=centers[key]
			if not p is Array or p.size()<3:continue
			var point=Vector3(float(p[0]),float(p[1]),float(p[2]))
			if broken.has(key):
				_add_marker(point,.16,Color(1.0,.12,.07,1.0))
			elif damaged.has(key):
				_add_marker(point,.12,Color(1.0,.65,.08,1.0))
		var hit=impact.get("point_local",[])
		var incoming=impact.get("incoming_local",[])
		if hit is Array and hit.size()>=3 and incoming is Array and incoming.size()>=3:
			var origin=Vector3(float(hit[0]),float(hit[1]),float(hit[2]))
			var direction=Vector3(float(incoming[0]),float(incoming[1]),float(incoming[2])).normalized()
			_add_marker(origin,.105,Color(1.0,.95,.6,1.0))
			_add_beam(origin-direction*.8,origin+direction*.12,Color(1.0,.36,.08,1.0))
		model.rotation.y=deg_to_rad(-26)

	func _apply_xray(root: Node3D):
		var ghost=StandardMaterial3D.new()
		ghost.albedo_color=Color(.27,.72,.79,.28)
		ghost.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
		ghost.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		ghost.depth_draw_mode=BaseMaterial3D.DEPTH_DRAW_DISABLED
		ghost.cull_mode=BaseMaterial3D.CULL_DISABLED
		for node in root.find_children("*","MeshInstance3D",true,false):
			(node as MeshInstance3D).material_override=ghost

	func _add_marker(point: Vector3,radius: float,colour: Color):
		var marker=MeshInstance3D.new()
		var sphere=SphereMesh.new()
		sphere.radius=radius
		sphere.height=radius*2.0
		marker.mesh=sphere
		marker.position=point
		var material=StandardMaterial3D.new()
		material.albedo_color=colour
		material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled=true
		material.emission=colour
		marker.material_override=material
		stage.add_child(marker)

	func _add_beam(from: Vector3,to: Vector3,colour: Color):
		var delta=to-from
		if delta.length()<.001:return
		var beam=MeshInstance3D.new()
		var cylinder=CylinderMesh.new()
		cylinder.top_radius=.025
		cylinder.bottom_radius=.025
		cylinder.height=delta.length()
		beam.mesh=cylinder
		beam.position=(from+to)*.5
		var material=StandardMaterial3D.new()
		material.albedo_color=colour
		material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled=true
		material.emission=colour
		beam.material_override=material
		stage.add_child(beam)
		beam.look_at(to,Vector3.UP)
		beam.rotate_object_local(Vector3.RIGHT,PI/2)

var title: Label
var model_view: ImpactModelView
var body: Label

func _ready():
	set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	offset_left=-610
	offset_right=-20
	offset_top=-340
	offset_bottom=-20
	custom_minimum_size=Vector2(590,320)
	size=custom_minimum_size
	var battle=get_parent().get_parent() if get_parent()!=null and get_parent().get_parent()!=null else null
	if battle!=null and bool(battle.get("is_demo")):
		set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
		offset_left=-220
		offset_right=280
		offset_top=-285
		offset_bottom=-20
		custom_minimum_size=Vector2(500,265)
		size=custom_minimum_size
	mouse_filter=Control.MOUSE_FILTER_IGNORE
	var style=StyleBoxFlat.new()
	style.bg_color=Color(.025,.035,.04,.94)
	style.border_color=Color(.72,.43,.24,.95)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	style.content_margin_left=10
	style.content_margin_right=10
	style.content_margin_top=8
	style.content_margin_bottom=8
	add_theme_stylebox_override("panel",style)
	var column=VBoxContainer.new()
	column.add_theme_constant_override("separation",4)
	add_child(column)
	title=Label.new()
	title.text="DAMAGE REPORT"
	title.add_theme_font_size_override("font_size",12)
	title.add_theme_color_override("font_color",Color("ead58f"))
	column.add_child(title)
	model_view=ImpactModelView.new()
	model_view.custom_minimum_size=Vector2(480,180) if battle!=null and bool(battle.get("is_demo")) else Vector2(560,235)
	model_view.size_flags_vertical=Control.SIZE_EXPAND_FILL
	column.add_child(model_view)
	body=Label.new()
	body.add_theme_font_size_override("font_size",10)
	body.add_theme_color_override("font_color",Color("edf0e8"))
	body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	column.add_child(body)
	hide()

func show_impact(event: Dictionary):
	var impact: Dictionary=event.get("impact",{})
	var russian=str(AppState.settings.language)=="ru"
	var vehicle_name=str(event.get("vehicle","vehicle"))
	var shell_name=str(event.get("shell",impact.get("shell","unknown")))
	var penetrated=bool(impact.get("penetrated",false))
	title.text="ОТЧЁТ О ПОПАДАНИИ" if russian else "IMPACT REPORT"
	var outcome=str(impact.get("outcome",""))
	var result="STOPPED"
	if penetrated:result="ПРОБИТИЕ" if russian else "PENETRATED"
	elif bool(impact.get("ricochet",false)):result="РИКОШЕТ" if russian else "RICOCHET"
	elif russian:result="НЕ ПРОБИЛО"
	var state="ТЕХНИКА УНИЧТОЖЕНА" if russian and outcome=="lethal" else ("VEHICLE DESTROYED" if outcome=="lethal" else ("КРИТИЧЕСКИЙ УРОН" if russian and outcome=="critical" else ("CRITICAL DAMAGE" if outcome=="critical" else "")))
	var damaged=event.get("damaged_modules",impact.get("damaged",[]))
	var disabled=event.get("destroyed_modules",impact.get("destroyed_modules",[]))
	var casualties="%s / %s" % [str(impact.get("crew_alive","—")),str(impact.get("crew_total","—"))]
	var modules=" · ".join(PackedStringArray(damaged.map(func(v):return str(v).replace("_"," ")))) if damaged is Array else ""
	var disabled_text=" · ".join(PackedStringArray(disabled.map(func(v):return str(v).replace("_"," ")))) if disabled is Array else ""
	var damage_label=("повреждены" if russian else "damaged")+": "+(modules if not modules.is_empty() else ("—" if russian else "—"))
	var disabled_label=("выведены" if russian else "disabled")+": "+(disabled_text if not disabled_text.is_empty() else "—")
	body.text="%s · %s · %s\n%s: %.0f / %.0f mm · %s\n%s %d · %s · %s · экипаж / crew %s" % [vehicle_name,shell_name,result,"Пробитие" if russian else "Penetration",float(impact.get("capability",0.0)),float(impact.get("effective",0.0)),state,"ВЫСТРЕЛ" if russian else "SHOT",int(event.get("shot_count",1)),damage_label,disabled_label,casualties]
	model_view.show_event(event)
	show()
