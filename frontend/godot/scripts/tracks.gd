extends Node3D
# Contact-pressure/slip approximation. Visual rut depth does not edit terrain colliders.
var world
var multimesh: MultiMesh
var cursor=0
var capacity=6000
var last_positions={}
var accumulated={}
var rut_cells={}
var segments=0
var max_depth=0.0
func setup(battle):
	world=battle
	multimesh=MultiMesh.new()
	multimesh.transform_format=MultiMesh.TRANSFORM_3D
	multimesh.use_colors=true
	var mesh=BoxMesh.new()
	mesh.size=Vector3(1,.012,1)
	multimesh.mesh=mesh
	multimesh.instance_count=capacity
	multimesh.visible_instance_count=0
	var instance=MultiMeshInstance3D.new()
	instance.multimesh=multimesh
	var material=StandardMaterial3D.new()
	material.vertex_color_use_as_albedo=true
	material.roughness=1
	instance.material_override=material
	add_child(instance)
func soil(position: Vector3) -> Dictionary:
	if absf(position.x)<20 or absf(position.z)<12:return {"name":"road","stiffness":18000000.0,"resistance":.035,"grip":.7,"mark":.18}
	if absf(position.z-25*sin(position.x/180))<30:return {"name":"riverbed","stiffness":1200000.0,"resistance":.09,"grip":.43,"mark":.85}
	return {"name":"soil","stiffness":4000000.0,"resistance":.055,"grip":.6,"mark":.6}
func cell_key(position: Vector3) -> Vector2i:
	return Vector2i(floori(position.x/1.5),floori(position.z/1.5))
func belt_velocity(speed: float, yaw: float, spacing: float, side: int) -> float:
	# +Z forward, positive yaw turns right: the right belt is the inner belt.
	return speed-side*yaw*spacing*.5

func normal_at(at: Vector3) -> Vector3:
	return Vector3(world.terrain.height_at(at.x-1,at.z)-world.terrain.height_at(at.x+1,at.z),2,world.terrain.height_at(at.x,at.z-1)-world.terrain.height_at(at.x,at.z+1)).normalized()

func settlement(previous: float, equilibrium: float, shear_distance: float, slip: float) -> float:
	# Saturating compaction with irreversible shear remoulding. No dt dependence.
	var limit=minf(.18,equilibrium*(1.0+.65*slip))
	return maxf(previous,lerpf(previous,limit,1-exp(-maxf(0,shear_distance)/1.2)))

func contact(v,dt: float) -> Dictionary:
	var ground=soil(v.position)
	var spacing=float(v.cfg.width_m)-float(v.cfg.track_width_m)
	var area=2*float(v.cfg.track_width_m)*float(v.cfg.length_m)*.72
	var pressure=float(v.cfg.mass_kg)*9.81*normal_at(v.position).y/maxf(.1,area)
	var effort=absf(float(v.cmd[0]))*.65
	var slip=clampf((effort-ground.grip)/maxf(.1,ground.grip)+absf(v.yaw_rate)*.12,0,1)
	var depth=clampf(pressure/ground.stiffness*(1+slip),0,.18)
	var previous=0.0
	for side in [-1,1]:
		var at=v.position+v.global_basis.x*side*spacing*.5
		previous+=float(rut_cells.get(cell_key(at),0))*.5
	var resistance=ground.resistance+minf(.08,previous*.35)+slip*.025
	if not v.is_on_floor():
		for side in [0,1]:
			last_positions.erase(v.agent_id*2+side)
			accumulated.erase(v.agent_id*2+side)
		return {"resistance":ground.resistance,"grip":ground.grip,"slip":0.0,"depth":0.0,"pressure_pa":0.0}
	for side in [-1,1]:
		var key=v.agent_id*2+(1 if side==1 else 0)
		var at=v.position+v.global_basis.x*side*spacing*.5
		at.y=world.terrain.height_at(at.x,at.z)+.024
		if not last_positions.has(key):last_positions[key]=at;continue
		var previous_at: Vector3=last_positions[key]
		var travel=Vector2(at.x-previous_at.x,at.z-previous_at.z).length()
		var belt_speed=belt_velocity(v.speed,v.yaw_rate,spacing,side)
		accumulated[key]=float(accumulated.get(key,0))+absf(belt_speed)*dt
		if travel<.4 and accumulated[key]<.65:continue
		if travel>12:last_positions[key]=at;accumulated[key]=0;continue
		var direction=(at-previous_at).normalized() if travel>.04 else v.global_basis.z
		var centre=(at+previous_at)*.5
		centre.y=world.terrain.height_at(centre.x,centre.z)+.024
		var normal=normal_at(centre)
		var right=normal.cross(direction).normalized()
		direction=right.cross(normal).normalized()
		var basis=Basis(right,normal,direction).scaled(Vector3(v.cfg.track_width_m,.7+depth*6,maxf(.45,travel)))
		multimesh.set_instance_transform(cursor,Transform3D(basis,centre))
		var shade=.24-ground.mark*.16-slip*.025
		multimesh.set_instance_color(cursor,Color(shade*1.1,shade,shade*.75))
		cursor=(cursor+1)%capacity
		segments+=1
		multimesh.visible_instance_count=mini(capacity,segments)
		# Deposit along the swept strip, not only at the vehicle centre/endpoint.
		var samples=maxi(1,ceili(travel/.5))
		var shear=maxf(travel,float(accumulated[key]))/samples
		for sample in range(samples):
			var point=previous_at.lerp(at,(sample+.5)/samples)
			var cell=cell_key(point)
			var old_depth=float(rut_cells.get(cell,0))
			var new_depth=settlement(old_depth,depth,shear,slip)
			rut_cells[cell]=new_depth
			max_depth=maxf(max_depth,new_depth)
		last_positions[key]=at
		accumulated[key]=0
	return {"resistance":resistance,"grip":ground.grip,"slip":slip,"depth":depth,"pressure_pa":pressure}
