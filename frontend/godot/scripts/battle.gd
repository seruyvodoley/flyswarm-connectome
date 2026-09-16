extends Node3D
signal completed(report)
signal pause_requested
signal backend_failed(message)
var session_config
var launch_args=PackedStringArray()
var is_range=false
var replay_buffer=[]
var report_cache={}
var progress_clock=0.0

const Catalog=preload("res://scripts/catalog.gd")
const Terrain=preload("res://scripts/terrain.gd")
const Vehicle=preload("res://scripts/vehicle.gd")
const Bridge=preload("res://scripts/bridge.gd")
var terrain
var tracks
var vehicles=[]
var objectives=[]
var tickets=[300.0,300.0]
var shells=[]
var effects=[]
var scenario={}
var bridge=Bridge.new()
var sim_time=0.0
var frame=0
var selected=0
var camera_mode=1
var last_camera_mode=-1
var observer_environment: Environment
var camera: Camera3D
var camera_button: Button
var battlefield_pan=Vector2.ZERO
var battlefield_zoom=1600.0

var comm_view=0 # 0 off, 1 red, 2 blue, 3 all
var comm_toggle: Button
var comm_panel: PanelContainer
var comm_title: Label
var comm_text: RichTextLabel
var comm_links: MeshInstance3D
var comm_line_material: StandardMaterial3D
var comm_history=[]
var comm_last_sample=-1
var comm_last_link={}
var replay_communication={}
var hud: Label
var detail: Label
var debug=false
var sensor_debug: MeshInstance3D
var replay_shell_nodes=[]
var normalized=false
var audio_mode="no_audio"
var training=false
var time_limit=600.0
var record_path=""
var recorder: FileAccess
var start_wall=0
var physics_usec=0.0
var rng=RandomNumberGenerator.new()
var paused=false
var requires_brain=false
var replay=[]
var replay_index=0
var replay_clock=0.0
var replay_mode=false
var free_yaw=0.0
var free_pitch=-.3
var ended=false
var finished_report=false
var shot_distances=[]
var capture_changes=0
var objective_captures=[0,0]
var objective_neutralizations=[0,0]
var screenshot_path=""

# ============================================================
# TEST RANGE KILLCAM / HIT FEEDBACK
# ============================================================

var range_feedback: Label
var range_feedback_timer=0.0

var range_killcam_active=false
var range_killcam_elapsed=0.0
var range_killcam_duration=3.6
var range_killcam_target=8
var range_killcam_saved_camera=1
var range_target_destroyed=false

var range_killcam_panel: PanelContainer
var range_killcam_title: Label
var range_killcam_body: Label
var range_killcam_path: MeshInstance3D

func option(name: String, fallback: String="") -> String:
	var args=launch_args if session_config!=null else OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i]==name:return args[i+1]
	return fallback
