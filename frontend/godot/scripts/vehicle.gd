extends CharacterBody3D
const Combat=preload("res://scripts/combat.gd")
const VehicleAppearance=preload("res://scripts/vehicles/vehicle_appearance.gd")
var cfg: Dictionary
var world
var agent_id=0
var team=0
var speed=0.0
var yaw_rate=0.0
var turret_angle=0.0
var gun_angle=0.0
var turret_rate=0.0
var gun_rate=0.0
var drive_throttle=0.0
var manual_aim=false
var manual_turret_target=0.0
var manual_gun_target=0.0
var manual_hull_target=0.0
var manual_hull_aim=false
var reload_left=0.0
var ammo_left=0
var alive=true
var target=-1
var target_range=0.0
var aim_error=0.0
var elevation_error=0.0
var seen=false
var previous_size=0.0
var looming=0.0
var cmd=[0.0,0.0,0.0,0.0,0.0,0.0]
var modules={}
var module_damage={}
var impact_history: Array[Dictionary]=[]
var volumes={}
var armour_bodies=[]
var metrics={"distance_travelled":0.0,"stationary_s":0.0,"reverse_s":0.0,"shots":0,"penetrations":0,"kills":0,"capture_s":0.0,"objective_presence_s":0.0,"contest_s":0.0,"target_switches":0,"target_visible_s":0.0,"chassis_aim_s":0.0,"stuck_recoveries":0}
var last_impact={}
var dn=[0,0,0,0,0]
var audio_input=0.0
var model: Node3D
var turret: Node3D
var gun: Node3D
var gun_rest=Vector3.ZERO
var muzzle: Node3D
var wheels=[]
var visual_hull: Node3D
var contact_state={"resistance":.055,"grip":.65,"slip":0.0,"depth":0.0,"pressure_pa":0.0}
var stuck_intent_s=0.0
var recovery_left_s=0.0
var recovery_turn=1.0

func setup(config: Dictionary, index: int, battle):
	cfg=config
	agent_id=index
	team=int(index/8)
	world=battle
	ammo_left=int(cfg.ammo_count)
	collision_layer=2
	collision_mask=3
	floor_snap_length=2.5
	floor_max_angle=deg_to_rad(40)
	var shape=CollisionShape3D.new()
	var box=BoxShape3D.new()
	box.size=Vector3(cfg.width_m-.3,1.4,cfg.length_m-.5)
	shape.shape=box
	# Keep the lower face of the CharacterBody collider at the vehicle root.
	shape.position.y=.7
	add_child(shape)
	for key in cfg.modules:
		var xyz=cfg.modules[key]
		volumes[key]=Vector3(xyz[0],xyz[1],xyz[2])
	for key in volumes:
		modules[key]=true
		module_damage[key]=0.0
	if world.is_demo and index not in [0,8]:
		model=Node3D.new()
		model.name="InactiveDemoVehicle_%d" % index
		add_child(model)
		_add_identification_label()
		alive=false
		visible=false
		collision_layer=0
		collision_mask=0
		return
	model=load("res://assets/vehicles/"+cfg.id+".glb").instantiate()
	add_child(model)
	VehicleAppearance.apply(model,str(cfg.id))
	turret=model.find_child("TurretPivot",true,false)
	gun=model.find_child("GunElevationPivot",true,false)
	muzzle=model.find_child("Muzzle",true,false)
	gun_rest=gun.position
	for child in model.find_children("Wheel*","MeshInstance3D",true,false): wheels.append(child)
	_add_identification_label()
	_add_demo_participant_mark()
	var l=float(cfg.length_m)/2
	var w=float(cfg.width_m)/2
	add_plate("upper_front",Vector3(0,1.4,l-.4),Vector3(w*1.8,1.0,.12),Vector3(deg_to_rad(-cfg.armour_data.upper_front.slope_deg),0,0))
	add_plate("lower_front",Vector3(0,.65,l-.15),Vector3(w*1.8,.65,.12),Vector3(deg_to_rad(-float(cfg.armour_data.lower_front.slope_deg)),0,0))
	add_plate("side",Vector3(-w+.18,1.15,0),Vector3(.15,1.6,l*1.9),Vector3.ZERO)
	add_plate("side",Vector3(w-.18,1.15,0),Vector3(.15,1.6,l*1.9),Vector3.ZERO)
	add_plate("rear",Vector3(0,1.2,-l+.2),Vector3(w*1.8,1.5,.15),Vector3.ZERO)
	add_plate("roof",Vector3(0,1.98,0),Vector3(w*1.8,.12,l*1.7),Vector3.ZERO)
	var mount=Node3D.new()
	mount.name="ArmourTurretPivot"
	add_child(mount)
	# The casemate sits far forward on the Jagdpanther and SU-100. Match the
	# actual vehicle asset pivot rather than placing every fighting compartment
	# at the same generic hull coordinate.
	mount.position=to_local(turret.global_position)+Vector3(0,.42 if cfg.turreted else 0,0)
	var front_zone="turret_front" if cfg.turreted else "casemate_front"
	add_plate(front_zone,Vector3(0,0,1.2),Vector3(2.5,.9,.12),Vector3(deg_to_rad(-float(cfg.armour_data[front_zone].slope_deg)),0,0),mount)
	for sign_value in [-1,1]: add_plate("turret_side" if cfg.turreted else "casemate_side",Vector3(sign_value*1.2,0,0),Vector3(.12,.9,2.5),Vector3.ZERO,mount)
	add_plate("turret_rear",Vector3(0,0,-1.2),Vector3(2.4,.9,.12),Vector3.ZERO,mount)
	add_plate("mantlet",Vector3(0,0,1.35),Vector3(.8,.6,.2),Vector3.ZERO,mount)

