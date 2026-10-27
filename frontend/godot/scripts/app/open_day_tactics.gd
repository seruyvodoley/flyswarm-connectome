extends RefCounted

# Open Day gameplay assistance. The real CNS remains frozen and connected;
# this deliberately strong, external controller never changes scientific modes.
var random=RandomNumberGenerator.new()
var next_decision=-1.0
var mode="flank"
var flank_sign=1.0
var standoff=180.0
var goal=Vector3.ZERO
var route=PackedVector3Array()
var route_index=0
var last_target=Vector3.INF
var last_seen=-100.0
var mode_since=0.0
var last_shots=0
var last_relocation_shots=0
var last_sample_yaw=0.0
var last_sample=Vector3.INF
var stuck_since=0.0
var reverse_until=-1.0
var blocked_goals={}
var state_seconds={}
var position_changes=0
var flank_attempts=0
var recoveries=0
var decisions=0
var decision_ms=0.0
var plan_cache={}

func configure(match_seed: int) -> void:
	random.seed=match_seed ^ 0x4F50454E
	next_decision=-1.0;last_seen=-100;mode_since=0;last_shots=0;last_relocation_shots=0
	flank_sign=1.0 if random.randf()>.5 else -1.0
	route.clear();blocked_goals.clear();state_seconds.clear();plan_cache.clear()
	last_sample=Vector3.INF;last_target=Vector3.INF
	position_changes=0;flank_attempts=0;recoveries=0;decisions=0;decision_ms=0

func preferred_range(cfg: Dictionary) -> float:
	# Longer barrels / casemates exploit distance; T-34 keeps room to manoeuvre.
	var speed=float(cfg.ammo_data.muzzle_velocity_m_s)
	return clampf(145.0+(speed-650.0)*.17+(28.0 if not cfg.turreted else 0.0),140.0,225.0)

func update(now: float, vehicle, target, nav, visible: bool, threatened: bool, health: float, dt: float) -> Dictionary:
	state_seconds[mode]=float(state_seconds.get(mode,0.0))+dt
	if visible:last_seen=now
	standoff=preferred_range(vehicle.cfg)
	var distance=vehicle.position.distance_to(target.position)
	var radial=vehicle.position-target.position;radial.y=0
	var closing=(target.velocity-vehicle.velocity).dot(radial.normalized())
	var reloading=vehicle.reload_left>.7
	var aim_elevation=vehicle.aim_angles_for_direction((target.position+Vector3.UP*1.45-vehicle.muzzle.global_position).normalized()).y
	var elevation_ok=aim_elevation>=deg_to_rad(float(vehicle.cfg.elevation_deg[0]))-.01 and aim_elevation<=deg_to_rad(float(vehicle.cfg.elevation_deg[1]))+.01
	var shots=int(vehicle.metrics.shots)
	if now>=next_decision:
		var started=Time.get_ticks_usec()
		var previous=mode
		var minimum=standoff*.57
		var withdrawal=distance<minimum or (threatened and reloading and (health<.55 or closing>2.0))
		if mode=="relocate" and now-mode_since<5.0 and route_index<route.size():pass
		elif mode=="disengage" and now-mode_since<5.0 and route_index<route.size():pass
		elif withdrawal:mode="disengage"
		elif visible and reloading and threatened and shots>last_relocation_shots:mode="relocate"
		elif visible and not elevation_ok:mode="relocate"
		elif visible and distance>=minimum and distance<=standoff+55.0:mode="hold"
		elif not visible and last_seen>0 and now-last_seen<4.5:mode="ambush"
		elif not visible:mode="flank"
		else:mode="pressure"
		if mode!=previous or decisions==0:
			mode_since=now
			if mode=="flank":flank_attempts+=1
			if mode=="relocate":last_relocation_shots=shots
		# A selected route persists between decisions. Replan after target motion,
		# a state change or blocked progress, never on every 50 Hz physics tick.
		var needs_route=route.is_empty() or mode!=previous or last_target.distance_to(target.position)>28.0 or route_index>=route.size()
		if mode in ["hold","ambush"]:
			route.clear();route_index=0;goal=vehicle.position
		elif needs_route:
			choose_position(now,vehicle,target,nav)
			last_target=target.position
		var turning=absf(wrapf(vehicle.rotation.y-last_sample_yaw,-PI,PI))>.08
		if last_sample!=Vector3.INF and previous not in ["hold","ambush"] and mode not in ["hold","ambush"] and vehicle.position.distance_to(last_sample)<.7 and not turning:
			if now-stuck_since>3.5:
				blocked_goals[Vector2i(roundi(goal.x/14),roundi(goal.z/14))]=now+20.0
				reverse_until=now+1.6;recoveries+=1;flank_sign=-flank_sign
				route.clear();route_index=0;stuck_since=now
		else:stuck_since=now
		last_sample=vehicle.position;last_sample_yaw=vehicle.rotation.y
		next_decision=now+1.2
		last_shots=shots;decisions+=1;decision_ms+=(Time.get_ticks_usec()-started)/1000.0
	while route_index<route.size() and vehicle.position.distance_to(route[route_index])<6.0:route_index+=1
	var waypoint=route[route_index] if route_index<route.size() else vehicle.position
	plan_cache={"mode":mode,"flank_sign":flank_sign,"standoff":standoff,"next_decision":next_decision,"goal":goal,"waypoint":waypoint,"route_remaining":route.size()-route_index,"reverse":now<reverse_until,"holding":mode in ["hold","ambush"]}
	return plan_cache.duplicate()

