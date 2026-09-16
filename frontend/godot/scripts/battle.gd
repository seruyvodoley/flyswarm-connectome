extends Node3D
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
var camera: Camera3D
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
var screenshot_path=""

func option(name: String, fallback: String="") -> String:
	var args=OS.get_cmdline_user_args()
	for i in range(args.size()-1):
		if args[i]==name:return args[i+1]
	return fallback
func has(name: String) -> bool:return name in OS.get_cmdline_user_args()
func _ready():
	start_wall=Time.get_ticks_usec()
	camera_mode=int(option("--camera","1"))
	normalized=has("--normalized")
	training=has("--training")
	requires_brain=has("--connect")
	audio_mode=option("--audio","no_audio")
	scenario=Catalog.read_json("scenarios/"+("training_range" if training else "krasny_valley")+".json")
	scenario.seed=int(option("--seed",str(scenario.seed)))
	time_limit=float(option("--seconds",str(scenario.time_limit_s)))
	rng.seed=scenario.seed
	tickets=[float(scenario.tickets),float(scenario.tickets)]
	terrain=Terrain.new()
	add_child(terrain)
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
	sky.environment=env
	add_child(sky)
	var sun=DirectionalLight3D.new()
	sun.rotation_degrees=Vector3(-42,-28,0)
	sun.light_color=Color(1,.92,.77)
	sun.light_energy=1.7
	sun.shadow_enabled=true
	sun.directional_shadow_max_distance=300
	add_child(sun)
	for i in range(3):
		var v=scenario.objectives[i]
		var pos=Vector3(v[0],terrain.height_at(v[0],v[1]),v[1])
		objectives.append({"position":pos,"owner":-1,"progress":0.0})
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
		add_child(label)
		objectives[i].marker=marker
	for i in range(16):
		var team=int(i/8)
		var id=scenario.blue[i%8] if team==0 else scenario.red[i%8]
		id=option("--mirror",id)
		var tank=Vehicle.new()
		add_child(tank)
		tank.setup(Catalog.vehicle(id,normalized),i,self)
		var sign_value=(-1 if team==0 else 1)*(-1 if has("--swap") else 1)
		var x=(i%8-3.5)*scenario.spawn_spacing
		var z=scenario.spawn_z*sign_value
		tank.position=Vector3(x,terrain.height_at(x,z)+.1,z)
		tank.rotation.y=0 if sign_value<0 else PI
		vehicles.append(tank)
	sensor_debug=MeshInstance3D.new()
	add_child(sensor_debug)
	camera=Camera3D.new()
	camera.far=2300
	camera.fov=62
	add_child(camera)
	camera.position=Vector3(170,140,-250)
	camera.look_at(Vector3(0,0,0))
	var canvas=CanvasLayer.new()
	add_child(canvas)
	hud=Label.new()
	hud.position=Vector2(24,18)
	hud.add_theme_font_size_override("font_size",22)
	hud.add_theme_color_override("font_shadow_color",Color.BLACK)
	hud.add_theme_constant_override("shadow_offset_x",2)
	hud.add_theme_constant_override("shadow_offset_y",2)
	var backdrop=ColorRect.new()
	backdrop.color=Color(.025,.04,.05,.78)
	backdrop.position=Vector2(12,10)
	backdrop.size=Vector2(670,365)
	backdrop.mouse_filter=Control.MOUSE_FILTER_IGNORE
	canvas.add_child(backdrop)
	canvas.add_child(hud)
	detail=Label.new()
	detail.position=Vector2(24,190)
	detail.add_theme_font_size_override("font_size",16)
	canvas.add_child(detail)
	if requires_brain: bridge.connect_backend(int(option("--port","8765")))
	record_path=option("--record","")
	if record_path!="":
		DirAccess.make_dir_recursive_absolute(record_path)
		recorder=FileAccess.open(record_path.path_join("replay.jsonl"),FileAccess.WRITE)
		var manifest={"date":Time.get_datetime_string_from_system(true),"map":scenario.name,"map_seed":scenario.seed,"mode":"NORMALIZED" if normalized else "HISTORICAL","audio":audio_mode,"controller":"backend" if requires_brain else "RULE_BASED_CONTROL","side_swap":has("--swap"),"vehicles":[],"seconds":time_limit}
		var output=[]
		OS.execute("git",["-C",ProjectSettings.globalize_path("res://../.."),"rev-parse","HEAD"],output)
		manifest.git_commit="".join(output).strip_edges()
		output=[]
		OS.execute("git",["-C",ProjectSettings.globalize_path("res://../.."),"status","--porcelain"],output)
		manifest.git_dirty=not "".join(output).strip_edges().is_empty()
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
		assert(f!=null,"Replay missing")
		while not f.eof_reached():
			var row=JSON.parse_string(f.get_line())
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
	if replay_mode:
		replay_clock+=delta
		while replay_index<replay.size() and replay[replay_index].time<=replay_clock:
			var row=replay[replay_index]
			sim_time=row.time
			tickets=row.tickets
			for state in row.vehicles:
				var v=vehicles[int(state.id)]
				v.position=Vector3(state.position[0],state.position[1],state.position[2])
				v.rotation.y=state.yaw
				v.turret.rotation.y=state.turret
				v.gun.rotation.x=-state.gun
				v.alive=state.alive
				v.modules=state.modules
			for n in replay_shell_nodes:n.queue_free()
			replay_shell_nodes=[]
			for xyz in row.get("projectiles",[]):
				var n=terrain.box(Vector3(xyz[0],xyz[1],xyz[2]),Vector3(.2,.2,.6),Color(1,.7,.2),false)
				replay_shell_nodes.append(n)
			for i in range(3):
				objectives[i].owner=row.zones[i].owner
				objectives[i].progress=row.zones[i].progress
			replay_index+=1
		if replay_index>=replay.size() and has("--quit"):get_tree().quit()
		return
	if ended or paused:return
	var started=Time.get_ticks_usec()
	bridge.poll()
	if requires_brain:
		if bridge.pending and (Time.get_ticks_usec()-bridge.sent_at)>10000000:
			push_error("Brain response timeout; no silent baseline fallback")
			get_tree().quit(2)
			return
		if bridge.commands.is_empty():
			if not bridge.pending:
				var observations=[]
				for v in vehicles:
					v.sense(.02)
					observations.append(v.observation())
				bridge.request(observations,audio_mode)
			if (Time.get_ticks_usec()-start_wall)>180000000 and sim_time==0:
				push_error("Brain backend timeout")
				get_tree().quit(2)
			return
		for i in range(16):
			vehicles[i].cmd=bridge.commands[i]
			vehicles[i].dn=bridge.last_reply.get("traces",[])[i]
			vehicles[i].audio_input=bridge.last_reply.get("heard",[])[i]
		bridge.commands=[]
		delta=.02
	for v in vehicles:
		if not requires_brain:
			if frame%5==0:v.sense(delta*5)
			v.cmd=v.teacher()
		if training:
			v.cmd[0]=0
			v.cmd[2]=0
		v.step(delta)
	step_shells(delta)
	step_objectives(delta)
	sim_time+=delta
	frame+=1
	physics_usec+=Time.get_ticks_usec()-started
	if recorder and frame%5==0:recorder.store_line(JSON.stringify(snapshot()))
	if sim_time>=time_limit or minf(tickets[0],tickets[1])<=0 or alive_count(0)==0 or alive_count(1)==0:
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
	shells.append({"position":p,"velocity":dir*v.cfg.ammo_data.muzzle_velocity_m_s,"ammo":v.cfg.ammo_data,"owner":v.agent_id,"distance":0.0,"age":0.0,"visual":vis})
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
			if victim!=null:victim.hit(s,hit.position,hit.normal,hit.collider.get_meta("zone"))
			effect(hit.position,Color(.69,.51,.27),1.3,.6)
		if not hit.is_empty() or s.age>8 or s.distance>2500:
			s.visual.queue_free()
			shells.remove_at(i)
		else:
			s.position=to
			s.visual.position=to