func _add_identification_label() -> void:
	var label=Label3D.new()
	label.text=("B" if team==0 else "R")+str(agent_id%8+1)+" · "+cfg.display_name
	label.position=Vector3(0,5,0)
	label.font_size=36
	label.pixel_size=.015
	label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	label.fixed_size=false
	label.name="Identification"
	label.outline_size=6
	label.modulate=Color(.35,.65,1) if team==0 else Color(1,.4,.25)
	label.visibility_range_end=4000
	add_child(label)

func _add_demo_participant_mark() -> void:
	if not world.is_demo or agent_id not in [0,8]:return
	var parent: Node3D=turret if is_instance_valid(turret) else model
	var bounds:=AABB()
	var found:=false
	var inverse:=parent.global_transform.affine_inverse()
	for node in parent.find_children("*", "MeshInstance3D", true, false):
		var mesh_node:=node as MeshInstance3D
		if mesh_node.mesh==null:continue
		var transform_to_parent:=inverse*mesh_node.global_transform
		for point in _box_corners(mesh_node.get_aabb()):
			var local_point:=transform_to_parent*point
			if not found:bounds=AABB(local_point,Vector3.ZERO);found=true
			else:bounds=bounds.expand(local_point)
	if not found:return
	var mark:=Sprite3D.new()
	mark.name="OpenDayParticipantMark"
	mark.texture=load("res://assets/environment/fly/flyswarm-mark.svg")
	mark.pixel_size=.0017
	mark.modulate=Color("83b5dd") if team==0 else Color("df925e")
	mark.rotation.x=-PI*.5
	mark.position=Vector3(bounds.get_center().x,bounds.end.y+.018,bounds.get_center().z)
	parent.add_child(mark)

func _box_corners(box: AABB) -> Array[Vector3]:
	var p:=box.position
	var e:=box.end
	return [p,Vector3(e.x,p.y,p.z),Vector3(p.x,e.y,p.z),Vector3(p.x,p.y,e.z),Vector3(e.x,e.y,p.z),Vector3(e.x,p.y,e.z),Vector3(p.x,e.y,e.z),e]

func add_plate(zone: String, pos: Vector3, size: Vector3, rot: Vector3, parent: Node3D=null):
	var body=StaticBody3D.new()
	(parent if parent else self).add_child(body)
	body.position=pos
	body.rotation=rot
	body.collision_layer=4
	body.collision_mask=0
	body.set_meta("vehicle",self)
	body.set_meta("zone",zone)
	var shape=CollisionShape3D.new()
	var b=BoxShape3D.new()
	b.size=size
	shape.shape=b
	body.add_child(shape)
	armour_bodies.append(body)

func excluded() -> Array[RID]:
	var ids: Array[RID]=[get_rid()]
	for b in armour_bodies: ids.append(b.get_rid())
	return ids

