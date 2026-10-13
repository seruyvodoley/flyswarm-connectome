extends PanelContainer
const ImpactPathOverlay=preload("res://scripts/impact_path_overlay.gd")

class ImpactModelView extends SubViewportContainer:
	var viewport: SubViewport
	var stage: Node3D
	var model: Node3D
	var camera: Camera3D
	var projectile: MeshInstance3D
	var overlay: Control
	var path_start=Vector3.ZERO
	var path_end=Vector3.ZERO
	var shot_elapsed=0.0

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
		camera=Camera3D.new()
		camera.position=Vector3(4.5,4.2,8.0)
		camera.fov=43
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
		overlay=ImpactPathOverlay.new()
		overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
		overlay.mouse_filter=Control.MOUSE_FILTER_IGNORE
		add_child(overlay)

	func _process(delta: float):
		if projectile!=null and is_instance_valid(projectile):
			shot_elapsed=minf(1.0,shot_elapsed+delta/1.2)
			projectile.position=path_start.lerp(path_end,shot_elapsed)
			overlay.progress=shot_elapsed
			overlay.queue_redraw()

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
		projectile=null
		overlay.active=false
		var turret=model.find_child("TurretPivot",true,false)
		if turret is Node3D:turret.rotation.y=float(event.get("turret_angle",0.0))
		var impact: Dictionary=event.get("impact",{})
		var centers: Dictionary=event.get("module_positions",{})
		var broken: Array=event.get("destroyed_modules",impact.get("destroyed_modules",[]))
		var damaged: Array=impact.get("damaged",[])
		var disabled: Array=impact.get("disabled",[])
		for key in centers:
			var p=centers[key]
			if not p is Array or p.size()<3:continue
			var point=Vector3(float(p[0]),float(p[1]),float(p[2]))
			if disabled.has(key):
				_add_marker(point,.19,Color(1.0,.12,.07,1.0))
			elif broken.has(key):
				_add_marker(point,.12,Color(.7,.2,.16,.8))
			elif damaged.has(key):
				_add_marker(point,.15,Color(1.0,.65,.08,1.0))
		var hit=impact.get("point_local",[])
		var incoming=impact.get("incoming_local",[])
		if hit is Array and hit.size()>=3 and incoming is Array and incoming.size()>=3:
			var origin=Vector3(float(hit[0]),float(hit[1]),float(hit[2]))
			var direction=Vector3(float(incoming[0]),float(incoming[1]),float(incoming[2])).normalized()
			var penetrated=bool(impact.get("penetrated",false))
			path_start=origin-direction*1.8
			path_end=origin+direction*(2.4 if penetrated else .08)
			shot_elapsed=0.0
			_add_marker(origin,.16,Color(1.0,.95,.6,1.0))
			_add_beam(path_start,origin,Color(1.0,.38,.10,.92))
			if penetrated:
				_add_beam(origin,path_end,Color(1.0,.76,.18,.9))
				for key in damaged:
					if not centers.has(key):continue
					var xyz=centers[key]
					if xyz is Array and xyz.size()>=3:
						_add_beam(origin+direction*.15,Vector3(float(xyz[0]),float(xyz[1]),float(xyz[2])),Color(1.0,.38,.12,.65))
			projectile=_add_marker(path_start,.11,Color(1.0,.96,.55,1.0))
			var view=(-direction+Vector3(0,.43,0)).normalized()
			var side=view.cross(Vector3.UP).normalized()
			camera.position=model.to_global(Vector3(0,.8,0)+view*6.8+side*5.8)
			camera.look_at(model.to_global(Vector3(0,.9,0)))
			var hit_modules={}
			for key in damaged:
				if not centers.has(key):continue
				var xyz=centers[key]
				if xyz is Array and xyz.size()>=3:hit_modules[key]=Vector3(float(xyz[0]),float(xyz[1]),float(xyz[2]))
			overlay.set_impact(model,camera,Vector2(viewport.size),path_start,origin,path_end,hit_modules)
		model.rotation.y=deg_to_rad(-26)

	func _apply_xray(root: Node3D):
		var ghost=StandardMaterial3D.new()
		ghost.albedo_color=Color(.65,.91,.86,.51)
		ghost.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
		ghost.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		ghost.depth_draw_mode=BaseMaterial3D.DEPTH_DRAW_DISABLED
		ghost.cull_mode=BaseMaterial3D.CULL_DISABLED
		for node in root.find_children("*","MeshInstance3D",true,false):
			(node as MeshInstance3D).material_override=ghost

	func _add_marker(point: Vector3,radius: float,colour: Color) -> MeshInstance3D:
		var marker=MeshInstance3D.new()
		marker.name="DamageMarker"
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
		model.add_child(marker)
		return marker

	func _add_beam(from: Vector3,to: Vector3,colour: Color):
		var delta=to-from
		if delta.length()<.001:return
		var beam=MeshInstance3D.new()
		beam.name="ImpactPath"
		var cylinder=CylinderMesh.new()
		cylinder.top_radius=.055
		cylinder.bottom_radius=.055
		cylinder.height=delta.length()
		beam.mesh=cylinder
		beam.position=(from+to)*.5
		var material=StandardMaterial3D.new()
		material.albedo_color=colour
		material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled=true
		material.emission=colour
		material.emission_energy_multiplier=2.0
		beam.material_override=material
		model.add_child(beam)
		beam.look_at(model.to_global(to),Vector3.UP)
		beam.rotate_object_local(Vector3.RIGHT,PI/2)

