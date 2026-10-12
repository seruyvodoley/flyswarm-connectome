extends Node3D

const TerrainScript=preload("res://scripts/terrain.gd")
const Appearance=preload("res://scripts/vehicles/vehicle_appearance.gd")
const VEHICLES=["panther_g","tiger_i","jagdpanther","t34_85","is2_1944","su100"]
var replay_path=""
var frames:Array=[]
var tanks:Array=[]
var camera:Camera3D
var frame_index=0
var elapsed=0.0
var playing=true
var play_speed=1.0
var selected_agent=0
var camera_mode="strategic"
var yaw=0.0
var pitch=-.48
var zoom=750.0
var status:Label
var details:Label
var zones_root:Node3D
var terrain
var event_cursor=-1
var effect_nodes:Array=[]

func _ready():
	replay_path=AppState.marl_replay_path
	_build_world()
	_build_ui()
	_load_replay()

func _build_world():
	var env=WorldEnvironment.new();var environment=Environment.new();environment.background_mode=Environment.BG_COLOR;environment.background_color=Color(.48,.61,.70)
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.ambient_light_color=Color(.62,.69,.75);environment.ambient_light_energy=.65;environment.tonemap_mode=Environment.TONE_MAPPER_FILMIC;environment.fog_enabled=true;environment.fog_light_color=Color(.69,.73,.67);environment.fog_density=.0004;env.environment=environment;add_child(env)
	var sun=DirectionalLight3D.new();sun.rotation=Vector3(deg_to_rad(-52),deg_to_rad(-28),0);sun.light_energy=1.25;sun.shadow_enabled=true;add_child(sun)
	terrain=TerrainScript.new();terrain.vegetation_density=.62;terrain.forest_center=Vector2(540,540);terrain.forest_radius=145;add_child(terrain);terrain.build(false,1944,1500)
	zones_root=Node3D.new();zones_root.name="RecordedObjectives";add_child(zones_root)
	for index in 3:
		var marker=MeshInstance3D.new();var cylinder=CylinderMesh.new();cylinder.top_radius=53;cylinder.bottom_radius=53;cylinder.height=.3;marker.mesh=cylinder
		var mat=StandardMaterial3D.new();mat.albedo_color=Color(.9,.75,.25,.34);mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;marker.material_override=mat;marker.position=Vector3((index-1)*240,.2,0);zones_root.add_child(marker)
	camera=Camera3D.new();camera.current=true;camera.fov=57;camera.environment=environment;add_child(camera)

func _build_ui():
	var layer=CanvasLayer.new();add_child(layer)
	var panel=PanelContainer.new();panel.position=Vector2(20,18);panel.custom_minimum_size=Vector2(440,135);layer.add_child(panel)
	var col=VBoxContainer.new();panel.add_child(col)
	status=Label.new();status.text=_tr("Загрузка Python-траектории…","Loading recorded Python state…");status.add_theme_font_size_override("font_size",19);col.add_child(status)
	details=Label.new();details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;col.add_child(details)
	var controls=HBoxContainer.new();col.add_child(controls)
	_button(controls,"◀ 10",func():_seek(-10));_button(controls,_tr("Пауза / Пуск","Pause / Play"),func():playing=not playing)
	_button(controls,"10 ▶",func():_seek(10));_button(controls,"−",func():play_speed=maxf(.25,play_speed*.5));_button(controls,"+",func():play_speed=minf(4.,play_speed*2.))
	var cameras=HBoxContainer.new();col.add_child(cameras)
	_button(cameras,_tr("Обзор","Strategic"),func():camera_mode="strategic");_button(cameras,_tr("Следовать","Follow selected"),func():camera_mode="follow");_button(cameras,_tr("Наводчик","Gunner"),func():camera_mode="gunner");_button(cameras,_tr("Свободная","Free"),func():camera_mode="free")
	var select=OptionButton.new();select.size_flags_horizontal=Control.SIZE_EXPAND_FILL;cameras.add_child(select)
	for i in 16:select.add_item("%s · %s" % [_tr("СИНИЕ" if i<8 else "КРАСНЫЕ","BLUE" if i<8 else "RED"),str(i%8+1)])
	select.item_selected.connect(func(i):selected_agent=i)
	var exit_button=Button.new();exit_button.text=_tr("Назад в лабораторию MARL","Back to MARL Laboratory");exit_button.anchor_left=.72;exit_button.anchor_right=.99;exit_button.anchor_top=.025;exit_button.anchor_bottom=.08;exit_button.pressed.connect(func():AppState.show_page("MarlLaboratory"));layer.add_child(exit_button)
func _button(parent:Node,caption:String,action:Callable):
	var b=Button.new();b.text=caption;b.pressed.connect(action);parent.add_child(b)
func _tr(ru:String,en:String)->String:return ru if str(AppState.settings.get("language","en"))=="ru" else en