func sense(dt: float):
	if not alive:
		target=-1
		seen=false
		target_range=0.0
		aim_error=0.0
		elevation_error=0.0
		looming=0.0
		return
	var previous_target=target
	target=-1
	seen=false
	var nearest=1400.0
	for v in world.vehicles:
		if v.team==team or not v.alive: continue
		var delta=v.global_position-global_position
		var bearing=wrapf(atan2(delta.x,delta.z)-rotation.y,-PI,PI)
		if absf(bearing)>deg_to_rad(100): continue
		var distance=delta.length()
		if distance<nearest and world.has_los(self,v):
			nearest=distance
			target=v.agent_id
		if target>=0:
			seen=true
	if target>=0:
		var delta=world.vehicles[target].global_position+Vector3(0,1.6,0)-muzzle.global_position
		target_range=delta.length()
		aim_error=wrapf(atan2(delta.x,delta.z)-rotation.y-turret_angle,-PI,PI)
		elevation_error=atan2(delta.y,Vector2(delta.x,delta.z).length())-gun_angle+model.rotation.x
		var angular_size=2*atan(3.0/maxf(1,target_range))
		looming=maxf(0,(angular_size-previous_size)/maxf(dt,.001))
		previous_size=angular_size
	else:
		target_range=0
		aim_error=0
		elevation_error=0
		looming=0
	if previous_target!=target and previous_target>=0: metrics.target_switches+=1

func teacher() -> Array:
	# Rule AI may reason about scenario objectives. MaleCNS observations remain
	# unchanged: no objective XYZ or hidden "go capture B" command is injected
	# into the biological controller.
	var destination=world.objective_destination(self)
	var delta=destination-global_position
	var heading=wrapf(atan2(delta.x,delta.z)-rotation.y,-PI,PI)
	var steer=clampf(heading*2,-1,1)
	var throttle=.8 if absf(heading)<1.2 else .15
	if delta.length()<world.scenario.zone_radius*.6: throttle=0
	var front=global_position+Vector3(0,1.3,0)
	var query=PhysicsRayQueryParameters3D.create(front,front+global_basis.z*12,3,excluded())
	if not get_world_3d().direct_space_state.intersect_ray(query).is_empty():
		steer=1.0 if agent_id%2==0 else -1.0
		throttle=-.25
	var turn=0.0
	var elevate=0.0
	var fire=0.0
	if target>=0:
		turn=clampf(aim_error*4,-1,1)
		var flight=target_range/float(cfg.ammo_data.muzzle_velocity_m_s)
		var drop_angle=atan2(4.905*flight*flight,maxf(1,target_range))
		elevate=clampf((elevation_error+drop_angle)*6,-1,1)
		if not cfg.turreted and absf(aim_error)>.05:
			steer=clampf(aim_error*2,-1,1)
		if absf(aim_error)<.015 and absf(elevation_error+drop_angle)<.012: fire=1
	if world.training:
		throttle=0
		steer=0
	return [throttle,0.0,steer,turn,elevate,fire]

