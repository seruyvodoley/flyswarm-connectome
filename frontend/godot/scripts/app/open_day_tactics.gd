extends RefCounted

# Engineered Open Day assistance, kept outside the frozen MaleCNS model.
# A separate seeded RNG keeps tactical choices independent of shell dispersion.
var random=RandomNumberGenerator.new()
var next_decision=-1.0
var last_threat=-10.0
var mode="flank"
var flank_sign=1.0
var standoff=60.0

func configure(match_seed: int) -> void:
	random.seed=match_seed ^ 0x4F50454E
	next_decision=-1.0
	last_threat=-10.0
	flank_sign=1.0 if random.randf()>.5 else -1.0

func plan(now: float, casemate: bool, health: float, distance: float, reloading: bool, threatened: bool) -> Dictionary:
	var react_to_threat=threatened and reloading and now-last_threat>3.0
	if now>=next_decision or react_to_threat:
		if react_to_threat:last_threat=now
		if random.randf()<.45:flank_sign=-flank_sign
		var choices=["flank","pressure","relocate","hold"]
		mode=choices[random.randi_range(0,choices.size()-1)]
		if health<.4 or react_to_threat:mode="disengage"
		elif distance>115.0:mode="pressure"
		standoff=random.randf_range(55.0,88.0) if casemate else random.randf_range(38.0,70.0)
		if mode=="pressure":standoff*=.78
		if mode=="disengage":standoff+=24.0
		next_decision=now+random.randf_range(3.5,7.5)
	var flank_degrees=35.0 if casemate else 62.0
	if mode=="pressure":flank_degrees=20.0
	elif mode=="relocate" or mode=="disengage":flank_degrees=85.0
	return {"mode":mode,"flank_sign":flank_sign,"standoff":standoff,"flank_angle":deg_to_rad(flank_degrees)*flank_sign,"next_decision":next_decision}

static func lead_position(target: Vector3, relative_velocity: Vector3, acceleration: Vector3, flight_time: float) -> Vector3:
	return target+relative_velocity*flight_time+acceleration*(.5*flight_time*flight_time)

static func aim_command(error: float, platform_rate: float, max_rate: float, neural_command: float) -> float:
	# Cancel hull rotation and taper neural corrections near the firing solution.
	# A constant decoder bias previously prevented the gun ever settling on it.
	var correction=neural_command*.10*minf(1.0,absf(error)/deg_to_rad(8.0))
	return clampf((error*4.0-platform_rate)/maxf(.001,max_rate)+correction,-1.0,1.0)