func has(name: String) -> bool:return name in (launch_args if session_config!=null else OS.get_cmdline_user_args())
func _ready():
	if session_config!=null:
		launch_args=session_config.cli_args()
		debug=AppState.settings.debug or session_config.range_mode in ["armour","modules"]
	start_wall=Time.get_ticks_usec()
	camera_mode=int(option("--camera","1"))
	normalized=has("--normalized")
	training=has("--training")
	is_range=has("--range") or (session_config!=null and session_config.map=="test_range")
	# Autonomous battles open in a true battlefield overview. Test range keeps
	# the normal third-person follow camera.
	if session_config!=null and not has("--camera"):
		camera_mode=1 if is_range else 0
	requires_brain=has("--connect")
	audio_mode=option("--audio","no_audio")
	scenario=Catalog.read_json("scenarios/"+("training_range" if training else "krasny_valley")+".json")
	scenario.seed=int(option("--seed",str(scenario.seed)))
	if is_range:scenario.size_m=2200
	var replay_manifest={}
	if has("--replay"):
		var manifest_path=option("--replay").get_base_dir().path_join("manifest.json")
		if FileAccess.file_exists(manifest_path):replay_manifest=JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		audio_mode=str(replay_manifest.get("audio",audio_mode))
		if replay_manifest.get("map","").contains("Training"):
			training=true
			scenario=Catalog.read_json("scenarios/training_range.json")
		if replay_manifest.has("vehicles") and replay_manifest.vehicles.size()==16:
			for i in range(8):
				scenario.blue[i]=replay_manifest.vehicles[i].id
				scenario.red[i]=replay_manifest.vehicles[i+8].id
		scenario.seed=int(replay_manifest.get("map_seed",scenario.seed))
	time_limit=float(option("--seconds",str(scenario.time_limit_s)))
	rng.seed=int(option("--battle-seed",str(scenario.seed)))
	tickets=[float(scenario.tickets),float(scenario.tickets)]
	terrain=Terrain.new()
	add_child(terrain)
	terrain.range_flat=is_range
	terrain.mobility_course=is_range and session_config!=null and session_config.range_mode=="mobility"
	terrain.vegetation_density=AppState.settings.vegetation if session_config!=null else 1.0
	terrain.build(training,int(scenario.seed),float(scenario.size_m))
	tracks=load("res://scripts/tracks.gd").new()
	add_child(tracks)
	tracks.setup(self)
	var sky=WorldEnvironment.new()
	var env=Environment.new()
	env.background_mode=Environment.BG_SKY
	var sky_res=Sky.new()
	var sky_mat=ProceduralSkyMaterial.new()
	sky_mat.sky_top_color=Color(.23,.36,.48)
	sky_mat.sky_horizon_color=Color(.69,.73,.67)
	sky_res.sky_material=sky_mat
	env.sky=sky_res
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color=Color(.62,.69,.75)
	env.ambient_light_energy=.65
	env.tonemap_mode=Environment.TONE_MAPPER_FILMIC
	env.fog_enabled=true
	env.fog_density=.00018
	env.fog_light_color=Color(.61,.68,.65)
	observer_environment=env
	sky.environment=env
	add_child(sky)
	var sun=DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-42,-28,0)
	sun.light_color=Color(1,.92,.77)
	sun.light_energy=1.7
	sun.shadow_enabled=AppState.settings.shadows if session_config!=null else true
	sun.directional_shadow_max_distance=300
	add_child(sun)
	for i in range(3):
		var v=scenario.objectives[i]
		var pos=Vector3(v[0],terrain.height_at(v[0],v[1]),v[1])
		objectives.append({"position":pos,"owner":-1,"progress":0.0,"contested":false,"inside":[0,0]})
		var marker=MeshInstance3D.new()
		var mesh=CylinderMesh.new()
		mesh.top_radius=scenario.zone_radius
		mesh.bottom_radius=scenario.zone_radius
		mesh.height=.14
		mesh.radial_segments=48
		marker.mesh=mesh
		marker.position=pos+Vector3(0,.3,0)
		marker.material_override=terrain.material(Color(.33,.37,.31))
		add_child(marker)
		var label=Label3D.new()
		label.text=["A","B","C"][i]
		label.font_size=120
		label.pixel_size=.08
		label.position=pos+Vector3(0,18,0)
		label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
		label.fixed_size=false
		label.name="ObjectiveLabel"+str(i)
		label.font_size=36
		label.outline_size=4
		add_child(label)
		objectives[i].marker=marker
		objectives[i].label=label
		update_objective_visual(i)
	for i in range(16):
		var team=int(i/8)
		var id=scenario.blue[i%8] if team==0 else scenario.red[i%8]
		id=option("--mirror",id)
		if is_range and session_config!=null:id=session_config.training_vehicle if team==0 else session_config.target_vehicle
		var tank=Vehicle.new()
		add_child(tank)
		tank.setup(Catalog.vehicle(id,normalized),i,self)
		var sign_value=(-1 if team==0 else 1)*(-1 if has("--swap") else 1)
		var x=(i%8-3.5)*scenario.spawn_spacing
		var z=scenario.spawn_z*sign_value
		tank.position=Vector3(x,terrain.height_at(x,z)+.1,z)
		tank.rotation.y=0 if sign_value<0 else PI
		vehicles.append(tank)
		if is_range:
			if i in [0,8]:
				var distance=session_config.range_distance if session_config!=null else 500
				tank.position=Vector3(0,.1,(-.5 if i==0 else .5)*distance)
				tank.rotation.y=0 if i==0 else PI+deg_to_rad(session_config.target_angle if session_config!=null else 0)
			else:
				tank.alive=false; tank.hide();tank.position=Vector3(1500+i*20,-100,1500)
				tank.collision_layer=0; tank.collision_mask=0
				for plate in tank.armour_bodies:plate.collision_layer=0
		if session_config!=null:
			for mesh in tank.model.find_children("*","GeometryInstance3D",true,false):mesh.lod_bias=AppState.settings.lod

	sensor_debug=MeshInstance3D.new()
	add_child(sensor_debug)
	camera=Camera3D.new()
	camera.far=4000
	camera.near=.1
	camera.fov=62
	add_child(camera)
	camera.position=Vector3(170,140,-250)
	camera.look_at(Vector3(0,0,0))
	var canvas=CanvasLayer.new()
	add_child(canvas)
	hud=Label.new()
	hud.position=Vector2(24,18)
	hud.add_theme_font_size_override("font_size",14)
	hud.size.x=430
	hud.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	hud.add_theme_color_override("font_shadow_color",Color.BLACK)
	hud.add_theme_constant_override("shadow_offset_x",2)
	hud.add_theme_constant_override("shadow_offset_y",2)
	var backdrop=ColorRect.new()
	backdrop.color=Color(.025,.04,.05,.78)
	backdrop.position=Vector2(12,10)
	backdrop.size=Vector2(455,290)
	backdrop.mouse_filter=Control.MOUSE_FILTER_IGNORE
	canvas.add_child(backdrop)
	canvas.add_child(hud)
	detail=Label.new()
	detail.position=Vector2(24,155)
	detail.size.x=430
	detail.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	detail.add_theme_font_size_override("font_size",12)
	canvas.add_child(detail)

	# --------------------------------------------------------
	# Test Range hit feedback / killcam UI
	# --------------------------------------------------------

	range_feedback=Label.new()
	range_feedback.set_anchors_preset(Control.PRESET_CENTER_TOP)
	range_feedback.offset_left=-310
	range_feedback.offset_right=310
	range_feedback.offset_top=82
	range_feedback.offset_bottom=132
	range_feedback.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	range_feedback.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	range_feedback.add_theme_font_size_override("font_size",22)
	range_feedback.add_theme_color_override("font_shadow_color",Color.BLACK)
	range_feedback.add_theme_constant_override("shadow_offset_x",2)
	range_feedback.add_theme_constant_override("shadow_offset_y",2)
	range_feedback.visible=false
	canvas.add_child(range_feedback)

	range_killcam_panel=PanelContainer.new()
	range_killcam_panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	range_killcam_panel.offset_left=-330
	range_killcam_panel.offset_right=330
	range_killcam_panel.offset_top=-225
	range_killcam_panel.offset_bottom=-28
	range_killcam_panel.visible=false

	var killcam_style=StyleBoxFlat.new()
	killcam_style.bg_color=Color(.025,.035,.04,.92)
	killcam_style.border_color=Color(.62,.54,.36,.9)
	killcam_style.set_border_width_all(1)
	killcam_style.set_corner_radius_all(5)
	killcam_style.content_margin_left=20
	killcam_style.content_margin_right=20
	killcam_style.content_margin_top=14
	killcam_style.content_margin_bottom=14
	range_killcam_panel.add_theme_stylebox_override("panel",killcam_style)

	var killcam_box=VBoxContainer.new()
	killcam_box.add_theme_constant_override("separation",8)
	range_killcam_panel.add_child(killcam_box)

	range_killcam_title=Label.new()
	range_killcam_title.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	range_killcam_title.add_theme_font_size_override("font_size",28)
	killcam_box.add_child(range_killcam_title)

	range_killcam_body=Label.new()
	range_killcam_body.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	range_killcam_body.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	range_killcam_body.add_theme_font_size_override("font_size",16)
	killcam_box.add_child(range_killcam_body)

	var reset_target_button=Button.new()
	reset_target_button.text=AppState.tr_text("RESET TARGET")
	reset_target_button.custom_minimum_size.y=40
	reset_target_button.pressed.connect(reset_range_target)
	killcam_box.add_child(reset_target_button)

	canvas.add_child(range_killcam_panel)

	range_killcam_path=MeshInstance3D.new()
	range_killcam_path.visible=false
	add_child(range_killcam_path)

	# Clickable observer controls.
	camera_button=Button.new()
	camera_button.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	camera_button.offset_left=-440
	camera_button.offset_right=-225
	camera_button.offset_top=18
	camera_button.offset_bottom=62
	camera_button.pressed.connect(cycle_camera)
	canvas.add_child(camera_button)

	comm_toggle=Button.new()
	comm_toggle.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	comm_toggle.offset_left=-215
	comm_toggle.offset_right=-18
	comm_toggle.offset_top=18
	comm_toggle.offset_bottom=62
	comm_toggle.pressed.connect(cycle_comms)
	comm_toggle.visible=not is_range
	canvas.add_child(comm_toggle)

	comm_panel=PanelContainer.new()
	comm_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	comm_panel.offset_left=-460
	comm_panel.offset_right=-18
	comm_panel.offset_top=72
	comm_panel.offset_bottom=570

	var comm_style=StyleBoxFlat.new()
	comm_style.bg_color=Color(.025,.04,.05,.93)
	comm_style.border_color=Color(.35,.43,.40)
	comm_style.set_border_width_all(1)
	comm_style.set_corner_radius_all(4)
	comm_style.content_margin_left=14
	comm_style.content_margin_right=14
	comm_style.content_margin_top=12
	comm_style.content_margin_bottom=12
	comm_panel.add_theme_stylebox_override("panel",comm_style)

	var comm_box=VBoxContainer.new()
	comm_box.add_theme_constant_override("separation",8)
	comm_panel.add_child(comm_box)

	comm_title=Label.new()
	comm_title.add_theme_font_size_override("font_size",20)
	comm_box.add_child(comm_title)

	var disclaimer=Label.new()
	disclaimer.text=AppState.tr_text("Interface shows physical/neural signal telemetry, not decoded language.")
	disclaimer.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	disclaimer.modulate=Color(.68,.74,.70)
	comm_box.add_child(disclaimer)

	comm_text=RichTextLabel.new()
	comm_text.bbcode_enabled=false
	comm_text.fit_content=false
	comm_text.scroll_active=true
	comm_text.scroll_following=true
	comm_text.size_flags_vertical=Control.SIZE_EXPAND_FILL
	comm_text.custom_minimum_size=Vector2(390,390)
	comm_box.add_child(comm_text)

	canvas.add_child(comm_panel)

	comm_links=MeshInstance3D.new()
	add_child(comm_links)
	comm_line_material=StandardMaterial3D.new()
	comm_line_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	comm_line_material.vertex_color_use_as_albedo=true

	update_camera_button()
	refresh_comm_panel()

	if requires_brain: bridge.connect_backend(int(option("--port","8765")))
	record_path=option("--record","")
	if record_path!="":
		DirAccess.make_dir_recursive_absolute(record_path)
		if (session_config==null and not has("--no-replay")) or (session_config!=null and session_config.record):recorder=FileAccess.open(record_path.path_join("replay.jsonl"),FileAccess.WRITE)
		var manifest={"date":Time.get_datetime_string_from_system(true),"map":scenario.name,"map_seed":scenario.seed,"mode":"NORMALIZED" if normalized else "HISTORICAL","audio":audio_mode,"controller":"backend" if requires_brain else "RULE_BASED_CONTROL","side_swap":has("--swap"),"vehicles":[],"seconds":time_limit}
		var output=[]
		OS.execute("git",["-C",ProjectSettings.globalize_path("res://../.."),"rev-parse","HEAD"],output)
		manifest.git_commit="".join(output).strip_edges()
		output=[]
		OS.execute("git",["-C",ProjectSettings.globalize_path("res://../.."),"status","--porcelain"],output)
		manifest.git_dirty=not "".join(output).strip_edges().is_empty()
		if session_config!=null:manifest.session=session_config.as_dict()
		manifest.engine=Engine.get_version_info()
		manifest.source_hashes={}
		for source in ["battle.gd","vehicle.gd","terrain.gd","tracks.gd","combat.gd","bridge.gd","catalog.gd"]:
			manifest.source_hashes[source]=FileAccess.get_sha256("res://scripts/"+source)
		for v in vehicles:manifest.vehicles.append(v.cfg)
		FileAccess.open(record_path.path_join("manifest.json"),FileAccess.WRITE).store_string(JSON.stringify(manifest,"  "))
	var replay_file=option("--replay","")
	if replay_file!="":
		replay_mode=true
		var f=FileAccess.open(replay_file,FileAccess.READ)
		if f==null:
			if session_config!=null:backend_failed.emit("Replay file is missing")
			return
		while not f.eof_reached():
			var line=f.get_line()
			if line.strip_edges().is_empty():continue
			var row=JSON.parse_string(line)
			if row is Dictionary:replay.append(row)
		requires_brain=false
	print("READY ",scenario.name," 16 vehicles; ","NORMALIZED" if normalized else "HISTORICAL", " backend=",requires_brain)
	screenshot_path=option("--screenshot","")