func step(dt: float):
	if not alive: return
	reload_left=maxf(0,reload_left-dt)
	gun.position=gun.position.lerp(gun_rest,minf(1,dt*8))
	var old=global_position
	var requested_throttle=float(cmd[0])
	var throttle=requested_throttle
	var steer=float(cmd[2])
	if manual_hull_aim:
		var hull_error=wrapf(manual_hull_target-rotation.y,-PI,PI)
		var pivot_at_speed=1.0 if cfg.neutral_steering else clampf(absf(speed)/2,.15,1)
		var hull_max=deg_to_rad(float(cfg.turn_rate_deg_s))*pivot_at_speed/(1.0+absf(speed)*.08)
		var hull_accel=deg_to_rad(float(cfg.hull_yaw_accel_deg_s2))
		var hull_stop_rate=sqrt(2.0*hull_accel*absf(hull_error))
		steer=clampf(signf(hull_error)*minf(hull_max,hull_stop_rate)/maxf(.01,hull_max),-1.0,1.0)
		if absf(hull_error)<.001 and absf(yaw_rate)<.002:steer=0.0
	var mechanically_mobile=bool(modules.engine and modules.track_left and modules.track_right)
	if not mechanically_mobile:
		throttle=0;steer=0;speed=0
		stuck_intent_s=0.0
		recovery_left_s=0.0
	if not modules.driver: throttle*=.2;steer*=.2

	# Deterministic anti-deadlock manoeuvre. It does not choose objectives or
	# targets; it only frees a mechanically mobile tank that has been ordered
	# to move but has made virtually no progress for several seconds.
	if mechanically_mobile and recovery_left_s>0.0:
		if recovery_left_s>1.35:
			throttle=-.60
			steer=recovery_turn
		else:
			throttle=.72
			steer=-recovery_turn*.72
		recovery_left_s=maxf(0.0,recovery_left_s-dt)

	var slope=(world.terrain.height_at(position.x+sin(rotation.y)*3,position.z+cos(rotation.y)*3)-world.terrain.height_at(position.x,position.z))/3
	contact_state=world.tracks.contact(self,dt)
	drive_throttle=move_toward(drive_throttle,throttle,dt/maxf(.05,float(cfg.throttle_response_s)))
	var power_acc=minf(minf(minf(float(cfg.traction),contact_state.grip)*9.81,float(cfg.engine_kw)*1000*.7/(float(cfg.mass_kg)*maxf(2,absf(speed)))),float(cfg.drive_accel_m_s2))
	if not modules.transmission: power_acc*=.2
	var accel=drive_throttle*power_acc-slope*9.81
	if absf(speed)>.05: accel-=signf(speed)*float(contact_state.resistance)*9.81
	if absf(throttle)<.01 or cmd[1]>.5: speed=move_toward(speed,0,float(cfg.brake_m_s2)*dt)
	else: speed+=accel*dt
	var road=absf(position.x)<20 or absf(position.z)<12
	var limit=float(cfg.max_speed_kph if road else cfg.cross_country_kph)/3.6
	speed=clampf(speed,-float(cfg.reverse_kph)/3.6,limit)
	speed*=1-absf(steer)*float(cfg.steering_loss)*dt
	var pivot=1.0 if cfg.neutral_steering else clampf(absf(speed)/2,.15,1)
	var desired_yaw_rate=steer*deg_to_rad(cfg.turn_rate_deg_s)*pivot/(1+absf(speed)*.08)
	yaw_rate=move_toward(yaw_rate,desired_yaw_rate,deg_to_rad(float(cfg.hull_yaw_accel_deg_s2))*dt) if mechanically_mobile else 0.0
	if manual_hull_aim:
		var remaining_hull=wrapf(manual_hull_target-rotation.y,-PI,PI)
		if signf(yaw_rate)==signf(remaining_hull) and absf(yaw_rate*dt)>=absf(remaining_hull):
			rotation.y=manual_hull_target
			yaw_rate=0.0
		else:
			rotation.y=wrapf(rotation.y+yaw_rate*dt,-PI,PI)
	else:
		rotation.y+=yaw_rate*dt
	velocity=Vector3(sin(rotation.y)*speed,-9.81,cos(rotation.y)*speed)
	move_and_slide()
	position.x=clampf(position.x,-world.terrain.extent+8,world.terrain.extent-8)
	position.z=clampf(position.z,-world.terrain.extent+8,world.terrain.extent-8)
	var terrain_floor=world.terrain.height_at(position.x,position.z)+.08
	if position.y<terrain_floor:
		position.y=terrain_floor
		if velocity.y<0.0:velocity.y=0.0

	var moved=Vector2(global_position.x-old.x,global_position.z-old.z).length()
	if mechanically_mobile and recovery_left_s<=0.0 and absf(requested_throttle)>.25 and moved<.025 and absf(speed)<.45 and not world.training:
		stuck_intent_s+=dt
		if stuck_intent_s>=2.8:
			stuck_intent_s=0.0
			recovery_left_s=2.7
			recovery_turn=1.0 if (agent_id+int(world.sim_time/3.0))%2==0 else -1.0
			metrics.stuck_recoveries+=1
	else:
		if moved>.06 or absf(requested_throttle)<=.25 or recovery_left_s>0.0:
			stuck_intent_s=0.0

	var traverse_factor=1.0 if modules.turret_drive else .1
	var turret_max=deg_to_rad(float(cfg.turret_rate_deg_s))*traverse_factor
	var gun_max=deg_to_rad(float(cfg.gun_rate_deg_s))*traverse_factor
	var desired_turret_rate=0.0
	var desired_gun_rate=0.0
	if not modules.gunner:
		turret_rate=0.0
		gun_rate=0.0
	if modules.gunner:
		if manual_aim:
			var turret_error=wrapf(manual_turret_target-turret_angle,-PI,PI) if cfg.turreted else manual_turret_target-turret_angle
			var gun_error=manual_gun_target-gun_angle
			desired_turret_rate=signf(turret_error)*minf(turret_max,sqrt(2.0*deg_to_rad(float(cfg.turret_accel_deg_s2))*traverse_factor*absf(turret_error)))
			desired_gun_rate=signf(gun_error)*minf(gun_max,sqrt(2.0*deg_to_rad(float(cfg.gun_accel_deg_s2))*traverse_factor*absf(gun_error)))
		else:
			desired_turret_rate=clampf(float(cmd[3]),-1,1)*turret_max
			desired_gun_rate=clampf(float(cmd[4]),-1,1)*gun_max
	turret_rate=move_toward(turret_rate,desired_turret_rate,deg_to_rad(float(cfg.turret_accel_deg_s2))*traverse_factor*dt)
	gun_rate=move_toward(gun_rate,desired_gun_rate,deg_to_rad(float(cfg.gun_accel_deg_s2))*traverse_factor*dt)
	if manual_aim and modules.gunner:
		var remaining=wrapf(manual_turret_target-turret_angle,-PI,PI) if cfg.turreted else manual_turret_target-turret_angle
		turret_angle+=clampf(turret_rate*dt,-absf(remaining),absf(remaining))
		if absf(remaining)<=absf(turret_rate*dt):turret_rate=0.0
		remaining=manual_gun_target-gun_angle
		gun_angle+=clampf(gun_rate*dt,-absf(remaining),absf(remaining))
		if absf(remaining)<=absf(gun_rate*dt):gun_rate=0.0
	else:
		turret_angle+=turret_rate*dt
		gun_angle+=gun_rate*dt
	turret_angle=wrapf(turret_angle,-PI,PI) if cfg.turreted else clampf(turret_angle,-deg_to_rad(cfg.traverse_limit_deg),deg_to_rad(cfg.traverse_limit_deg))
	gun_angle=clampf(gun_angle,deg_to_rad(cfg.elevation_deg[0]),deg_to_rad(cfg.elevation_deg[1]))
	if not cfg.turreted and absf(turret_angle)>=deg_to_rad(cfg.traverse_limit_deg)-.0001:turret_rate=0.0
	if gun_angle<=deg_to_rad(cfg.elevation_deg[0])+.0001 or gun_angle>=deg_to_rad(cfg.elevation_deg[1])-.0001:gun_rate=0.0
	if turret: turret.rotation.y=turret_angle
	if gun: gun.rotation.x=-gun_angle
	get_node("ArmourTurretPivot").rotation.y=turret_angle if cfg.turreted else 0
	model.rotation.x=lerpf(model.rotation.x,-atan(slope),dt*5)
	var side_slope=(world.terrain.height_at(position.x+cos(rotation.y)*2,position.z-sin(rotation.y)*2)-world.terrain.height_at(position.x,position.z))/2
	model.rotation.z=lerpf(model.rotation.z,atan(side_slope),dt*5)
	for wheel in wheels: wheel.rotate_x(speed*dt/.45)
	if cmd[5]>.5 and reload_left<=0 and ammo_left>0 and modules.breech and modules.gunner:
		world.fire(self)
		gun.position-=Vector3(0,0,.22)
		reload_left=float(cfg.reload_s)*(1 if modules.loader else 2.5)
		ammo_left-=1
		metrics.shots+=1
	metrics.distance_travelled+=moved
	if absf(speed)<.2:metrics.stationary_s+=dt
	if speed<-.1:metrics.reverse_s+=dt
	if seen:metrics.target_visible_s+=dt
	if target>=0 and absf(yaw_rate)>.02:metrics.chassis_aim_s+=dt