func step_objectives(dt: float):
	for zone in objectives:
		var counts=[0,0]
		for v in vehicles:
			if v.alive and v.position.distance_to(zone.position)<scenario.zone_radius:
				counts[v.team]+=1
				v.metrics.capture_s+=dt
		if counts[0]>0 and counts[1]==0:zone.progress=minf(1,zone.progress+dt/scenario.capture_seconds)
		if counts[1]>0 and counts[0]==0:zone.progress=maxf(-1,zone.progress-dt/scenario.capture_seconds)
		var old=zone.owner
		if zone.progress>=1:zone.owner=0
		if zone.progress<=-1:zone.owner=1
		if old!=zone.owner:capture_changes+=1
		if zone.owner>=0:
			tickets[1-zone.owner]=maxf(0,tickets[1-zone.owner]-dt*scenario.ticket_bleed_per_s)
			zone.marker.material_override.albedo_color=Color(.22,.38,.65) if zone.owner==0 else Color(.65,.27,.17)
func alive_count(team: int) -> int:
	var count=0
	for v in vehicles:
		if v.alive and v.team==team:count+=1
	return count
func effect(p: Vector3,c: Color,size: float,lifetime: float):
	var mesh=MeshInstance3D.new()
	var sphere=SphereMesh.new()
	sphere.radius=size
	sphere.height=size*2
	sphere.radial_segments=8
	sphere.rings=4
	mesh.mesh=sphere
	mesh.material_override=terrain.material(c)
	add_child(mesh)
	mesh.position=p
	effects.append({"node":mesh,"life":lifetime,"initial":lifetime})