func has_los(a,b) -> bool:
	var start=a.global_position+Vector3(0,2.5,0)
	var end=b.global_position+Vector3(0,1.7,0)
	if terrain.forest_blocks(start,end):return false
	var q=PhysicsRayQueryParameters3D.create(start,end,5,a.excluded())
	var hit=get_world_3d().direct_space_state.intersect_ray(q)
	return hit.is_empty() or (hit.collider.has_meta("vehicle") and hit.collider.get_meta("vehicle")==b)

func _physics_process(delta):
	if paused:return

	# Killcam is presentation-only. Freeze the manual range simulation while
	# the observer camera inspects the destroyed target.
	if is_range and range_killcam_active:
		return
	if replay_mode:
		replay_clock+=delta
		while replay_index<replay.size() and replay[replay_index].time<=replay_clock:
			var row=replay[replay_index]
			sim_time=row.time
			tickets=row.tickets
			replay_communication=row.get("communication",{}) if row.get("communication",{}) is Dictionary else {}
			ingest_communication(replay_communication)
			for state in row.vehicles:
				var v=vehicles[int(state.id)]
				v.position=Vector3(state.position[0],state.position[1],state.position[2])
				v.rotation.y=state.yaw
				v.turret.rotation.y=state.turret
				v.gun.rotation.x=-state.gun
				v.alive=state.alive
				v.metrics=state.get("metrics",v.metrics)
				v.turret_angle=state.turret
				v.gun_angle=state.gun
				v.modules=state.modules
			for n in replay_shell_nodes:n.queue_free()
			replay_shell_nodes=[]
			for xyz in row.get("projectiles",[]):
				var n=terrain.box(Vector3(xyz[0],xyz[1],xyz[2]),Vector3(.2,.2,.6),Color(1,.7,.2),false)
				replay_shell_nodes.append(n)
			for i in range(3):
				var zone_state=row.zones[i]
				objectives[i].owner=int(zone_state.get("owner",-1))
				objectives[i].progress=float(zone_state.get("progress",0.0))
				objectives[i].contested=zone_state.get("contested",false)
				var replay_inside=zone_state.get("inside",[0,0])
				objectives[i].inside=replay_inside.duplicate() if replay_inside is Array else [0,0]
				update_objective_visual(i)
			replay_index+=1
		if replay_index>=replay.size():
			if has("--quit"):get_tree().quit()
			elif session_config!=null and not finished_report:finish()

		return
	if ended or paused:return
	var started=Time.get_ticks_usec()
	bridge.poll()
	if requires_brain:
		if bridge.pending and (Time.get_ticks_usec()-bridge.sent_at)>10000000:
			push_error("Brain response timeout; no silent baseline fallback")
			if session_config!=null:paused=true;backend_failed.emit("No neural response for 10 seconds.")
			else:get_tree().quit(2)
			return
		if sim_time>0 and bridge.tcp.get_status()!=StreamPeerTCP.STATUS_CONNECTED and session_config!=null:
			paused=true;backend_failed.emit("Connection to the local brain server was lost.");return
		if bridge.commands.is_empty():
			if not bridge.pending:
				var observations=[]
				for v in vehicles:
					v.sense(.02)
					observations.append(v.observation())
				bridge.request(observations,audio_mode)
			if (Time.get_ticks_usec()-start_wall)>180000000 and sim_time==0:
				push_error("Brain backend timeout")
				if session_config!=null:paused=true;backend_failed.emit("Backend connection timed out.")
				else:get_tree().quit(2)
			return
		for i in range(16):
			vehicles[i].cmd=bridge.commands[i]
			vehicles[i].dn=bridge.last_reply.get("traces",[])[i]
			vehicles[i].audio_input=bridge.last_reply.get("heard",[])[i]
		ingest_communication(bridge.last_reply.get("communication",{}))
		bridge.commands=[]
		delta=.02
	for v in vehicles:
		if not requires_brain:
			if frame%5==0:v.sense(delta*5)
			v.cmd=v.teacher()
		if is_range:
			v.cmd=manual_commands() if v.agent_id==0 else [0,0,0,0,0,0]
		if training:
			v.cmd[0]=0
			v.cmd[2]=0
		v.step(delta)
	if is_range:
		vehicles[0].target=8
		vehicles[0].target_range=vehicles[0].position.distance_to(vehicles[8].position)
	step_shells(delta)
	if not is_range:step_objectives(delta)
	sim_time+=delta
	frame+=1
	physics_usec+=Time.get_ticks_usec()-started
	if frame%5==0:
		var row=JSON.stringify(snapshot())
		if recorder:recorder.store_line(row)
		elif session_config!=null and not replay_mode:
			replay_buffer.append(row)
			if replay_buffer.size()>6000:replay_buffer.pop_front()
	if record_path!="" and sim_time-progress_clock>=.5:
		progress_clock=sim_time
		FileAccess.open(record_path.path_join("live.json"),FileAccess.WRITE).store_string(JSON.stringify({"sim_time":sim_time,"wall_time":(Time.get_ticks_usec()-start_wall)/1000000.0}))

	var elimination_end = (
		minf(tickets[0], tickets[1]) <= 0 or
		alive_count(0) == 0 or
		alive_count(1) == 0
	)

	if sim_time>=time_limit or (not is_range and elimination_end):
		finish()

func fire(v):
	var p=v.muzzle.global_position
	var heading=v.rotation.y+v.turret_angle
	var angle=v.gun_angle
	var dispersion=float(v.cfg.gun_data.dispersion_mrad)*.001
	heading+=rng.randfn(0,dispersion)
	angle+=rng.randfn(0,dispersion)
	var dir=v.muzzle.global_basis.z.normalized()
	dir=dir.rotated(Vector3.UP,rng.randfn(0,dispersion)).rotated(v.global_basis.x,rng.randfn(0,dispersion))
	var vis=MeshInstance3D.new()
	var mesh=SphereMesh.new()
	mesh.radius=.12
	mesh.height=.24
	vis.mesh=mesh
	var material=terrain.material(Color(1,.65,.17))
	material.emission_enabled=true
	material.emission=Color(1,.5,.1)
	vis.material_override=material
	add_child(vis)
	vis.position=p
	shells.append({"position":p,"velocity":dir*v.cfg.ammo_data.muzzle_velocity_m_s,"ammo":v.cfg.ammo_data,"owner":v.agent_id,"origin":p,"distance":0.0,"age":0.0,"visual":vis})
	effect(p,Color(1,.65,.16),.7,.10)
	shot_distances.append(v.target_range)