func hit(shell: Dictionary, point: Vector3, normal: Vector3, zone: String):
	if not alive:return
	last_impact=Combat.impact(shell.ammo,shell.distance,shell.velocity,normal,cfg.armour_data[zone])
	last_impact.shell=shell.ammo.get("id","unknown")
	last_impact.impact_speed_m_s=shell.velocity.length()
	last_impact.nominal_thickness_mm=cfg.armour_data[zone].thickness_mm
	last_impact.zone=zone
	last_impact.distance=shell.distance
	last_impact.damaged=[]
	var local_start=to_local(point)
	var local_direction=global_basis.inverse()*shell.velocity.normalized()
	last_impact.point_local=[local_start.x,local_start.y,local_start.z]
	last_impact.incoming_local=[local_direction.x,local_direction.y,local_direction.z]
	if not last_impact.penetrated:
		last_impact.outcome="ricochet" if last_impact.ricochet else "non_penetration"
		last_impact.disabled=[]
		_record_impact(shell)
		return
	world.vehicles[shell.owner].metrics.penetrations+=1
	var start=local_start
	var direction=local_direction.normalized()
	var disabled=[]
	var damaged=[]
	var remaining=float(last_impact.remaining_penetration_mm)
	var energy_fraction=clampf(remaining/maxf(1.0,float(last_impact.capability)),0.0,1.0)
	var travel_limit=.55+4.0*sqrt(energy_fraction)
	var cone_slope=tan(deg_to_rad(12.0))
	var turret_pivot=to_local(turret.global_position)
	for key in volumes:
		var centre: Vector3=volumes[key]
		if cfg.turreted and key in ["gunner","commander","loader","breech","turret_drive"]:
			centre=turret_pivot+Basis(Vector3.UP,turret_angle)*(centre-turret_pivot)
		var relative=centre-start
		var depth=relative.dot(direction)
		if depth<0.0 or depth>travel_limit:continue
		var miss_distance=(relative-direction*depth).length()
		var direct_radius=module_radius(key)
		var direct_path_radius=.055+depth*.018
		var fragment_radius=direct_radius+minf(.72,depth*cone_slope)
		if miss_distance>fragment_radius:continue
		var severity=0.0
		if miss_distance<=direct_radius+direct_path_radius:
			severity=1.8 if key!="ammo_rack" else 1.55
		else:
			# A penetrating round sheds a widening, directional cone of fragments.
			# Their energy fades with distance from the penetrator and along the
			# post-armour path; repeated hits accumulate against module strength.
			var cone_width=maxf(.001,fragment_radius-direct_radius)
			var lateral_fraction=clampf((miss_distance-direct_radius)/cone_width,0.0,1.0)
			var falloff=1.0-lateral_fraction*.72
			var residual=clampf(1.0-depth/maxf(.1,travel_limit),.12,1.0)
			severity=(.72 if key=="ammo_rack" else 1.05)*falloff*sqrt(energy_fraction)*residual
		module_damage[key]=minf(3.0,float(module_damage.get(key,0.0))+severity)
		if not damaged.has(key):damaged.append(key)
		var threshold=1.0 if key in ["driver","gunner","commander","loader","radio_operator"] else (1.35 if key=="ammo_rack" else 1.6)
		if module_damage[key]>=threshold and bool(modules.get(key,true)):
			modules[key]=false
			disabled.append(key)
	last_impact.damaged=damaged
	last_impact.disabled=disabled
	last_impact.outcome="critical" if not disabled.is_empty() else ("minor_damage" if not damaged.is_empty() else "penetration_no_internal_damage")
	var crew_keys=["driver","gunner","commander","loader","radio_operator"]
	var crew_total=0
	var crew_alive=0
	for crew_key in crew_keys:
		if modules.has(crew_key):
			crew_total+=1
			if bool(modules[crew_key]):crew_alive+=1
	var ammo_destroyed=(modules.has("ammo_rack") and not bool(modules["ammo_rack"]))
	var crew_knockout=(crew_total>=2 and crew_alive<=1)
	last_impact.crew_alive=crew_alive
	last_impact.crew_total=crew_total
	last_impact.destroyed_modules=[]
	for key in modules:
		if not bool(modules[key]):last_impact.destroyed_modules.append(key)
	if ammo_destroyed or crew_knockout:
		last_impact.outcome="lethal"
		last_impact.kill_reason="ammo_rack" if ammo_destroyed else "crew_knockout"
		destroy_vehicle(int(shell.owner))
	_record_impact(shell)