var title: Label
var model_view: ImpactModelView
var body: Label
var source_id=-1
var remaining=0.0
const DISPLAY_SECONDS=4.0

func _ready():
	set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	offset_left=-610
	offset_right=-20
	offset_top=-465
	offset_bottom=-95
	custom_minimum_size=Vector2(590,370)
	size=custom_minimum_size
	var battle=get_parent().get_parent() if get_parent()!=null and get_parent().get_parent()!=null else null
	var demo_layout=battle!=null and battle.get("is_demo")==true
	if demo_layout:
		set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
		offset_left=410
		offset_right=780
		offset_top=-390
		offset_bottom=-130
		custom_minimum_size=Vector2(370,260)
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
	title.add_theme_font_size_override("font_size",11)
	title.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	title.add_theme_color_override("font_color",Color("ead58f"))
	column.add_child(title)
	model_view=ImpactModelView.new()
	model_view.custom_minimum_size=Vector2(350,145) if demo_layout else Vector2(560,235)
	model_view.size_flags_vertical=Control.SIZE_EXPAND_FILL
	column.add_child(model_view)
	body=Label.new()
	body.add_theme_font_size_override("font_size",11)
	body.add_theme_color_override("font_color",Color("edf0e8"))
	body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	column.add_child(body)
	hide()

func _process(delta: float):
	if not visible:return
	remaining=maxf(0.0,remaining-delta)
	if remaining<=0.0:hide()

func dismiss():
	remaining=0.0
	source_id=-1
	hide()

func show_impact(event: Dictionary):
	var impact: Dictionary=event.get("impact",{})
	var russian=str(AppState.settings.language)=="ru"
	var vehicle_name=str(event.get("vehicle","vehicle"))
	source_id=int(event.get("source_id",-1))
	remaining=DISPLAY_SECONDS
	var source_name=str(event.get("source_name",""))
	var target_name=str(event.get("target_name",vehicle_name))
	var shell_name=str(event.get("shell",impact.get("shell","unknown")))
	var penetrated=bool(impact.get("penetrated",false))
	title.text=("ПОПАДАНИЕ  %s → %s" if russian else "HIT  %s → %s") % [source_name,target_name]
	var outcome=str(impact.get("outcome",""))
	var result="STOPPED"
	if penetrated:result="ПРОБИТИЕ" if russian else "PENETRATED"
	elif bool(impact.get("ricochet",false)):result="РИКОШЕТ" if russian else "RICOCHET"
	elif russian:result="НЕ ПРОБИЛО"
	var state="ТЕХНИКА УНИЧТОЖЕНА" if russian and outcome=="lethal" else ("VEHICLE DESTROYED" if outcome=="lethal" else ("КРИТИЧЕСКИЙ УРОН" if russian and outcome=="critical" else ("CRITICAL DAMAGE" if outcome=="critical" else "")))
	var damaged=impact.get("damaged",[])
	var disabled=impact.get("disabled",[])
	var casualties="%s / %s" % [str(impact.get("crew_alive","—")),str(impact.get("crew_total","—"))]
	var modules=" · ".join(PackedStringArray(damaged.map(func(v):return str(v).replace("_"," ")))) if damaged is Array else ""
	var disabled_text=" · ".join(PackedStringArray(disabled.map(func(v):return str(v).replace("_"," ")))) if disabled is Array else ""
	var damage_label=("повреждены" if russian else "damaged")+": "+(modules if not modules.is_empty() else ("—" if russian else "—"))
	var disabled_label=("выведены" if russian else "disabled")+": "+(disabled_text if not disabled_text.is_empty() else "—")
	body.text="%s · %s\n%s %s · %.0f / %.0f mm\n%s\n%s\n%s · %s %s" % [shell_name,result,"БРОНЯ" if russian else "ARMOUR",str(impact.get("zone","?")),float(impact.get("capability",0.0)),float(impact.get("effective",0.0)),damage_label,disabled_label,state if not state.is_empty() else vehicle_name,"ЭКИПАЖ" if russian else "CREW",casualties]
	model_view.show_event(event)
	show()