func step_shells(dt: float):
	for i in range(shells.size()-1,-1,-1):
		var s=shells[i]
		var from=s.position
		var old_velocity=s.velocity
		s.velocity+=Vector3.DOWN*9.81*dt
		s.velocity*=exp(-float(s.ammo.drag_per_m)*s.velocity.length()*dt)
		var to=from+(old_velocity+s.velocity)*.5*dt
		s.distance+=from.distance_to(to)
		s.age+=dt
		var q=PhysicsRayQueryParameters3D.create(from,to,5,vehicles[s.owner].excluded())
		var hit=get_world_3d().direct_space_state.intersect_ray(q)
		if not hit.is_empty():
			var victim=hit.collider.get_meta("vehicle") if hit.collider.has_meta("vehicle") else null

			if victim!=null:
				victim.hit(
					s,
					hit.position,
					hit.normal,
					hit.collider.get_meta("zone")
				)

				if is_range and victim.agent_id==8 and int(s.owner)==0:
					on_range_target_impact(
						victim,
						s,
						hit.position
					)
			effect(hit.position,Color(.69,.51,.27),1.3,.6)
		if not hit.is_empty() or s.age>8 or s.distance>2500:
			s.visual.queue_free()
			shells.remove_at(i)
		else:
			s.position=to
			s.visual.position=to

func objective_capture_multiplier(count: int) -> float:
	if count <= 0:
		return 0.0

	var bonus = float(scenario.get("capture_multi_bonus_per_extra_vehicle", 0.35))
	var cap = float(scenario.get("capture_multi_cap", 2.0))

	return minf(
		cap,
		1.0 + bonus * float(count - 1)
	)


func objective_destination(vehicle) -> Vector3:
	# Rule AI знает о целях сценария.
	# MaleCNS по-прежнему НЕ получает XYZ точек или скрытую команду
	# "ехать на B".
	var preferred = vehicle.agent_id % objectives.size()
	var preferred_zone = objectives[preferred]

	if int(preferred_zone.get("owner", -1)) != vehicle.team:
		return preferred_zone["position"]

	if bool(preferred_zone.get("contested", false)):
		return preferred_zone["position"]

	var best = -1
	var best_distance = INF

	for offset in range(objectives.size()):
		var index = (preferred + offset) % objectives.size()
		var zone = objectives[index]

		if int(zone.get("owner", -1)) == vehicle.team:
			if not bool(zone.get("contested", false)):
				continue

		var distance = vehicle.global_position.distance_squared_to(
			zone["position"]
		)

		if distance < best_distance:
			best_distance = distance
			best = index

	if best >= 0:
		return objectives[best]["position"]

	# Все точки уже наши: возвращаемся к исходной назначенной точке
	# и фактически обороняем её.
	return preferred_zone["position"]


func objective_hud_status(zone: Dictionary) -> String:
	var inside = zone.get("inside", [0, 0])

	if bool(zone.get("contested", false)):
		return "%s %d:%d" % [
			AppState.tr_text("CONTESTED"),
			int(inside[0]),
			int(inside[1])
		]

	var control = float(zone.get("progress", 0.0))
	var percent = clampi(
		int(round(absf(control) * 100.0)),
		0,
		100
	)

	var owner = int(zone.get("owner", -1))

	if owner == 0:
		return "%s %d%%" % [
			AppState.tr_text("BLUE"),
			percent
		]

	if owner == 1:
		return "%s %d%%" % [
			AppState.tr_text("RED"),
			percent
		]

	if control > 0.001:
		return "%s ↑ %d%%" % [
			AppState.tr_text("BLUE"),
			percent
		]

	if control < -0.001:
		return "%s ↑ %d%%" % [
			AppState.tr_text("RED"),
			percent
		]

	return AppState.tr_text("NEUTRAL")


func update_objective_visual(index: int):
	if index < 0 or index >= objectives.size():
		return

	var zone = objectives[index]

	var neutral = Color(0.34, 0.36, 0.34)
	var blue = Color(0.22, 0.42, 0.78)
	var red = Color(0.76, 0.25, 0.18)
	var contested = Color(0.90, 0.70, 0.16)

	var control = float(zone.get("progress", 0.0))
	var colour = neutral

	if bool(zone.get("contested", false)):
		colour = contested
	elif control > 0.0:
		colour = neutral.lerp(
			blue,
			clampf(control, 0.0, 1.0)
		)
	elif control < 0.0:
		colour = neutral.lerp(
			red,
			clampf(-control, 0.0, 1.0)
		)

	var marker = zone.get("marker", null)

	if is_instance_valid(marker):
		if marker.material_override != null:
			marker.material_override.albedo_color = colour

	var objective_label = zone.get("label", null)

	if is_instance_valid(objective_label):
		objective_label.text = (
			["A", "B", "C"][index]
			+ "\n"
			+ objective_hud_status(zone)
		)


func step_objectives(dt: float):
	# Signed Domination control:
	#
	#   +1.0  BLUE owns
	#    0.0  neutral
	#   -1.0  RED owns
	#
	# Поэтому полный переворот:
	#
	# enemy-owned -> neutral -> friendly-owned

	for index in range(objectives.size()):
		var zone = objectives[index]

		var counts = [0, 0]
		var occupants = [[], []]

		for vehicle in vehicles:
			if not vehicle.alive:
				continue

			if vehicle.position.distance_to(
				zone["position"]
			) >= float(scenario.zone_radius):
				continue

			counts[vehicle.team] += 1
			occupants[vehicle.team].append(vehicle)

			vehicle.metrics.objective_presence_s += dt

		zone["inside"] = [
			counts[0],
			counts[1]
		]

		var contested_now = (
			counts[0] > 0
			and counts[1] > 0
		)

		zone["contested"] = contested_now

		# ====================================================
		# CONTESTED
		# ====================================================

		if contested_now:
			# Противники в круге блокируют изменение прогресса.
			for team in range(2):
				for vehicle in occupants[team]:
					vehicle.metrics.contest_s += dt

		# ====================================================
		# ONE TEAM ONLY
		# ====================================================

		elif counts[0] > 0 or counts[1] > 0:
			var team = 0
			if counts[1] > 0:
				team = 1

			var direction = 1.0
			if team == 1:
				direction = -1.0

			var multiplier = objective_capture_multiplier(
				counts[team]
			)

			var capture_seconds = maxf(
				0.001,
				float(scenario.capture_seconds)
			)

			var previous = float(
				zone.get("progress", 0.0)
			)

			var updated = clampf(
				previous
				+ direction
				* (dt / capture_seconds)
				* multiplier,
				-1.0,
				1.0
			)

			zone["progress"] = updated

			# Только реальное движение capture bar считается вкладом
			# в захват. Простое стояние на уже своей точке сюда не входит.
			var effective_effort = (
				absf(updated - previous)
				* capture_seconds
			)

			if effective_effort > 0.0:
				var per_vehicle = (
					effective_effort
					/ maxf(
						1.0,
						float(counts[team])
					)
				)

				for vehicle in occupants[team]:
					vehicle.metrics.capture_s += per_vehicle

			# ====================================================
			# ENEMY OWNED -> NEUTRAL
			# ====================================================

			var owner = int(
				zone.get("owner", -1)
			)

			if owner == 0 and updated <= 0.0:
				zone["owner"] = -1

				objective_neutralizations[1] += 1
				capture_changes += 1

			elif owner == 1 and updated >= 0.0:
				zone["owner"] = -1

				objective_neutralizations[0] += 1
				capture_changes += 1

			# ====================================================
			# NEUTRAL -> OWNED
			# ====================================================

			owner = int(
				zone.get("owner", -1)
			)

			if owner == -1:
				if updated >= 1.0:
					zone["owner"] = 0

					objective_captures[0] += 1
					capture_changes += 1

				elif updated <= -1.0:
					zone["owner"] = 1

					objective_captures[1] += 1
					capture_changes += 1

		update_objective_visual(index)

	# ========================================================
	# DOMINATION TICKET BLEED
	# ========================================================
	#
	# Равное число точек:
	#     bleed отсутствует
	#
	# 2 : 1
	#     отстающая сторона теряет 1× base
	#
	# 2 : 0 / 3 : 1
	#     2×
	#
	# 3 : 0
	#     3×

	var owned = [0, 0]

	for zone in objectives:
		var owner = int(
			zone.get("owner", -1)
		)

		if owner >= 0:
			owned[owner] += 1

	var difference = owned[0] - owned[1]

	var bleed = float(
		scenario.ticket_bleed_per_s
	)

	if difference > 0:
		tickets[1] = maxf(
			0.0,
			tickets[1]
				- dt
				* bleed
				* float(difference)
		)

	elif difference < 0:
		tickets[0] = maxf(
			0.0,
			tickets[0]
				- dt
				* bleed
				* float(-difference)
		)


