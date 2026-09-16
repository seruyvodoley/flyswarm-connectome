extends CharacterBody3D
const Combat=preload("res://scripts/combat.gd")
var cfg: Dictionary
var world
var agent_id=0
var team=0
var speed=0.0
var yaw_rate=0.0
var turret_angle=0.0
var gun_angle=0.0
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
var volumes={}
var armour_bodies=[]
var metrics={"distance_travelled":0.0,"stationary_s":0.0,"reverse_s":0.0,"shots":0,"penetrations":0,"kills":0,"capture_s":0.0,"target_switches":0,"target_visible_s":0.0,"chassis_aim_s":0.0}
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
	shape.position.y=1.0
	add_child(shape)
	model=load("res://assets/vehicles/"+cfg.id+".glb").instantiate()
	add_child(model)
	turret=model.find_child("TurretPivot",true,false)
	gun=model.find_child("GunElevationPivot",true,false)
	muzzle=model.find_child("Muzzle",true,false)
	gun_rest=gun.position
	for child in model.find_children("Wheel*","MeshInstance3D",true,false): wheels.append(child)
	var label=Label3D.new()
	label.text=("B" if team==0 else "R")+str(index%8+1)+" · "+cfg.display_name
	label.position=Vector3(0,5,0)
	label.font_size=36
	label.pixel_size=.015
	label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate=Color(.35,.65,1) if team==0 else Color(1,.4,.25)
	label.visibility_range_end=300
	add_child(label)
	var l=float(cfg.length_m)/2
	var w=float(cfg.width_m)/2
	add_plate("upper_front",Vector3(0,1.4,l-.4),Vector3(w*1.8,1.0,.12),Vector3(deg_to_rad(-cfg.armour_data.upper_front.slope_deg),0,0))
	add_plate("lower_front",Vector3(0,.65,l-.15),Vector3(w*1.8,.65,.12),Vector3.ZERO)
	add_plate("side",Vector3(-w+.18,1.15,0),Vector3(.15,1.6,l*1.9),Vector3.ZERO)
	add_plate("side",Vector3(w-.18,1.15,0),Vector3(.15,1.6,l*1.9),Vector3.ZERO)
	add_plate("rear",Vector3(0,1.2,-l+.2),Vector3(w*1.8,1.5,.15),Vector3.ZERO)
	add_plate("roof",Vector3(0,1.98,0),Vector3(w*1.8,.12,l*1.7),Vector3.ZERO)
	var mount=Node3D.new()
	mount.name="ArmourTurretPivot"
	add_child(mount)
	mount.position=Vector3(0,2.3,.4)
	add_plate("turret_front" if cfg.turreted else "casemate_front",Vector3(0,0,1.2),Vector3(2.5,.9,.12),Vector3.ZERO,mount)
	for sign_value in [-1,1]: add_plate("turret_side" if cfg.turreted else "casemate_side",Vector3(sign_value*1.2,0,0),Vector3(.12,.9,2.5),Vector3.ZERO,mount)
	add_plate("turret_rear",Vector3(0,0,-1.2),Vector3(2.4,.9,.12),Vector3.ZERO,mount)
	add_plate("mantlet",Vector3(0,0,1.35),Vector3(.8,.6,.2),Vector3.ZERO,mount)
	for key in cfg.modules:
		var xyz=cfg.modules[key]
		volumes[key]=Vector3(xyz[0],xyz[1],xyz[2])
	for key in volumes: modules[key]=true

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
	var destination=world.objectives[agent_id%3].position
	var delta=destination-global_position
	var heading=wrapf(atan2(delta.x,delta.z)-rotation.y,-PI,PI)
	var steer=clampf(heading*2,-1,1)
	var throttle=.8 if absf(heading)<1.2 else .15
	if delta.length()<world.scenario.zone_radius*.6: throttle=0
	# Short forward obstacle probe. Does not assign roles by vehicle class.
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
	var throttle=float(cmd[0])
	var steer=float(cmd[2])
	if not modules.engine or not modules.track_left or not modules.track_right: throttle=0;steer=0;speed=0
	if not modules.driver: throttle*=.2;steer*=.2
	var slope=(world.terrain.height_at(position.x+sin(rotation.y)*3,position.z+cos(rotation.y)*3)-world.terrain.height_at(position.x,position.z))/3
	contact_state=world.tracks.contact(self,dt)
	var power_acc=minf(minf(float(cfg.traction),contact_state.grip)*9.81,float(cfg.engine_kw)*1000*.7/(float(cfg.mass_kg)*maxf(2,absf(speed))))
	if not modules.transmission: power_acc*=.2
	var accel=throttle*power_acc-slope*9.81
	if absf(speed)>.05: accel-=signf(speed)*float(contact_state.resistance)*9.81
	if absf(throttle)<.01 or cmd[1]>.5: speed=move_toward(speed,0,float(cfg.brake_m_s2)*dt)
	else: speed+=accel*dt
	var road=absf(position.x)<20 or absf(position.z)<12
	var limit=float(cfg.max_speed_kph if road else cfg.cross_country_kph)/3.6
	speed=clampf(speed,-float(cfg.reverse_kph)/3.6,limit)
	speed*=1-absf(steer)*float(cfg.steering_loss)*dt
	var pivot=1.0 if cfg.neutral_steering else clampf(absf(speed)/2,.15,1)
	yaw_rate=steer*deg_to_rad(cfg.turn_rate_deg_s)*pivot/(1+absf(speed)*.08)
	rotation.y+=yaw_rate*dt
	velocity=Vector3(sin(rotation.y)*speed,-9.81,cos(rotation.y)*speed)
	move_and_slide()
	position.x=clampf(position.x,-world.terrain.extent+8,world.terrain.extent-8)
	position.z=clampf(position.z,-world.terrain.extent+8,world.terrain.extent-8)
	if position.y<world.terrain.height_at(position.x,position.z)-2: position.y=world.terrain.height_at(position.x,position.z)+.05
	var traverse_factor=1.0 if modules.turret_drive else .1
	if modules.gunner:
		turret_angle+=float(cmd[3])*deg_to_rad(cfg.turret_rate_deg_s)*dt*traverse_factor
		turret_angle=wrapf(turret_angle,-PI,PI) if cfg.turreted else clampf(turret_angle,-deg_to_rad(cfg.traverse_limit_deg),deg_to_rad(cfg.traverse_limit_deg))
		gun_angle=clampf(gun_angle+float(cmd[4])*.12*dt,deg_to_rad(cfg.elevation_deg[0]),deg_to_rad(cfg.elevation_deg[1]))
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
	metrics.distance_travelled+=Vector2(global_position.x-old.x,global_position.z-old.z).length()
	if absf(speed)<.2:metrics.stationary_s+=dt
	if speed<-.1:metrics.reverse_s+=dt
	if seen:metrics.target_visible_s+=dt
	if target>=0 and absf(yaw_rate)>.02:metrics.chassis_aim_s+=dt