func _record_impact(shell: Dictionary) -> void:
	last_impact.shot_number=impact_history.size()+1
	last_impact.shooter=int(shell.get("owner",-1))
	last_impact.module_damage=module_damage.duplicate(true)
	last_impact.modules=modules.duplicate(true)
	last_impact.destroyed_modules=[]
	for key in modules:
		if not bool(modules[key]):last_impact.destroyed_modules.append(key)
	impact_history.append(last_impact.duplicate(true))

func impact_module_positions() -> Dictionary:
	var result={}
	var pivot=to_local(turret.global_position) if is_instance_valid(turret) else Vector3.ZERO
	for key in volumes:
		var centre: Vector3=volumes[key]
		if cfg.turreted and key in ["gunner","commander","loader","breech","turret_drive"]:
			centre=pivot+Basis(Vector3.UP,turret_angle)*(centre-pivot)
		result[key]=[centre.x,centre.y,centre.z]
	return result

func module_radius(key: String) -> float:
	if key in ["driver","gunner","commander","loader","radio_operator"]:return .38
	if key=="ammo_rack":return .44
	if key in ["engine","transmission","fuel"]:return .58
	if key in ["track_left","track_right"]:return .43
	return .43

func destroy_vehicle(killer_id: int):
	if not alive:return
	alive=false
	speed=0.0
	velocity=Vector3.ZERO
	yaw_rate=0.0
	turret_rate=0.0
	gun_rate=0.0
	drive_throttle=0.0
	cmd=[0.0,0.0,0.0,0.0,0.0,0.0]
	stuck_intent_s=0.0
	recovery_left_s=0.0
	world.tickets[team]=maxf(0.0,float(world.tickets[team])-float(world.scenario.loss_cost))
	if killer_id>=0 and killer_id<world.vehicles.size():world.vehicles[killer_id].metrics.kills+=1
	var catastrophic=not bool(modules.get("ammo_rack",true))
	if world.has_method("vehicle_destroyed_effect"):
		world.vehicle_destroyed_effect(global_position+Vector3(0,1.0,0),catastrophic)
	else:
		world.effect(global_position+Vector3(0,1.5,0),Color(.16,.13,.10),1.5,2.2)
	VehicleAppearance.set_destroyed(model,str(cfg.id),true)
	if gun:gun.rotation.x=deg_to_rad(8.0)
	var identification=find_child("Identification",true,false)
	if identification is Label3D:
		identification.text="× "+("B" if team==0 else "R")+str(agent_id%8+1)+" · "+str(cfg.display_name)
		identification.modulate=Color(.48,.48,.46)