func alive_count(team: int) -> int:
	var count=0
	for v in vehicles:
		if v.alive and v.team==team:count+=1
	return count
func effect(
	p: Vector3,
	c: Color,
	size: float,
	lifetime: float,
	expansion: float=.25,
	rise_speed: float=0.0
):
	# Bounded visual effect.
	#
	# Old implementation multiplied scale every frame for the whole lifetime.
	# A destroyed tank started at 5 m radius and grew for 8 seconds, producing
	# a cloud hundreds of metres wide.
	#
	# This implementation has an explicit MAXIMUM expansion.

	if session_config!=null:
		var limit=int(60*AppState.settings.effects)
		if effects.size()>=maxi(6,limit):
			return

	var mesh=MeshInstance3D.new()

	var sphere=SphereMesh.new()
	sphere.radius=size
	sphere.height=size*2.0
	sphere.radial_segments=10
	sphere.rings=6
	mesh.mesh=sphere

	var material=StandardMaterial3D.new()
	material.albedo_color=c
	material.roughness=.9
	material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA

	# Bright orange/yellow effects get a small self-lit component.
	# Smoke remains normally shaded.
	if maxf(c.r,maxf(c.g,c.b))>.55:
		material.emission_enabled=true
		material.emission=Color(c.r,c.g,c.b)

	mesh.material_override=material

	add_child(mesh)
	mesh.global_position=p

	effects.append({
		"node":mesh,
		"life":lifetime,
		"initial":lifetime,
		"expansion":maxf(0.0,expansion),
		"rise_speed":rise_speed,
		"base_alpha":c.a
	})


func vehicle_destroyed_effect(p: Vector3, catastrophic: bool=false):
	# A tank destruction is a compact flash/fire/smoke event.
	# Catastrophic ammo-rack destruction is somewhat stronger, but still
	# deliberately bounded to a few metres rather than dozens/hundreds.

	var intensity=1.15 if catastrophic else 1.0

	# Very short internal flash.
	effect(
		p+Vector3(0,.7,0),
		Color(1.0,.58,.12,1.0),
		.85*intensity,
		.16,
		.40,
		.2
	)

	# Fireball.
	effect(
		p+Vector3(0,1.0,0),
		Color(.72,.27,.055,.92),
		1.20*intensity,
		.42,
		.45,
		.35
	)

	# Several compact smoke lobes instead of one enormous expanding sphere.
	var smoke_count=5 if catastrophic else 4

	for i in range(smoke_count):
		var angle=rng.randf_range(0.0,TAU)
		var radius=rng.randf_range(.25,1.25)

		var offset=Vector3(
			cos(angle)*radius,
			rng.randf_range(.8,2.0),
			sin(angle)*radius
		)

		effect(
			p+offset,
			Color(.13,.12,.105,.72),
			rng.randf_range(.65,.95)*intensity,
			rng.randf_range(2.0,2.8),
			.85,
			rng.randf_range(.45,.75)
		)


func snapshot() -> Dictionary:
	var states=[]
	for v in vehicles:
		states.append({"id":v.agent_id,"vehicle":v.cfg.id,"position":[v.position.x,v.position.y,v.position.z],"yaw":v.rotation.y,"turret":v.turret_angle,"gun":v.gun_angle,"alive":v.alive,"modules":v.modules.duplicate(),"metrics":v.metrics.duplicate(),"target":v.target,"impact":v.last_impact.duplicate(true)})
	var zones=[]
	for z in objectives:zones.append({"owner":z.owner,"progress":z.progress,"contested":z.contested,"inside":z.inside.duplicate()})
	return {"time":sim_time,"vehicles":states,"tickets":tickets.duplicate(),"zones":zones,"brain":bridge.last_reply.get("mode","DISCONNECTED"),"projectiles":shell_snapshot(),"communication":current_communication().duplicate(true)}
func shell_snapshot() -> Array:
	var out=[]
	for s in shells:out.append([s.position.x,s.position.y,s.position.z])
	return out