func _load_replay():
	if not FileAccess.file_exists(replay_path):status.text=_tr("Файл повтора недоступен: ","Replay file is unavailable: ")+replay_path;return
	var file=FileAccess.open(replay_path,FileAccess.READ)
	while not file.eof_reached():
		var line=file.get_line()
		if line.strip_edges()=="":continue
		var parsed=JSON.parse_string(line)
		if parsed is Dictionary and parsed.get("kind","")=="frame" and parsed.has("agents"):frames.append(parsed)
	file.close()
	if frames.is_empty():status.text=_tr("В повторе нет кадров состояния","No valid state frames in replay");return
	var initial=frames[0]
	for index in 16:
		var record=initial.agents[index];var vehicle_id=str(record.get("vehicle_id","tiger_i"))
		if vehicle_id not in VEHICLES:vehicle_id="tiger_i"
		var root=Node3D.new();root.name=str(record.agent_id);add_child(root)
		var model=load("res://assets/vehicles/"+vehicle_id+".glb").instantiate();root.add_child(model);Appearance.apply(model,vehicle_id)
		var turret=model.find_child("TurretPivot",true,false);var gun=model.find_child("GunElevationPivot",true,false)
		var wheels=model.find_children("Wheel*","MeshInstance3D",true,false)
		var label=Label3D.new();label.text=("B" if index<8 else "R")+str(index%8+1);label.position=Vector3(0,5,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.modulate=Color("72adff") if index<8 else Color("ef7959");root.add_child(label)
		var alive=bool(record.get("alive",true))
		if not alive:Appearance.apply(model,vehicle_id,true)
		tanks.append({"root":root,"model":model,"turret":turret,"gun":gun,"wheels":wheels,"alive":alive,"vehicle_id":vehicle_id})
	_apply_frame(0)
	status.text=_tr("АНАЛИТИЧЕСКИЙ ПОВТОР · %d кадров · %s","ANALYTICAL REPLAY · %d frames · %s") % [frames.size(),str(initial.get("run_id",initial.get("seed","seed ?")))]

func _process(delta):
	if frames.is_empty():return
	for effect in effect_nodes:
		effect.time_left-=delta
		if effect.time_left<=0 and is_instance_valid(effect.node):effect.node.queue_free()
	effect_nodes=effect_nodes.filter(func(effect):return effect.time_left>0)
	if playing:
		elapsed+=delta*play_speed
		while frame_index<frames.size()-1 and elapsed>=float(frames[frame_index+1].get("sim_time_s",0)):
			frame_index+=1;_apply_frame(frame_index)
		if frame_index>=frames.size()-1:playing=false
		for entry in tanks:
			var rotation_amount=float(entry.root.get_meta("speed",0.))*delta/1.2
			for wheel in entry.wheels:
				if is_instance_valid(wheel):wheel.rotate_x(rotation_amount)
	_update_camera()
func _seek(amount:int):
	frame_index=clampi(frame_index+amount,0,frames.size()-1);elapsed=float(frames[frame_index].get("sim_time_s",0));_apply_frame(frame_index)
func _apply_frame(index:int):
	if index<0 or index>=frames.size():return
	var frame=frames[index]
	for i in mini(16,frame.agents.size()):
		var state=frame.agents[i];var entry=tanks[i];var pos=state.position_m
		entry.root.position=Vector3(float(pos[0]),terrain.height_at(float(pos[0]),float(pos[1]))+0.08,float(pos[1]))
		entry.root.rotation.y=PI*.5-float(state.heading_rad)
		if is_instance_valid(entry.turret):entry.turret.rotation.y=-float(state.turret_heading_rad)
		if is_instance_valid(entry.gun):entry.gun.rotation.x=-float(state.gun_elevation_rad)
		entry.root.set_meta("speed",float(state.speed_m_s))
		if entry.alive!=bool(state.alive):
			entry.alive=bool(state.alive)
			Appearance.apply(entry.model,entry.vehicle_id,not entry.alive)
			if not entry.alive:_emit_destruction(entry.root)
		if is_instance_valid(entry.root.get_node_or_null("Label3D")):entry.root.get_node("Label3D").text=("B" if i<8 else "R")+str(i%8+1)+(" ×" if not entry.alive else "")
	if event_cursor!=index:
		event_cursor=index
		_show_recorded_effects(frame)
	status.text=_tr("%s  ·  такт %d / %d  ·  %.1f с  ·  %.2fx","%s  ·  tick %d / %d  ·  %.1f s  ·  %.2fx") % [_tr("ИДЁТ" if playing else "ПАУЗА","PLAYING" if playing else "PAUSED"),int(frame.tick),frames.size()-1,float(frame.sim_time_s),play_speed]
	var agent=frame.agents[selected_agent];var team=_tr("СИНИЕ","BLUE") if selected_agent<8 else _tr("КРАСНЫЕ","RED")
	var zones=[]
	for zone in frame.get("zones",[]):zones.append("%s:%s" % [zone.zone_id,str(zone.owner if zone.owner!=null else "—")])
	var recent=frame.get("events",[]);var event_text=""
	for event in recent:
		if event.get("type","") in ["shot","damage","destroyed"]:event_text+="\n"+str(event.get("type"))+" "+str(event.get("agent_id"))+" → "+str(event.get("target_id"))+" · damage "+str(event.get("damage",0))
	details.text=_tr("%s · %s · прочность %.2f · скорость %.1f м/с · награда %.3f\nБилеты %s   Точки %s%s","%s · %s · HP %.2f · speed %.1f m/s · reward %.3f\nTickets %s   Objectives %s%s") % [team,str(agent.vehicle_id),float(agent.health),float(agent.speed_m_s),float(agent.reward),str(frame.get("tickets",{})),"  ".join(zones),event_text]

func _update_camera():
	if camera_mode=="follow" and tanks.size()>selected_agent:
		var target:Node3D=tanks[selected_agent].root
		var forward=Vector3(sin(target.rotation.y),0,cos(target.rotation.y))
		var follow_distance=clampf(zoom*.025,12.,48.)
		camera.global_position=target.global_position-forward*follow_distance+Vector3(0,follow_distance*.32,0)
		camera.look_at(target.global_position+Vector3(0,2,0),Vector3.UP)
	elif camera_mode=="gunner" and tanks.size()>selected_agent:
		var target:Node3D=tanks[selected_agent].root
		var turret:Node3D=tanks[selected_agent].turret
		var yaw_world=target.rotation.y+(turret.rotation.y if is_instance_valid(turret) else 0.)
		var direction=Vector3(sin(yaw_world),0,cos(yaw_world))
		camera.global_position=target.global_position+Vector3(0,2.1,0)+direction*1.4
		camera.look_at(camera.global_position+direction*100,Vector3.UP)
	elif camera_mode=="strategic":
		camera.position=Vector3(0,zoom*.8,zoom*.45);camera.look_at(Vector3.ZERO,Vector3.UP)
	elif camera_mode=="free":
		var direction=Vector3(cos(pitch)*sin(yaw),sin(pitch),cos(pitch)*cos(yaw))
		camera.position=Vector3.ZERO-direction*zoom*.7;camera.look_at(Vector3.ZERO,Vector3.UP)

func _unhandled_input(event):
	if event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:zoom=maxf(80,zoom*.85)
		if event.button_index==MOUSE_BUTTON_WHEEL_DOWN:zoom=minf(1500,zoom*1.15)
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		camera_mode="free";yaw-=event.relative.x*.004;pitch=clampf(pitch-event.relative.y*.004,-1.3,-.08)

func _show_recorded_effects(frame:Dictionary):
	for event in frame.get("events",[]):
		if event.get("type","")!="shot":continue
		var source=_agent_index(str(event.get("agent_id","")));var target=_agent_index(str(event.get("target_id","")))
		if source<0 or target<0:continue
		var from:Vector3=tanks[source].root.global_position+Vector3(0,2,0)
		var to:Vector3=tanks[target].root.global_position+Vector3(0,2,0)
		var delta=to-from
		if delta.length()<.01:continue
		var tracer=MeshInstance3D.new();var mesh=CylinderMesh.new();mesh.top_radius=.12;mesh.bottom_radius=.12;mesh.height=delta.length();tracer.mesh=mesh
		var material=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.albedo_color=Color("ffd37b") if bool(event.get("hit",false)) else Color("aebbc1");material.emission_enabled=true;material.emission=material.albedo_color;tracer.material_override=material
		add_child(tracer);tracer.global_position=(from+to)*.5;tracer.global_basis=Basis(Quaternion(Vector3.UP,delta.normalized()));effect_nodes.append({"node":tracer,"time_left":.11})
		if bool(event.get("hit",false)):
			var marker=Label3D.new();marker.text="ANALYTICAL DAMAGE  +%.2f" % float(event.get("damage",0));marker.billboard=BaseMaterial3D.BILLBOARD_ENABLED;marker.modulate=Color("ffd37b");marker.position=Vector3(0,7,0);tanks[target].root.add_child(marker);effect_nodes.append({"node":marker,"time_left":1.4})

func _agent_index(identifier:String)->int:
	if identifier.begins_with("blue_"):return clampi(identifier.trim_prefix("blue_").to_int(),0,7)
	if identifier.begins_with("red_"):return 8+clampi(identifier.trim_prefix("red_").to_int(),0,7)
	return -1

func _emit_destruction(parent:Node3D):
	var particles=CPUParticles3D.new();particles.amount=36;particles.lifetime=1.1;particles.one_shot=true;particles.explosiveness=.88;particles.direction=Vector3.UP;particles.spread=76;particles.gravity=Vector3(0,1.5,0);particles.initial_velocity_min=3.;particles.initial_velocity_max=9.;particles.scale_amount_min=.22;particles.scale_amount_max=.62;particles.color=Color("e99342")
	var sphere=SphereMesh.new();sphere.radius=.25;sphere.height=.5;var material=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;material.albedo_color=Color(1,.48,.19,.82);particles.mesh=sphere;particles.material_override=material;particles.position=Vector3(0,1,0);parent.add_child(particles);particles.finished.connect(particles.queue_free);particles.emitting=true