func hit(shell: Dictionary, point: Vector3, normal: Vector3, zone: String):
	if not alive:return
	last_impact=Combat.impact(shell.ammo,shell.distance,shell.velocity,normal,cfg.armour_data[zone])
	last_impact.zone=zone
	last_impact.distance=shell.distance
	last_impact.damaged=[]
	if not last_impact.penetrated:return
	world.vehicles[shell.owner].metrics.penetrations+=1
	var start=to_local(point)
	var direction=global_basis.inverse()*shell.velocity.normalized()
	for key in volumes:
		var relative=volumes[key]-start
		var depth=relative.dot(direction)
		if depth<0 or depth>float(cfg.length_m):continue
		var radius=.4+depth*.16
		if (relative-direction*depth).length()<radius:
			modules[key]=false
			last_impact.damaged.append(key)
	if not modules.ammo_rack or (not modules.gunner and not modules.commander and not modules.driver):
		alive=false
		speed=0
		world.tickets[team]-=world.scenario.loss_cost
		world.vehicles[shell.owner].metrics.kills+=1
		world.effect(global_position+Vector3(0,2,0),Color(.15,.13,.11),5,8)
		var charred=StandardMaterial3D.new()
		charred.albedo_color=Color(.12,.10,.08)
		charred.roughness=1
		for mesh in model.find_children("*","MeshInstance3D",true,false):mesh.material_override=charred

func observation() -> Dictionary:
	return {"id":agent_id,"vehicle":cfg.id,"alive":alive,"position":[position.x,position.y,position.z],"bearing":aim_error,"elevation":elevation_error,"visible":seen,"angular_size":previous_size if seen else 0.0,"looming":looming,"proprio":[speed/(cfg.max_speed_kph/3.6),yaw_rate,reload_left/maxf(1,cfg.reload_s),turret_angle/PI,gun_angle,1.0 if modules.engine else 0.0],"teacher":teacher(),"target":target}