func finish(notify_result=true):
	if finished_report:return
	finished_report=true
	ended=true
	var wall=(Time.get_ticks_usec()-start_wall)/1000000.0
	var report=snapshot()
	report.wall_seconds=wall
	report.realtime_factor=sim_time/maxf(.001,wall)
	report.mean_physics_ms=physics_usec/maxf(1,frame)/1000
	report.render_fps=Engine.get_frames_per_second() if DisplayServer.get_name()!="headless" else null
	report.ipc_roundtrip_ms=bridge.latency_ms
	report.brain_tick_ms=bridge.last_reply.get("tick_ms",null)
	report.shot_distances=shot_distances
	report.backend_metadata=bridge.last_reply.get("metadata",{})
	report.capture_changes=capture_changes
	report.objective_captures=objective_captures.duplicate()
	report.objective_neutralizations=objective_neutralizations.duplicate()
	report.track_segments=tracks.segments
	report.max_rut_depth_m=tracks.max_depth
	report.completion="complete" if notify_result else "interrupted"
	report.mode="NORMALIZED" if normalized else "HISTORICAL"
	if record_path!="":
		FileAccess.open(record_path.path_join("summary.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
		if recorder:recorder.flush()
	print("SUMMARY ",JSON.stringify({"sim_s":sim_time,"wall_s":wall,"xRT":report.realtime_factor,"physics_ms":report.mean_physics_ms,"brain_tick_ms":report.brain_tick_ms,"alive":[alive_count(0),alive_count(1)]}))
	report_cache=report
	if session_config!=null and notify_result:completed.emit(report)
	if has("--quit"):get_tree().quit()
func _process(dt):
	for i in range(effects.size()-1,-1,-1):
		var fx=effects[i]

		fx["life"]=float(fx["life"])-dt

		var initial=maxf(
			.001,
			float(fx.get("initial",1.0))
		)

		var progress=clampf(
			1.0-float(fx["life"])/initial,
			0.0,
			1.0
		)

		# Smooth 0 -> 1 without unbounded multiplicative growth.
		var smooth=progress*progress*(3.0-2.0*progress)

		var maximum_scale=1.0+float(
			fx.get("expansion",.25)
		)

		fx["node"].scale=Vector3.ONE*lerpf(
			1.0,
			maximum_scale,
			smooth
		)

		fx["node"].position.y+=float(
			fx.get("rise_speed",0.0)
		)*dt

		var material=fx["node"].material_override

		if material is StandardMaterial3D:
			var colour=material.albedo_color

			colour.a=float(
				fx.get("base_alpha",1.0)
			)*pow(
				maxf(0.0,1.0-progress),
				1.35
			)

			material.albedo_color=colour

		if float(fx["life"])<=0.0:
			fx["node"].queue_free()
			effects.remove_at(i)
	if range_feedback_timer>0.0:
		range_feedback_timer=maxf(0.0,range_feedback_timer-dt)

		if range_feedback_timer<=0.0 and is_instance_valid(range_feedback):
			range_feedback.visible=false

	if is_range and range_killcam_active:
		update_range_killcam(dt)
		return

	var v=vehicles[selected] if not vehicles.is_empty() else null
	if v==null:return
	sensor_debug.visible=debug
	if debug:
		var mesh=ImmediateMesh.new()
		var mat=StandardMaterial3D.new()
		mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color=Color(.3,1,.6)
		mesh.surface_begin(Mesh.PRIMITIVE_LINES,mat)
		var origin=v.position+Vector3(0,2.5,0)
		if v.target>=0:
			mesh.surface_add_vertex(origin)
			mesh.surface_add_vertex(vehicles[v.target].position+Vector3(0,2,0))
		for side in [-1,1]:
			var angle=v.rotation.y+side*deg_to_rad(100)
			mesh.surface_add_vertex(origin)
			mesh.surface_add_vertex(origin+Vector3(sin(angle),0,cos(angle))*35)
		mesh.surface_end()
		sensor_debug.mesh=mesh
	if camera_mode==0:
		# True whole-battle observer view. It is deliberately independent of
		# the selected vehicle.
		camera.projection=Camera3D.PROJECTION_ORTHOGONAL
		camera.size=battlefield_zoom
		camera.keep_aspect=Camera3D.KEEP_HEIGHT
		var pan=Vector2.ZERO
		if Input.is_physical_key_pressed(KEY_W):pan.y-=1
		if Input.is_physical_key_pressed(KEY_S):pan.y+=1
		if Input.is_physical_key_pressed(KEY_A):pan.x-=1
		if Input.is_physical_key_pressed(KEY_D):pan.x+=1
		if pan.length()>0:
			battlefield_pan+=pan.normalized()*dt*maxf(120,battlefield_zoom*.55)
			battlefield_pan.x=clampf(battlefield_pan.x,-terrain.extent*.8,terrain.extent*.8)
			battlefield_pan.y=clampf(battlefield_pan.y,-terrain.extent*.8,terrain.extent*.8)
		camera.position=Vector3(battlefield_pan.x,1100,battlefield_pan.y)
		camera.rotation=Vector3(-PI/2,0,0)
	elif camera_mode==1:
		camera.projection=Camera3D.PROJECTION_PERSPECTIVE
		var follow=v.position-v.global_basis.z*16+Vector3(0,8,0)
		camera.position=follow if last_camera_mode!=camera_mode else camera.position.lerp(follow,minf(1,dt*4))
		camera.look_at(v.position+Vector3(0,2,0))
	elif camera_mode==2:
		camera.projection=Camera3D.PROJECTION_PERSPECTIVE
		camera.position=v.muzzle.global_position+Vector3(0,.4,0)
		var a=v.rotation.y+v.turret_angle
		camera.look_at(camera.position+Vector3(sin(a)*cos(v.gun_angle),sin(v.gun_angle),cos(a)*cos(v.gun_angle))*100)
	else:
		camera.projection=Camera3D.PROJECTION_PERSPECTIVE
		var movement=Vector3.ZERO
		if Input.is_physical_key_pressed(KEY_W):movement-=camera.global_basis.z
		if Input.is_physical_key_pressed(KEY_S):movement+=camera.global_basis.z
		if Input.is_physical_key_pressed(KEY_A):movement-=camera.global_basis.x
		if Input.is_physical_key_pressed(KEY_D):movement+=camera.global_basis.x
		if Input.is_physical_key_pressed(KEY_Q):movement.y-=1
		if Input.is_physical_key_pressed(KEY_E):movement.y+=1
		camera.position+=movement*dt*100
	observer_environment.fog_enabled=camera_mode!=0
	last_camera_mode=camera_mode
	update_identification_labels()
	var connection=AppState.tr_text("BRAIN BACKEND DISCONNECTED · RULE_BASED_CONTROL")
	if requires_brain:
		connection=AppState.tr_text("BRAIN WAITING") if not bridge.connected() else "2 × batch=8 · "+bridge.last_reply.get("mode","")

	var physics_name=AppState.tr_text("Normalized research control" if normalized else "Historical · provisional data")
	var audio_name=AppState.tr_text({"no_audio":"No Audio","team_audio":"Team Audio","all_audio":"All Audio"}.get(audio_mode,audio_mode))

	hud.text=AppState.tr_format("hud.header",[
		tickets[0],alive_count(0),tickets[1],alive_count(1),
		objective_hud_status(objectives[0]),
		objective_hud_status(objectives[1]),
		objective_hud_status(objectives[2]),
		sim_time,physics_name,audio_name,connection,
		bridge.tick,bridge.last_reply.get("tick_ms",0),bridge.latency_ms,
		Engine.get_frames_per_second()
	])

	var communication=current_communication()
	var songs=communication.get("song_out",[])
	var own_song=float(songs[v.agent_id]) if songs.size()==16 else 0.0
	var los_text=AppState.tr_text("yes" if v.seen else "no")

	detail.text=AppState.tr_format("hud.detail",[
		v.cfg.display_name,
		AppState.tr_text(str(v.cfg.role)),
		"B" if v.team==0 else "R",
		v.agent_id%8+1,
		v.agent_id%8,
		v.speed*3.6,
		clampi(int(absf(v.speed)/3)+1,1,v.cfg.gears.size()),
		v.ammo_left,
		v.reload_left,
		v.target,
		v.target_range,
		los_text,
		rad_to_deg(v.gun_angle),
		own_song,
		v.audio_input,
		str(v.dn),
		camera_name(),
		(str(v.modules)+"\n"+str(v.last_impact)) if debug else ""
	])
	if is_range:
		detail.text+="\n"+AppState.tr_text("MANUAL · WASD drive · Q/E turret · R/F elevation · Space/LMB fire · ESC menu")
		if debug:detail.text+="\n"+AppState.tr_text("TARGET IMPACT: ")+str(vehicles[8].last_impact)
	if ended:detail.text+="\n"+AppState.tr_text("BATTLE COMPLETE")
	if screenshot_path!="" and sim_time>float(option("--capture-at","3.6")) and DisplayServer.get_name()!="headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(screenshot_path)
		screenshot_path=""
func _unhandled_input(event):
	if event is InputEventMouseButton and event.pressed and camera_mode==0:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:
			battlefield_zoom=clampf(battlefield_zoom*.86,280,1800)
		elif event.button_index==MOUSE_BUTTON_WHEEL_DOWN:
			battlefield_zoom=clampf(battlefield_zoom*1.16,280,1800)
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_TAB:selected=(selected+1)%16
			KEY_C:
				if is_range and range_killcam_active:
					end_range_killcam()
				else:
					cycle_camera()
			KEY_T:cycle_comms()
			KEY_F1:debug=not debug
			KEY_ENTER:
				if is_range:
					reset_range_target()
			KEY_KP_ENTER:
				if is_range:
					reset_range_target()
			KEY_SPACE:
				if not is_range:paused=not paused
			KEY_ESCAPE:
				if session_config!=null:pause_requested.emit()
				else:get_tree().quit()
	if is_range and not paused and event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		vehicles[0].turret_angle+=event.relative.x*.003
		vehicles[0].gun_angle-=event.relative.y*.002
	if camera_mode==3:
		if Input.is_physical_key_pressed(KEY_LEFT):camera.rotate_y(.035)
		if Input.is_physical_key_pressed(KEY_RIGHT):camera.rotate_y(-.035)
		if Input.is_physical_key_pressed(KEY_UP):camera.rotate_object_local(Vector3.RIGHT,.035)
		if Input.is_physical_key_pressed(KEY_DOWN):camera.rotate_object_local(Vector3.RIGHT,-.035)


func camera_name() -> String:
	return AppState.tr_text([
		"Battlefield",
		"Third-person",
		"Gunner",
		"Free camera",
	][camera_mode])

func update_camera_button():
	if is_instance_valid(camera_button):
		camera_button.text=AppState.tr_format("camera.button",[camera_name()])

func update_identification_labels():
	# Convert a bounded screen font size to world units. Label3D fixed_size uses
	# projection-dependent scaling and must not reuse a world-space pixel_size.
	var height=maxf(1,get_viewport().get_visible_rect().size.y)
	for tank in vehicles:
		var label=tank.get_node("Identification") as Label3D
		label.text=agent_label(tank.agent_id) if camera_mode==0 else agent_label(tank.agent_id)+" · "+tank.cfg.display_name
		label.visible=tank.alive and (camera_mode==0 or camera.position.distance_to(tank.position)<300)
		size_world_label(label,15,height)
		label.global_position=tank.global_position+Vector3(0,5,0)
		if camera_mode==0:
			label.global_position+=camera.global_basis.y*((1 if tank.agent_id%2==0 else -1)*12*camera.size/height)
	for i in range(objectives.size()):
		size_world_label(get_node("ObjectiveLabel"+str(i)),24,height)

func size_world_label(label: Label3D, pixels: float, viewport_height: float):
	var units=camera.size/viewport_height
	if camera.projection==Camera3D.PROJECTION_PERSPECTIVE:
		var depth=-(camera.global_transform.affine_inverse()*label.global_position).z
		units=2*maxf(.1,depth)*tan(deg_to_rad(camera.fov)*.5)/viewport_height
	label.pixel_size=units*pixels/label.font_size

func cycle_camera():
	camera_mode=(camera_mode+1)%4
	update_camera_button()

func comm_mode_label() -> String:
	return AppState.tr_text([
		"Comms: Off",
		"Comms: Red",
		"Comms: Blue",
		"Comms: All",
	][comm_view])

func cycle_comms():
	comm_view=(comm_view+1)%4
	refresh_comm_panel()

func current_communication() -> Dictionary:
	var value=replay_communication if replay_mode else bridge.last_reply.get("communication",{})
	return value if value is Dictionary else {}

func agent_label(id: int) -> String:
	return ("B"+str(id+1)) if id<8 else ("R"+str(id-7))

func comm_event_visible(event: Dictionary) -> bool:
	if comm_view==3:return true
	var sender=int(event.get("sender",-1))
	if sender<0:return false
	if comm_view==1:return sender>=8
	if comm_view==2:return sender<8
	return false

func visible_comm_events(limit: int=12) -> Array:
	var result=[]
	for event in comm_history:
		if sim_time-float(event.get("time",0))<=2.0 and comm_event_visible(event):
			result.append(event)
			if result.size()>=limit:break
	return result

func ingest_communication(communication):
	if not communication is Dictionary or communication.is_empty():return
	if not communication.get("sample",-1) is float and not communication.get("sample",-1) is int:return
	var sample=int(communication.get("sample",-1))
	if sample<0 or sample==comm_last_sample:return
	comm_last_sample=sample

	var sources=communication.get("events",[])
	if not sources is Array:return
	for source in sources:
		if not source is Dictionary:continue
		if not source.get("sender",null) is float and not source.get("sender",null) is int:continue
		if not source.get("receiver",null) is float and not source.get("receiver",null) is int:continue
		var event=source.duplicate(true)
		var sender=int(event.get("sender",-1))
		var receiver=int(event.get("receiver",-1))
		if sender<0 or sender>=16 or receiver<0 or receiver>=16:continue

		if sender==receiver:continue
		if not event.get("received",null) is float and not event.get("received",null) is int:continue
		if not event.get("raw",null) is float and not event.get("raw",null) is int:continue
		if not event.get("distance_m",null) is float and not event.get("distance_m",null) is int:continue
		if not is_finite(float(event.received)) or float(event.received)<0:continue
		if not is_finite(float(event.distance_m)) or float(event.distance_m)<0:continue
		var key=str(sender)+">"+str(receiver)
		var last_time=float(comm_last_link.get(key,-999.0))

		# UI-only deduplication. It does NOT modify neural communication.
		if sim_time-last_time<.25:continue

		comm_last_link[key]=sim_time
		event.time=sim_time
		comm_history.push_front(event)

	while comm_history.size()>80:
		comm_history.pop_back()

	refresh_comm_panel()

func update_comm_links(events: Array):
	if not is_instance_valid(comm_links):return

	if comm_view==0 or events.is_empty():
		comm_links.mesh=null
		return

	var valid=[]
	for event in events:
		var sender=int(event.get("sender",-1));var receiver=int(event.get("receiver",-1))
		if sender>=0 and sender<vehicles.size() and receiver>=0 and receiver<vehicles.size():
			if vehicles[sender].alive and vehicles[receiver].alive:valid.append(event)
	if valid.is_empty():comm_links.mesh=null;return
	var mesh=ImmediateMesh.new()
	mesh.surface_begin(Mesh.PRIMITIVE_LINES,comm_line_material)

	for event in valid:
		var sender=int(event.sender)
		var receiver=int(event.receiver)
		if sender<0 or sender>=vehicles.size() or receiver<0 or receiver>=vehicles.size():
			continue

		if not vehicles[sender].alive or not vehicles[receiver].alive:continue
		var strength=clampf(float(event.get("received",0))/.20,.25,1.0)
		var base=Color(.34,.66,1.0) if sender<8 else Color(1.0,.42,.30)
		var colour=base.darkened(1.0-strength)

		mesh.surface_set_color(colour)
		mesh.surface_add_vertex(vehicles[sender].global_position+Vector3(0,5,0))
		mesh.surface_set_color(colour)
		mesh.surface_add_vertex(vehicles[receiver].global_position+Vector3(0,5,0))

	mesh.surface_end()
	comm_links.mesh=mesh

func refresh_comm_panel():
	if is_instance_valid(comm_toggle):
		comm_toggle.text=comm_mode_label()

	if not is_instance_valid(comm_panel):return

	comm_panel.visible=comm_view!=0
	if comm_view==0:
		update_comm_links([])
		return

	comm_title.text=AppState.tr_text([
		"",
		"Team Communication · Red",
		"Team Communication · Blue",
		"Team Communication · All",
	][comm_view])

	if audio_mode=="no_audio":
		comm_text.text=AppState.tr_text("Communication channel disabled")
		update_comm_links([])
		return

	if not requires_brain and not replay_mode:
		comm_text.text=AppState.tr_text("No neural communication telemetry in Rule AI mode.")
		update_comm_links([])
		return

	var events=visible_comm_events(14)
	if events.is_empty():
		comm_text.text=AppState.tr_text("No signal above threshold yet.")
		update_comm_links([])
		return

	var lines=[]
	for event in events:
		lines.append(AppState.tr_format("comms.line",[
			float(event.get("time",0)),
			agent_label(int(event.sender)),
			agent_label(int(event.receiver)),
			float(event.get("raw",0)),
			float(event.get("received",0)),
			float(event.get("distance_m",0)),
		]))

	comm_text.text="\n".join(lines)
	update_comm_links(events)


func range_impact_result(impact: Dictionary) -> String:
	if bool(impact.get("ricochet",false)):
		return AppState.tr_text("RICOCHET")

	if bool(impact.get("penetrated",false)):
		return AppState.tr_text("PENETRATION")

	return AppState.tr_text("NO PENETRATION")


func show_range_feedback(message: String, duration: float=1.8):
	if not is_instance_valid(range_feedback):
		return

	range_feedback.text=message
	range_feedback.visible=true
	range_feedback_timer=duration


func range_kill_reason(target) -> String:
	if not bool(target.modules.get("ammo_rack", true)):
		return AppState.tr_text("Ammo rack detonation")

	var driver_down = not bool(target.modules.get("driver", true))
	var gunner_down = not bool(target.modules.get("gunner", true))
	var commander_down = not bool(target.modules.get("commander", true))

	if driver_down and gunner_down and commander_down:
		return AppState.tr_text("Crew incapacitated")

	return AppState.tr_text("Critical internal damage")


func on_range_target_impact(target, shell: Dictionary, point: Vector3):
	if not is_range:
		return

	var impact=target.last_impact
	if not impact is Dictionary:
		return

	var result=range_impact_result(impact)

	var capability=float(
		impact.get("capability",0.0)
	)

	var effective=float(
		impact.get("effective",0.0)
	)

	var zone=str(
		impact.get("zone","?")
	)

	var damaged=impact.get("damaged",[])
	var damaged_text=""

	if damaged is Array and not damaged.is_empty():
		damaged_text=" · "+", ".join(
			PackedStringArray(damaged)
		)

	show_range_feedback(
		"%s · %s · %.0f / %.0f mm%s" % [
			result,
			zone,
			capability,
			effective,
			damaged_text
		]
	)

	if not target.alive:
		start_range_killcam(
			target,
			shell,
			point
		)


func clear_range_killcam_path():
	if is_instance_valid(range_killcam_path):
		range_killcam_path.mesh=null
		range_killcam_path.visible=false


func draw_range_killcam_path(
	origin: Vector3,
	impact_point: Vector3
):
	if not is_instance_valid(range_killcam_path):
		return

	var mesh=ImmediateMesh.new()
	var material=StandardMaterial3D.new()

	material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color=Color(1.0,.76,.20,1.0)
	material.no_depth_test=true

	mesh.surface_begin(
		Mesh.PRIMITIVE_LINES,
		material
	)

	mesh.surface_add_vertex(origin)
	mesh.surface_add_vertex(impact_point)

	mesh.surface_end()

	range_killcam_path.mesh=mesh
	range_killcam_path.visible=true


func start_range_killcam(
	target,
	shell: Dictionary,
	impact_point: Vector3
):
	if not is_range:
		return

	range_target_destroyed=true
	range_killcam_active=true
	range_killcam_elapsed=0.0
	range_killcam_target=target.agent_id
	range_killcam_saved_camera=camera_mode

	camera.projection=Camera3D.PROJECTION_PERSPECTIVE
	camera.fov=55

	var impact=target.last_impact
	var ammo=shell.get("ammo",{})

	var shell_name=str(
		ammo.get(
			"id",
			impact.get("shell","unknown")
		)
	)

	var damaged=impact.get("damaged",[])
	var damaged_text=AppState.tr_text("none")

	if damaged is Array and not damaged.is_empty():
		damaged_text=", ".join(
			PackedStringArray(damaged)
		)

	var reason=range_kill_reason(target)

	range_killcam_title.text=AppState.tr_text(
		"TARGET DESTROYED"
	)

	var killcam_lines = PackedStringArray()
	killcam_lines.append(AppState.tr_text("Killcam"))
	killcam_lines.append(target.cfg.display_name)
	killcam_lines.append("")
	killcam_lines.append(
		AppState.tr_text("Shell")
		+ ": "
		+ shell_name
	)
	killcam_lines.append(
		AppState.tr_text("Hit zone")
		+ ": "
		+ str(impact.get("zone", "?"))
	)
	killcam_lines.append(
		AppState.tr_text("Impact distance")
		+ ": %.0f m" % float(impact.get("distance", 0.0))
	)
	killcam_lines.append(
		AppState.tr_text("Damaged modules")
		+ ": "
		+ damaged_text
	)
	killcam_lines.append(
		AppState.tr_text("Destruction reason")
		+ ": "
		+ reason
	)
	killcam_lines.append("")
	killcam_lines.append(
		AppState.tr_text("Press C to skip killcam")
		+ " · "
		+ AppState.tr_text("Press Enter to reset target")
	)

	range_killcam_body.text = "\n".join(killcam_lines)

	range_killcam_panel.visible=true

	var origin=shell.get(
		"origin",
		vehicles[0].muzzle.global_position
	)

	if origin is Vector3:
		draw_range_killcam_path(
			origin,
			impact_point
		)

	show_range_feedback(
		AppState.tr_text("TARGET DESTROYED"),
		2.0
	)


func update_range_killcam(dt: float):
	if not range_killcam_active:
		return

	range_killcam_elapsed+=dt

	if range_killcam_target < 0 or range_killcam_target >= vehicles.size():
		end_range_killcam()
		return

	var target=vehicles[range_killcam_target]

	var centre = target.global_position + Vector3(0, 1.5, 0)

	# Slow cinematic orbit around the wreck.
	var angle = target.rotation.y + 2.35 + range_killcam_elapsed * 0.32

	var radius=11.5

	var desired = centre + Vector3(
		sin(angle) * radius,
		5.2,
		cos(angle) * radius
	)

	camera.projection=Camera3D.PROJECTION_PERSPECTIVE
	camera.position=camera.position.lerp(
		desired,
		minf(1.0,dt*4.5)
	)

	camera.look_at(
		centre,
		Vector3.UP
	)

	if range_killcam_elapsed>=range_killcam_duration:
		end_range_killcam()


func end_range_killcam():
	if not range_killcam_active:
		return

	range_killcam_active=false
	range_killcam_elapsed=0.0

	camera_mode=range_killcam_saved_camera
	update_camera_button()

	clear_range_killcam_path()

	# Keep the summary panel visible until the user restores the target.
	if range_target_destroyed:
		range_killcam_panel.visible=true


func reset_range_target():
	if not is_range:
		return

	if vehicles.size()<=8:
		return

	var target=vehicles[8]

	range_killcam_active=false
	range_target_destroyed=false
	range_killcam_elapsed=0.0

	clear_range_killcam_path()

	if is_instance_valid(range_killcam_panel):
		range_killcam_panel.visible=false

	target.alive=true
	target.show()

	target.speed=0.0
	target.velocity=Vector3.ZERO
	target.yaw_rate=0.0

	target.turret_angle=0.0
	target.gun_angle=0.0

	target.reload_left=0.0
	target.ammo_left=int(target.cfg.ammo_count)

	target.cmd=[
		0.0,0.0,0.0,
		0.0,0.0,0.0
	]

	target.target=-1
	target.seen=false
	target.last_impact={}

	for key in target.modules:
		target.modules[key]=true

	# Remove destruction-char material override and restore materials embedded
	# in the GLB.
	for mesh in target.model.find_children(
		"*",
		"MeshInstance3D",
		true,
		false
	):
		mesh.material_override=null

	var distance=500
	var angle=0

	if session_config!=null:
		distance=int(session_config.range_distance)
		angle=int(session_config.target_angle)

	target.position = Vector3(0.0, 0.1, 0.5 * float(distance))

	target.rotation = Vector3(
		0.0,
		PI + deg_to_rad(float(angle)),
		0.0
	)

	if target.turret:
		target.turret.rotation.y=0.0

	if target.gun:
		target.gun.rotation.x=0.0

	camera_mode=1
	update_camera_button()

	vehicles[0].target=8
	vehicles[0].target_range = vehicles[0].position.distance_to(target.position)

	show_range_feedback(
		AppState.tr_text("TARGET RESTORED"),
		1.5
	)


func manual_commands() -> Array:
	if range_killcam_active:
		return [0,0,0,0,0,0]
	if camera_mode in [0,3]:return [0,0,0,0,0,0]
	var drive=float(Input.is_physical_key_pressed(KEY_W))-float(Input.is_physical_key_pressed(KEY_S))
	var steer=float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A))
	var turn=float(Input.is_physical_key_pressed(KEY_E))-float(Input.is_physical_key_pressed(KEY_Q))
	var elevate=float(Input.is_physical_key_pressed(KEY_R))-float(Input.is_physical_key_pressed(KEY_F))
	var fire=float(Input.is_physical_key_pressed(KEY_SPACE) or Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT))
	if session_config!=null and session_config.range_mode in ["free","mobility"]:fire=0
	return [drive,0,steer,turn,elevate,fire]
func save_replay():
	if record_path=="":return
	if not recorder:
		recorder=FileAccess.open(record_path.path_join("replay.jsonl"),FileAccess.WRITE)
		for row in replay_buffer:recorder.store_line(row)
		replay_buffer.clear()
	recorder.flush()
func _exit_tree():
	bridge.tcp.disconnect_from_host()
	if recorder:recorder.flush();recorder.close()