func snapshot() -> Dictionary:
	var states=[]
	for v in vehicles:
		states.append({"id":v.agent_id,"vehicle":v.cfg.id,"position":[v.position.x,v.position.y,v.position.z],"yaw":v.rotation.y,"turret":v.turret_angle,"gun":v.gun_angle,"alive":v.alive,"modules":v.modules.duplicate(),"metrics":v.metrics.duplicate(),"target":v.target,"impact":v.last_impact.duplicate(true)})
	var zones=[]
	for z in objectives:zones.append({"owner":z.owner,"progress":z.progress})
	return {"time":sim_time,"vehicles":states,"tickets":tickets.duplicate(),"zones":zones,"brain":bridge.last_reply.get("mode","DISCONNECTED"),"projectiles":shell_snapshot()}
func shell_snapshot() -> Array:
	var out=[]
	for s in shells:out.append([s.position.x,s.position.y,s.position.z])
	return out

func finish():
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
	report.track_segments=tracks.segments
	report.max_rut_depth_m=tracks.max_depth
	report.mode="NORMALIZED" if normalized else "HISTORICAL"
	if record_path!="":
		FileAccess.open(record_path.path_join("summary.json"),FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
		if recorder:recorder.flush()
	print("SUMMARY ",JSON.stringify({"sim_s":sim_time,"wall_s":wall,"xRT":report.realtime_factor,"physics_ms":report.mean_physics_ms,"brain_tick_ms":report.brain_tick_ms,"alive":[alive_count(0),alive_count(1)]}))
	if has("--quit"):get_tree().quit()
func _process(dt):
	for i in range(effects.size()-1,-1,-1):
		var fx=effects[i]
		fx.life-=dt
		fx.node.scale*=1+dt*.5
		if fx.life<=0:fx.node.queue_free();effects.remove_at(i)
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
		camera.position=camera.position.lerp(v.position+Vector3(110,100,-150),dt*2)
		camera.look_at(v.position+Vector3(0,2,0))
	elif camera_mode==1:
		camera.position=camera.position.lerp(v.position-v.global_basis.z*16+Vector3(0,8,0),dt*4)
		camera.look_at(v.position+Vector3(0,2,0))
	elif camera_mode==2:
		camera.position=v.muzzle.global_position+Vector3(0,.4,0)
		var a=v.rotation.y+v.turret_angle
		camera.look_at(camera.position+Vector3(sin(a)*cos(v.gun_angle),sin(v.gun_angle),cos(a)*cos(v.gun_angle))*100)
	else:
		var movement=Vector3.ZERO
		if Input.is_physical_key_pressed(KEY_W):movement-=camera.global_basis.z
		if Input.is_physical_key_pressed(KEY_S):movement+=camera.global_basis.z
		if Input.is_physical_key_pressed(KEY_A):movement-=camera.global_basis.x
		if Input.is_physical_key_pressed(KEY_D):movement+=camera.global_basis.x
		if Input.is_physical_key_pressed(KEY_Q):movement.y-=1
		if Input.is_physical_key_pressed(KEY_E):movement.y+=1
		camera.position+=movement*dt*100
	var connection="BRAIN BACKEND DISCONNECTED · RULE_BASED_CONTROL"
	if requires_brain:connection="BRAIN WAITING" if not bridge.connected() else "2 × batch=8 · "+bridge.last_reply.get("mode","")
	hud.text="KRASNY VALLEY   /   FLYSWARM RESEARCH\nGERMANY  %03d  (%d alive)     USSR  %03d  (%d alive)\nA %d   B %d   C %d   |   %.1fs   %s   %s\n%s\nBrain tick %d  %.1fms   IPC %.1fms   FPS %d" % [tickets[0],alive_count(0),tickets[1],alive_count(1),objectives[0].owner,objectives[1].owner,objectives[2].owner,sim_time,"NORMALIZED" if normalized else "HISTORICAL",audio_mode,connection,bridge.tick,bridge.last_reply.get("tick_ms",0),bridge.latency_ms,Engine.get_frames_per_second()]
	detail.text="%s  ·  %s  ·  %s%d / local brain %d\nSpeed %.1f km/h    Gear %d    Ammo %d    Reload %.1fs\nTarget %d   Range %.0fm   LOS %s   Gun %.1f°\nDN %s   JO %.3f\nTAB agent  |  C camera  |  F1 debug  |  SPACE pause\nFree camera: WASD / Q E / arrows\n%s" % [v.cfg.display_name,v.cfg.role,"B" if v.team==0 else "R",v.agent_id%8+1,v.agent_id%8,v.speed*3.6,clampi(int(absf(v.speed)/3)+1,1,v.cfg.gears.size()),v.ammo_left,v.reload_left,v.target,v.target_range,str(v.seen),rad_to_deg(v.gun_angle),str(v.dn),v.audio_input,(str(v.modules)+"\n"+str(v.last_impact)) if debug else ""]
	if ended:detail.text+="\nBATTLE COMPLETE"
	if screenshot_path!="" and sim_time>float(option("--capture-at","3.6")) and DisplayServer.get_name()!="headless":
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(screenshot_path)
		screenshot_path=""
func _unhandled_input(event):
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_TAB:selected=(selected+1)%16
			KEY_C:camera_mode=(camera_mode+1)%4
			KEY_F1:debug=not debug
			KEY_SPACE:paused=not paused
			KEY_ESCAPE:get_tree().quit()
	if camera_mode==3:
		if Input.is_physical_key_pressed(KEY_LEFT):camera.rotate_y(.035)
		if Input.is_physical_key_pressed(KEY_RIGHT):camera.rotate_y(-.035)
		if Input.is_physical_key_pressed(KEY_UP):camera.rotate_object_local(Vector3.RIGHT,.035)
		if Input.is_physical_key_pressed(KEY_DOWN):camera.rotate_object_local(Vector3.RIGHT,-.035)