func reset_destroyed_state():
	alive=true
	speed=0.0
	velocity=Vector3.ZERO
	yaw_rate=0.0
	turret_rate=0.0
	gun_rate=0.0
	drive_throttle=0.0
	manual_aim=false
	manual_hull_aim=false
	reload_left=0.0
	last_impact={}
	impact_history.clear()
	stuck_intent_s=0.0
	recovery_left_s=0.0
	cmd=[0.0,0.0,0.0,0.0,0.0,0.0]
	for key in modules:
		modules[key]=true
		module_damage[key]=0.0
	VehicleAppearance.set_destroyed(model,str(cfg.id),false)
	var identification=find_child("Identification",true,false)
	if identification is Label3D:
		identification.text=("B" if team==0 else "R")+str(agent_id%8+1)+" · "+str(cfg.display_name)
		identification.modulate=Color(.35,.65,1.0) if team==0 else Color(1.0,.4,.25)

func observation() -> Dictionary:
	return {"id":agent_id,"vehicle":cfg.id,"alive":alive,"position":[position.x,position.y,position.z],"bearing":aim_error,"elevation":elevation_error,"visible":seen,"angular_size":previous_size if seen else 0.0,"looming":looming,"proprio":[speed/(cfg.max_speed_kph/3.6),yaw_rate,reload_left/maxf(1,cfg.reload_s),turret_angle/PI,gun_angle,1.0 if modules.engine else 0.0],"rl_task":world.rl_task_features(self),"teacher":teacher(),"target":target}