func choose_position(now: float, vehicle, target, nav) -> void:
	var from=Vector2(vehicle.position.x,vehicle.position.z)
	var enemy=Vector2(target.position.x,target.position.z)
	var radial=(from-enemy).normalized()
	if radial.length_squared()<.1:radial=Vector2(0,1)
	var candidates=[]
	# Firing arcs around the enemy plus local covered alternatives. Every chosen
	# destination must have a complete graph route, including a withdrawal exit.
	for angle in [-85,-55,-30,0,30,55,85]:
		var offset=radial.rotated(deg_to_rad(float(angle))*flank_sign)*standoff
		candidates.append(enemy+offset)
	for radius in [28.0,56.0,84.0]:
		for i in 8:candidates.append(from+radial.rotated(float(i)*TAU/8.0)*radius)
	var ranked=[]
	for p in candidates:
		if absf(p.x)>310 or absf(p.y)>310 or not nav.passable(p):continue
		var id=nav.closest(p)
		if float(blocked_goals.get(id,0))>now:continue
		var point=nav.point(Vector2(id)*nav.CELL)
		var range_m=point.distance_to(target.position)
		var gun_los=nav.line_clear(point+Vector3.UP*1.65,target.position+Vector3.UP*1.45)
		var hull_los=nav.line_clear(point+Vector3.UP*.7,target.position+Vector3.UP*1.45)
		var travel=point.distance_to(vehicle.position)
		if travel<16.0:continue
		var bearing=atan2(point.x-vehicle.position.x,point.z-vehicle.position.z)
		var turn=absf(wrapf(bearing-vehicle.rotation.y,-PI,PI))
		var score=-absf(range_m-standoff)*.20-travel*.07-turn*2.0
		var exit_count=0
		for offset in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]:
			if nav.grid.is_in_boundsv(id+offset) and not nav.grid.is_point_solid(id+offset):exit_count+=1
		if exit_count<2:continue
		score+=exit_count*.6
		if gun_los:score+=22.0
		if gun_los and not hull_los:score+=12.0
		if mode=="disengage":
			score+=(range_m-vehicle.position.distance_to(target.position))*.65
			if not gun_los:score+=30.0
		elif mode=="relocate":
			if not gun_los:score+=25.0
		elif mode=="flank":
			var angle=radial.angle_to((p-enemy).normalized())*flank_sign
			score+=clampf(angle,-1.2,1.2)*17.0
		# Seeded tie-breaking is tiny; cover/range/reachability dominate choices.
		score+=random.randf()*.8
		ranked.append({"score":score,"point":point})
	ranked.sort_custom(func(a,b):return a.score>b.score)
	var best_score=-INF;var best_route=PackedVector3Array();var best_goal=goal
	for candidate in ranked.slice(0,10):
		var proposed=nav.path(vehicle.position,candidate.point)
		if proposed.size()<2:continue
		if proposed[-1].distance_to(candidate.point)>20.0:continue
		var path_length=0.0
		for i in range(1,proposed.size()):path_length+=proposed[i-1].distance_to(proposed[i])
		var score=float(candidate.score)-maxf(0.0,path_length-vehicle.position.distance_to(candidate.point))*.13
		if score>best_score:best_score=score;best_route=proposed;best_goal=candidate.point
	if not best_route.is_empty():
		goal=best_goal;route=best_route;route_index=1;position_changes+=1;return
	route.clear();route_index=0

func drive(vehicle, waypoint: Vector3, holding: bool, reverse: bool, source: Array) -> Array:
	var delta=waypoint-vehicle.position;delta.y=0
	var error=wrapf(atan2(delta.x,delta.z)-vehicle.rotation.y,-PI,PI)
	if reverse:return [-.48,0.0,flank_sign*.65]
	if holding or delta.length()<4.0:return [0.0,1.0,0.0]
	# Pivot before advancing into a tight turn. Neural bias tapers near the
	# waypoint and can never override a deliberate braking/holding decision.
	if absf(error)>1.05:return [0.0,1.0,clampf(error*1.8,-1.0,1.0)]
	var forward=Vector3(sin(vehicle.rotation.y),0,cos(vehicle.rotation.y))
	var ahead=vehicle.position+forward*3.0
	var slope=(vehicle.world.terrain.height_at(ahead.x,ahead.z)-vehicle.world.terrain.height_at(vehicle.position.x,vehicle.position.z))/3.0
	var throttle=1.0 if slope>.015 else clampf(.88+float(source[0])*.06,.7,.95)
	if slope<-.10:throttle=.55
	return [throttle,0.0,clampf(error*1.7+float(source[2])*.06,-1.0,1.0)]

static func lead_position(target: Vector3, relative_velocity: Vector3, acceleration: Vector3, flight_time: float) -> Vector3:
	return target+relative_velocity*flight_time+acceleration*(.5*flight_time*flight_time)

static func aim_command(error: float, platform_rate: float, max_rate: float, neural_command: float) -> float:
	var correction=neural_command*.10*minf(1.0,absf(error)/deg_to_rad(8.0))
	return clampf((error*4.0-platform_rate)/maxf(.001,max_rate)+correction,-1.0,1.0)
